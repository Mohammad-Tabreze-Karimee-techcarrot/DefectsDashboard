import os
import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html as dhtml, Input, Output, callback_context

# Paths and data
current_dir = os.path.dirname(os.path.abspath(__file__))
excel_file = os.path.join(current_dir, "data", "Smart FM Defects through Python.xlsx")
df = pd.read_excel(excel_file)

required_cols = ["State", "ID", "Issue Links", "Severity", "Assigned To"]
for col in required_cols:
    if col not in df.columns:
        df[col] = "N/A"

df["State_Display"] = df["State"].replace({"Active": "Reopen"})
state_colors = {"New": "red", "Reopen": "maroon", "Closed": "green", "Resolved": "orange"}

df_open = df[~df["State"].str.lower().eq("closed")]
severity_order = ["High", "Medium", "Low", "Suggestion"]
df_open["Severity"] = df_open["Severity"].astype(str).str.replace(r"^\d+\s*-\s*", "", regex=True)

# Aggregate counts for severity
severity_counts = df_open["Severity"].value_counts().reindex(severity_order, fill_value=0).reset_index()
severity_counts.columns = ["Severity", "Count"]

# Aggregate counts for state
state_counts_df = df["State_Display"].value_counts().reset_index()
state_counts_df.columns = ["State_Display", "Count"]

total_defects = len(df)
new_count = state_counts_df.loc[state_counts_df["State_Display"]=="New", "Count"].sum() if "New" in state_counts_df["State_Display"].values else 0
reopen_count = state_counts_df.loc[state_counts_df["State_Display"]=="Reopen", "Count"].sum() if "Reopen" in state_counts_df["State_Display"].values else 0
closed_count = state_counts_df.loc[state_counts_df["State_Display"]=="Closed", "Count"].sum() if "Closed" in state_counts_df["State_Display"].values else 0
resolved_count = state_counts_df.loc[state_counts_df["State_Display"]=="Resolved", "Count"].sum() if "Resolved" in state_counts_df["State_Display"].values else 0

# App
app = Dash(__name__)
app.title = "Smart FM Replacement Defects Dashboard"

# Pie chart
pie_fig = px.pie(df, names="State_Display", title="Defects by State", hole=0.3,
                 color="State_Display", color_discrete_map=state_colors)
pie_fig.update_traces(textinfo="percent+label+value")

# Bar chart by state with correct counts
bar_state_fig = px.bar(state_counts_df, x="State_Display", y="Count",
                       title="Defects Count by State",
                       color="State_Display",
                       color_discrete_map=state_colors,
                       text="Count",
                       hover_data={"Count": True, "State_Display": True})
bar_state_fig.update_traces(hovertemplate="State: %{x}<br>Defects: %{y}")

def create_severity_fig(selected_severity=None):
    colors_map = {"High": "red", "Medium": "orange", "Low": "yellow", "Suggestion": "blue"}
    bar_colors = [colors_map[s] if s != selected_severity else "darkgreen" for s in severity_order]
    fig = px.bar(
        severity_counts,
        x="Severity",
        y="Count",
        title="Open Defects Count by Severity",
        category_orders={"Severity": severity_order},
        color="Severity",
        color_discrete_map=dict(zip(severity_order, bar_colors)),
        text="Count",
        hover_data={"Count": True, "Severity": True}
    )
    fig.update_traces(hovertemplate="Severity: %{x}<br>Open Defects: %{y}")
    return fig

bar_severity_fig = create_severity_fig()

# Layout
app.layout = dhtml.Div([
    dhtml.H1("📊 Defects Dashboard", style={"textAlign": "center"}),

    dhtml.H2("Defects Status", style={"marginBottom": "10px"}),
    dhtml.Table([
        dhtml.Thead(dhtml.Tr([dhtml.Th("New Defects"), dhtml.Th("Reopen Defects"),
                              dhtml.Th("Closed Defects"), dhtml.Th("Resolved Defects"),
                              dhtml.Th("Total Defects")])),
        dhtml.Tbody(dhtml.Tr([
            dhtml.Td(new_count, style={"color": "white", "backgroundColor": "red", "fontWeight": "bold", "textAlign": "center"}),
            dhtml.Td(reopen_count, style={"color": "white", "backgroundColor": "maroon", "fontWeight": "bold", "textAlign": "center"}),
            dhtml.Td(closed_count, style={"color": "white", "backgroundColor": "green", "fontWeight": "bold", "textAlign": "center"}),
            dhtml.Td(resolved_count, style={"color": "white", "backgroundColor": "orange", "fontWeight": "bold", "textAlign": "center"}),
            dhtml.Td(total_defects, style={"color": "black", "backgroundColor": "lightgrey", "fontWeight": "bold", "textAlign": "center"})
        ]))
    ], style={"width": "80%", "margin": "auto", "marginBottom": "30px", "borderCollapse": "collapse"}),

    dhtml.Div([
        dcc.Graph(id="pie-chart", figure=pie_fig, style={"width": "33%", "height": "320px"}),
        dcc.Graph(id="bar-chart-state", figure=bar_state_fig, style={"width": "33%", "height": "320px"}),
        dcc.Graph(id="bar-chart-severity", figure=bar_severity_fig, style={"width": "33%", "height": "320px"})
    ], style={"display": "flex", "flexDirection": "row", "justifyContent": "space-between",
              "alignItems": "flex-start", "flexWrap": "nowrap", "marginBottom": "20px"}),

    dhtml.H2("🔗 Defects with Details", style={"marginTop": "20px"}),
    dhtml.Div(id="links-container", style={"marginTop": "20px"})
])

# Callback
@app.callback(
    [Output("links-container", "children"),
     Output("bar-chart-severity", "figure")],
    [Input("pie-chart", "clickData"),
     Input("bar-chart-state", "clickData"),
     Input("bar-chart-severity", "clickData")]
)
def display_links_and_highlight(pie_click, bar_state_click, bar_severity_click):
    ctx = callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None

    # Reset details table initially
    header = dhtml.Div([
        dhtml.Span("S.No", style={"fontWeight": "bold", "width": "50px", "display": "inline-block"}),
        dhtml.Span("Defect Link", style={"fontWeight": "bold", "width": "150px", "display": "inline-block"}),
        dhtml.Span("Severity", style={"fontWeight": "bold", "width": "150px", "display": "inline-block", "marginLeft": "40px"}),
    ], style={"marginBottom": "10px", "fontFamily": "Courier New, monospace",
              "borderBottom": "2px solid #000", "paddingBottom": "5px"})
    # By default, show only header
    details_container = dhtml.Div([header], style={"marginTop": "10px"})

    filtered = pd.DataFrame()
    selected_severity = None

    if triggered_id == "pie-chart" and pie_click:
        state_display = pie_click["points"][0]["label"]
        filtered = df[df["State"]=="Active"] if state_display=="Reopen" else df[df["State_Display"]==state_display]
    elif triggered_id == "bar-chart-state" and bar_state_click:
        state_display = bar_state_click["points"][0]["x"]
        filtered = df[df["State"]=="Active"] if state_display=="Reopen" else df[df["State_Display"]==state_display]
    elif triggered_id == "bar-chart-severity" and bar_severity_click:
        selected_severity = bar_severity_click["points"][0]["x"]
        filtered = df_open[df_open["Severity"]==selected_severity]

    if not filtered.empty:
        filtered = filtered.sort_values(by=["Assigned To","ID"], na_position="last")
        filtered["S.No"] = filtered.groupby("Assigned To").cumcount() + 1

        groups = []
        for assigned_to, group in filtered.groupby("Assigned To"):
            defect_rows = [
                dhtml.Div([
                    dhtml.Span(f"{row['S.No']}", style={"display":"inline-block","width":"50px","fontFamily":"Courier New, monospace"}),
                    dhtml.A(f"Defect {row['ID']}", href=row["Issue Links"], target="_blank",
                            style={"display":"inline-block","width":"150px","fontFamily":"Courier New, monospace"}),
                    dhtml.Span(f"{row['Severity']}", style={"display":"inline-block","width":"150px",
                                                            "fontFamily":"Courier New, monospace","marginLeft":"40px"})
                ], style={"marginBottom":"4px"}) for _, row in group.iterrows()
            ]
            details_section = dhtml.Details([
                dhtml.Summary(assigned_to, style={"fontWeight":"bold","color":"#007ACC",
                                                  "cursor":"pointer","fontSize":"16px","fontFamily":"Arial"}),
                dhtml.Div(defect_rows, style={"marginLeft":"20px","marginTop":"6px"})
            ], open=False)
            groups.append(details_section)

        details_container = dhtml.Div([header]+groups, style={"marginTop":"10px"})

    return details_container, create_severity_fig(selected_severity)

# Run
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)
