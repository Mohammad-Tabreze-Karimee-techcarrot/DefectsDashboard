import os
import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html as dhtml, Input, Output, callback_context

# Correct path to Excel file inside 'data' folder
current_dir = os.path.dirname(os.path.abspath(__file__))
excel_file = os.path.join(current_dir, "data", "Smart FM Defects through Python.xlsx")

# Load Excel
df = pd.read_excel(excel_file)

# Ensure required columns exist
required_cols = ["State", "ID", "Issue Links", "Severity", "Assigned To"]
for col in required_cols:
    if col not in df.columns:
        df[col] = "N/A"

# Replace 'Active' with 'Reopen' for display in charts
df["State_Display"] = df["State"].replace({"Active": "Reopen"})

# Define colors for states
state_colors = {
    "New": "red",
    "Reopen": "maroon",
    "Closed": "green",
    "Resolved": "orange"
}

# Filter for open defects only (exclude Closed)
df_open = df[~df["State"].str.lower().eq("closed")]

# Remove numbers from Severity and ensure order
severity_order = ["High", "Medium", "Low", "Suggestion"]
df_open["Severity"] = df_open["Severity"].astype(str).str.replace(r"^\d+\s*-\s*", "", regex=True)

# Count defects by state
state_counts = df["State_Display"].value_counts().to_dict()
total_defects = len(df)

new_count = state_counts.get("New", 0)
reopen_count = state_counts.get("Reopen", 0)
closed_count = state_counts.get("Closed", 0)
resolved_count = state_counts.get("Resolved", 0)

# Create Dash app
app = Dash(__name__)
app.title = "Defects Dashboard"

# Pie chart with counts + percentages
pie_fig = px.pie(
    df,
    names="State_Display",
    title="Defects by State",
    hole=0.3,
    color="State_Display",
    color_discrete_map=state_colors
)
pie_fig.update_traces(textinfo="percent+label+value")

# Bar chart for state
bar_state_fig = px.bar(
    df, x="State_Display", title="Defects Count by State", color="State_Display",
    color_discrete_map=state_colors
)

# Bar chart for open defects by severity
bar_severity_fig = px.bar(
    df_open,
    x="Severity",
    title="Open Defects Count by Severity",
    category_orders={"Severity": severity_order},
    color="Severity",
    color_discrete_map={
        "High": "red",
        "Medium": "orange",
        "Low": "yellow",
        "Suggestion": "blue"
    },
    text_auto=True
)

# Layout
app.layout = dhtml.Div([
    dhtml.H1("📊 Defects Dashboard", style={"textAlign": "center"}),

    # ====== DEFECTS STATUS TABLE ======
    dhtml.H2("Defects Status", style={"marginBottom": "10px"}),

    dhtml.Table([
        dhtml.Thead(
            dhtml.Tr([
                dhtml.Th("New Defects"),
                dhtml.Th("Reopen Defects"),
                dhtml.Th("Closed Defects"),
                dhtml.Th("Resolved Defects"),
                dhtml.Th("Total Defects")
            ])
        ),
        dhtml.Tbody([
            dhtml.Tr([
                dhtml.Td(new_count, style={"color": "white", "backgroundColor": "red", "fontWeight": "bold", "textAlign": "center"}),
                dhtml.Td(reopen_count, style={"color": "white", "backgroundColor": "maroon", "fontWeight": "bold", "textAlign": "center"}),
                dhtml.Td(closed_count, style={"color": "white", "backgroundColor": "green", "fontWeight": "bold", "textAlign": "center"}),
                dhtml.Td(resolved_count, style={"color": "white", "backgroundColor": "orange", "fontWeight": "bold", "textAlign": "center"}),
                dhtml.Td(total_defects, style={"color": "black", "backgroundColor": "lightgrey", "fontWeight": "bold", "textAlign": "center"})
            ])
        ])
    ], style={"width": "80%", "margin": "auto", "marginBottom": "30px", "borderCollapse": "collapse"}),

    # ====== CHARTS ======
    dhtml.Div([
        dcc.Graph(id="pie-chart", figure=pie_fig, style={"width": "33%", "height": "320px"}),
        dcc.Graph(id="bar-chart-state", figure=bar_state_fig, style={"width": "33%", "height": "320px"}),
        dcc.Graph(id="bar-chart-severity", figure=bar_severity_fig, style={"width": "33%", "height": "320px"})
    ], style={
        "display": "flex",
        "flexDirection": "row",
        "justifyContent": "space-between",
        "alignItems": "flex-start",
        "flexWrap": "nowrap",
        "marginBottom": "20px"
    }),

    # ====== DEFECT DETAILS ======
    dhtml.H2("🔗 Defects with Details", style={"marginTop": "20px"}),
    dhtml.Div(id="links-container", style={"marginTop": "20px"})
])

# ====== CALLBACK ======
@app.callback(
    Output("links-container", "children"),
    Input("pie-chart", "clickData"),
    Input("bar-chart-state", "clickData"),
    Input("bar-chart-severity", "clickData")
)
def display_links(pie_click, bar_state_click, bar_severity_click):
    ctx = callback_context
    if not ctx.triggered:
        return "Click on a chart to see defect links."

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    filtered = pd.DataFrame()

    # 🎯 Filter based on clicked chart
    if triggered_id == "pie-chart" and pie_click:
        state_display = pie_click["points"][0]["label"]
        if state_display == "Reopen":
            filtered = df[df["State"] == "Active"]
        else:
            filtered = df[df["State_Display"] == state_display]

    elif triggered_id == "bar-chart-state" and bar_state_click:
        state_display = bar_state_click["points"][0]["x"]
        if state_display == "Reopen":
            filtered = df[df["State"] == "Active"]
        else:
            filtered = df[df["State_Display"] == state_display]

    elif triggered_id == "bar-chart-severity" and bar_severity_click:
        severity = bar_severity_click["points"][0]["x"]
        filtered = df_open[df_open["Severity"] == severity]

    else:
        return "No data found."

    # Sort per Assigned To
    filtered = filtered.sort_values(by=["Assigned To", "ID"], na_position="last")
    filtered["S.No"] = filtered.groupby("Assigned To").cumcount() + 1

    # Table header only; details hidden until user clicks on Assigned To
    header = dhtml.Div([
        dhtml.Span("S.No", style={"fontWeight": "bold", "width": "50px", "display": "inline-block"}),
        dhtml.Span("Defect Link", style={"fontWeight": "bold", "width": "150px", "display": "inline-block"}),
        dhtml.Span("Severity", style={"fontWeight": "bold", "width": "150px", "display": "inline-block", "marginLeft": "40px"}),
    ], style={
        "marginBottom": "10px",
        "fontFamily": "Courier New, monospace",
        "borderBottom": "2px solid #000",
        "paddingBottom": "5px"
    })

    # Create collapsible sections for each Assigned To, all closed by default
    groups = []
    for assigned_to, group in filtered.groupby("Assigned To"):
        defect_rows = [
            dhtml.Div([
                dhtml.Span(f"{row['S.No']}", style={
                    "display": "inline-block", "width": "50px", "fontFamily": "Courier New, monospace"
                }),
                dhtml.A(f"Defect {row['ID']}", href=row["Issue Links"], target="_blank", style={
                    "display": "inline-block", "width": "150px", "fontFamily": "Courier New, monospace"
                }),
                dhtml.Span(f"{row['Severity']}", style={
                    "display": "inline-block", "width": "150px", "fontFamily": "Courier New, monospace", "marginLeft": "40px"
                })
            ], style={"marginBottom": "4px"})
            for _, row in group.iterrows()
        ]

        details_section = dhtml.Details([
            dhtml.Summary(assigned_to, style={
                "fontWeight": "bold",
                "color": "#007ACC",
                "cursor": "pointer",
                "fontSize": "16px",
                "fontFamily": "Arial"
            }),
            dhtml.Div(defect_rows, style={"marginLeft": "20px", "marginTop": "6px"})
        ], open=False)  # Always closed by default

        groups.append(details_section)

    return dhtml.Div([header] + groups, style={"marginTop": "10px"})

# Run app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)
