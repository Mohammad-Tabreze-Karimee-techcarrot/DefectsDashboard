import os
import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html as dhtml, Input, Output, State, callback_context
from defectsextraction import update_defects_excel

# ============================================================
# Fetch latest data always before app load
# ============================================================
def get_latest_data():
    """Always refresh defects data from DevOps before loading dashboard"""
    excel_path = update_defects_excel()
    return pd.read_excel(excel_path)

# Initial load
df = get_latest_data()

# Ensure required columns
required_cols = ["State", "ID", "Issue Links", "Severity", "Assigned To"]
for col in required_cols:
    if col not in df.columns:
        df[col] = "N/A"

df["State_Display"] = df["State"].replace({"Active": "Reopen"})
state_colors = {"New": "red", "Reopen": "maroon", "Closed": "green", "Resolved": "orange"}

# ============================================================
# Dash App Initialization
# ============================================================
app = Dash(__name__)
app.title = "Smart FM Replacement Defects Dashboard"

# ============================================================
# Base Figures
# ============================================================
def create_charts(df):
    df_open = df[~df["State"].str.lower().eq("closed")]
    df_open["Severity"] = df_open["Severity"].astype(str).str.replace(r"^\d+\s*-\s*", "", regex=True)

    severity_order = ["High", "Medium", "Low", "Suggestion"]
    severity_counts = df_open["Severity"].value_counts().reindex(severity_order, fill_value=0).reset_index()
    severity_counts.columns = ["Severity", "Count"]

    state_counts_df = df["State_Display"].value_counts().reset_index()
    state_counts_df.columns = ["State_Display", "Count"]

    pie_fig = px.pie(
        df,
        names="State_Display",
        title="<b>Defects by State</b>",
        hole=0.3,
        color="State_Display",
        color_discrete_map=state_colors
    )
    pie_fig.update_traces(textinfo="percent+label+value")

    bar_state_fig = px.bar(
        state_counts_df, x="State_Display", y="Count",
        title="<b>Defects Count by State</b>",
        color="State_Display",
        color_discrete_map=state_colors,
        text="Count"
    )
    bar_state_fig.update_traces(hovertemplate="State: %{x}<br>Defects: %{y}")
    bar_state_fig.update_layout(xaxis={'tickangle': 0}, title_font=dict(size=16, color="#1f77b4"))

    bar_severity_fig = px.bar(
        severity_counts,
        x="Severity",
        y="Count",
        title="<b>Open Defects Count by Severity</b>",
        category_orders={"Severity": severity_order},
        color="Severity",
        color_discrete_map={"High": "red", "Medium": "orange", "Low": "yellow", "Suggestion": "blue"},
        text="Count"
    )
    bar_severity_fig.update_layout(title_font=dict(size=16, color="#1f77b4"))

    return pie_fig, bar_state_fig, bar_severity_fig

pie_fig, bar_state_fig, bar_severity_fig = create_charts(df)

# ============================================================
# Layout
# ============================================================
app.layout = dhtml.Div([
    dcc.Store(id="filter-state", storage_type="session"),  # <-- store filter context
    dcc.Interval(id="auto-refresh", interval=5 * 60 * 1000, n_intervals=0),  # 5 mins auto-refresh

    dhtml.H1("Smart FM Replacement Defects Dashboard", style={"textAlign": "center"}),

    dhtml.H2("Defects Status", style={"marginBottom": "10px"}),

    # ======= Summary Table =======
    dhtml.Div(id="summary-table"),

    # ======= Charts =======
    dhtml.Div([
        dcc.Graph(id="pie-chart", figure=pie_fig, style={"width": "33%", "height": "320px"}),
        dcc.Graph(id="bar-chart-state", figure=bar_state_fig, style={"width": "33%", "height": "320px"}),
        dcc.Graph(id="bar-chart-severity", figure=bar_severity_fig, style={"width": "33%", "height": "320px"})
    ], style={
        "display": "flex", "flexDirection": "row", "justifyContent": "space-between",
        "alignItems": "flex-start", "flexWrap": "nowrap", "marginBottom": "20px"
    }),

    dhtml.H2("🔗 Defects with Details", style={"marginTop": "20px"}),
    dhtml.Div(id="links-container", style={"marginTop": "20px"})
])

# ============================================================
# Callbacks
# ============================================================

# ---------- Update summary table ----------
@app.callback(
    Output("summary-table", "children"),
    Input("auto-refresh", "n_intervals")
)
def update_summary(_):
    df = get_latest_data()
    df["State_Display"] = df["State"].replace({"Active": "Reopen"})
    state_counts = df["State_Display"].value_counts()

    def get_count(state):
        return state_counts.get(state, 0)

    total_defects = len(df)
    return dhtml.Table([
        dhtml.Thead(dhtml.Tr([
            dhtml.Th("New"), dhtml.Th("Reopen"),
            dhtml.Th("Closed"), dhtml.Th("Resolved"), dhtml.Th("Total")
        ])),
        dhtml.Tbody(dhtml.Tr([
            dhtml.Td(get_count("New"), style={"color": "white", "backgroundColor": "red", "textAlign": "center", "fontWeight": "bold"}),
            dhtml.Td(get_count("Reopen"), style={"color": "white", "backgroundColor": "maroon", "textAlign": "center", "fontWeight": "bold"}),
            dhtml.Td(get_count("Closed"), style={"color": "white", "backgroundColor": "green", "textAlign": "center", "fontWeight": "bold"}),
            dhtml.Td(get_count("Resolved"), style={"color": "white", "backgroundColor": "orange", "textAlign": "center", "fontWeight": "bold"}),
            dhtml.Td(total_defects, style={"color": "black", "backgroundColor": "lightgrey", "textAlign": "center", "fontWeight": "bold"})
        ]))
    ], style={"width": "80%", "margin": "auto", "marginBottom": "30px"})


# ---------- Handle filtering and refresh ----------
@app.callback(
    [Output("links-container", "children"),
     Output("bar-chart-severity", "figure"),
     Output("filter-state", "data")],
    [Input("pie-chart", "clickData"),
     Input("bar-chart-state", "clickData"),
     Input("bar-chart-severity", "clickData"),
     Input("auto-refresh", "n_intervals")],
    [State("filter-state", "data")]
)
def display_links_and_highlight(pie_click, bar_state_click, bar_severity_click, n_intervals, stored_filter):
    ctx = callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None

    # ✅ Determine filter to use
    filter_state = stored_filter or {}

    if triggered_id in ["pie-chart", "bar-chart-state", "bar-chart-severity"]:
        # update filter if user clicked something
        filter_state = {
            "source": triggered_id,
            "value": None
        }
        if triggered_id == "pie-chart" and pie_click:
            filter_state["value"] = pie_click["points"][0]["label"]
        elif triggered_id == "bar-chart-state" and bar_state_click:
            filter_state["value"] = bar_state_click["points"][0]["x"]
        elif triggered_id == "bar-chart-severity" and bar_severity_click:
            filter_state["value"] = bar_severity_click["points"][0]["x"]

    # ✅ Fetch updated data (auto-refresh or user interaction)
    df = get_latest_data()
    df["State_Display"] = df["State"].replace({"Active": "Reopen"})
    df_open = df[~df["State"].str.lower().eq("closed")]
    df_open["Severity"] = df_open["Severity"].astype(str).str.replace(r"^\d+\s*-\s*", "", regex=True)

    filtered = pd.DataFrame()
    selected_severity = None

    if filter_state and "source" in filter_state and "value" in filter_state and filter_state["value"]:
        if filter_state["source"] in ["pie-chart", "bar-chart-state"]:
            state_display = filter_state["value"]
            filtered = df[df["State"] == "Active"] if state_display == "Reopen" else df[df["State_Display"] == state_display]
        elif filter_state["source"] == "bar-chart-severity":
            selected_severity = filter_state["value"]
            filtered = df_open[df_open["Severity"] == selected_severity]

    # Create header
    header = dhtml.Div([
        dhtml.Span("S.No", style={"fontWeight": "bold", "width": "50px", "display": "inline-block"}),
        dhtml.Span("Defect Link", style={"fontWeight": "bold", "width": "150px", "display": "inline-block"}),
        dhtml.Span("Severity", style={"fontWeight": "bold", "width": "150px", "display": "inline-block", "marginLeft": "40px"})
    ], style={"marginBottom": "10px", "fontFamily": "Courier New, monospace", "borderBottom": "2px solid #000", "paddingBottom": "5px"})

    details_container = [header]
    if not filtered.empty:
        filtered = filtered.sort_values(by=["Assigned To", "ID"])
        filtered["S.No"] = filtered.groupby("Assigned To").cumcount() + 1
        for i, (assigned_to, group) in enumerate(filtered.groupby("Assigned To")):
            defect_rows = [
                dhtml.Div([
                    dhtml.Span(str(row["S.No"]), style={"display": "inline-block", "width": "50px"}),
                    dhtml.A(f"Defect {row['ID']}", href=row["Issue Links"], target="_blank", style={"width": "150px", "display": "inline-block"}),
                    dhtml.Span(str(row["Severity"]), style={"width": "150px", "display": "inline-block", "marginLeft": "40px"})
                ], style={"marginBottom": "4px"})
                for _, row in group.iterrows()
            ]
            details_section = dhtml.Details([
                dhtml.Summary(assigned_to, style={"fontWeight": "bold", "color": "#007ACC", "cursor": "pointer", "fontSize": "16px"}),
                dhtml.Div(defect_rows, style={"marginLeft": "20px", "marginTop": "6px"})
            ])
            details_container.append(details_section)

    bar_severity_fig = px.bar(
        df_open["Severity"].value_counts().reindex(["High", "Medium", "Low", "Suggestion"], fill_value=0).reset_index(),
        x="index", y="Severity", title="<b>Open Defects Count by Severity</b>",
        color="index", color_discrete_map={"High": "red", "Medium": "orange", "Low": "yellow", "Suggestion": "blue"},
        text="Severity"
    )
    bar_severity_fig.update_layout(title_font=dict(size=16, color="#1f77b4"))

    return dhtml.Div(details_container), bar_severity_fig, filter_state


# ============================================================
# Run Server
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)
