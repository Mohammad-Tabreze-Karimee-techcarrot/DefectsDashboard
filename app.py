import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html as dhtml, Input, Output, callback_context, State
from datetime import datetime
import subprocess
import threading
import time

# Paths and data
current_dir = os.path.dirname(os.path.abspath(__file__))
excel_file = os.path.join(current_dir, "data", "Smart FM Defects through Python.xlsx")

def load_data():
    """Load data from Excel file"""
    if not os.path.exists(excel_file):
        print(f"Error: Excel file not found at {excel_file}")
        return pd.DataFrame(columns=["State", "ID", "Issue Links", "Severity", "Assigned To"])
    
    df = pd.read_excel(excel_file)
    required_cols = ["State", "ID", "Issue Links", "Severity", "Assigned To"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = "N/A"
    
    # Clean and standardize the Severity column BEFORE any filtering
    df["Severity"] = df["Severity"].astype(str).str.replace(r"^\d+\s*-\s*", "", regex=True).str.strip()
    
    # Map severity levels including Critical
    severity_map = {
        "Suggestion": "Suggestion",
        "Low": "Low",
        "Medium": "Medium",
        "High": "High",
        "Critical": "Critical"
    }
    df["Severity"] = df["Severity"].map(severity_map).fillna("Unknown")
    
    # Create State_Display column (Active -> Reopen)
    df["State_Display"] = df["State"].replace({"Active": "Reopen"})
    
    return df

def refresh_data_from_devops():
    """Run the defects extraction script"""
    try:
        print(f"🔄 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Refreshing data from DevOps...")
        extraction_script = os.path.join(current_dir, "defectsextraction.py")
        subprocess.run(["python", extraction_script], check=True)
        print(f"✅ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Data refresh completed")
    except Exception as e:
        print(f"❌ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error refreshing data: {str(e)}")

def schedule_data_refresh():
    """Background thread to refresh data every 5 minutes"""
    while True:
        time.sleep(300)  # 5 minutes
        refresh_data_from_devops()

# Start background refresh thread
refresh_thread = threading.Thread(target=schedule_data_refresh, daemon=True)
refresh_thread.start()

# Define colors
state_colors = {"New": "#dc3545", "Reopen": "#7d1e2b", "Closed": "#28a745", "Resolved": "#fd7e14"}
severity_order = ["Critical", "High", "Medium", "Low", "Suggestion"]

# App
app = Dash(__name__)
server = app.server  # THIS LINE IS CRITICAL FOR WAITRESS/PRODUCTION
app.title = "Smart FM Replacement Defects Dashboard"

# Layout
app.layout = dhtml.Div([
    dcc.Interval(
        id='interval-component',
        interval=300*1000,  # Refresh every 5 minutes (in milliseconds)
        n_intervals=0
    ),
    dcc.Store(id='data-store'),  # Store for data
    dcc.Store(id='scroll-trigger', data=0),  # Store to trigger scroll
    
    dhtml.Div([
        dhtml.H1("Smart FM Replacement Defects Dashboard", 
                style={"textAlign": "center", "color": "#2c3e50", "marginBottom": "10px",
                       "fontFamily": "Arial, sans-serif", "fontWeight": "bold"}),
        dhtml.Div(id="last-updated", style={"textAlign": "center", "color": "#7f8c8d", 
                                            "fontSize": "14px", "marginBottom": "20px"})
    ]),

    dhtml.Div(id="status-table"),

    dhtml.Div([
        dcc.Graph(id="pie-chart", style={"width": "33%", "height": "400px"}, config={'displayModeBar': False}),
        dcc.Graph(id="bar-chart-state", style={"width": "33%", "height": "400px"}, config={'displayModeBar': False}),
        dcc.Graph(id="bar-chart-severity", style={"width": "33%", "height": "400px"}, config={'displayModeBar': False})
    ], style={"display": "flex", "flexDirection": "row", "justifyContent": "space-between",
              "alignItems": "flex-start", "flexWrap": "nowrap", "marginBottom": "30px",
              "padding": "0 20px"}),

    dhtml.H2("🔗 Defects with Details", 
            id="defects-section",
            style={"marginTop": "30px", "marginLeft": "20px", "color": "#2c3e50",
                   "fontFamily": "Arial, sans-serif", "fontWeight": "bold"}),
    dhtml.Div(id="links-container", style={"marginTop": "20px", "padding": "0 20px"}),
    
    # Hidden div to trigger scroll
    dhtml.Div(id='scroll-output', style={'display': 'none'})
], style={"backgroundColor": "#f8f9fa", "minHeight": "100vh", "padding": "20px 0"})

# Callback to load data
@app.callback(
    Output('data-store', 'data'),
    [Input('interval-component', 'n_intervals')]
)
def update_data_store(n):
    df = load_data()
    return df.to_json(date_format='iso', orient='split')

# Main callback
@app.callback(
    [Output("status-table", "children"),
     Output("pie-chart", "figure"),
     Output("bar-chart-state", "figure"),
     Output("bar-chart-severity", "figure"),
     Output("links-container", "children"),
     Output("last-updated", "children"),
     Output("scroll-trigger", "data")],
    [Input('data-store', 'data'),
     Input("pie-chart", "clickData"),
     Input("bar-chart-state", "clickData"),
     Input("bar-chart-severity", "clickData")],
    [State("scroll-trigger", "data")]
)
def update_all(json_data, pie_click, bar_state_click, bar_severity_click, scroll_count):
    if not json_data:
        return None, {}, {}, {}, None, "", scroll_count
    
    df = pd.read_json(json_data, orient='split')
    
    # Define colors
    state_colors = {"New": "#dc3545", "Reopen": "#7d1e2b", "Closed": "#28a745", "Resolved": "#fd7e14"}
    
    # Filter for open defects (exclude Closed AND Resolved)
    df_open = df[~df["State"].str.lower().isin(["closed", "resolved"])]
    
    # Aggregate counts for severity from OPEN defects only
    severity_counts = df_open["Severity"].value_counts().reindex(severity_order, fill_value=0).reset_index()
    severity_counts.columns = ["Severity", "Count"]
    
    # Aggregate counts for state
    state_counts_df = df["State_Display"].value_counts().reset_index()
    state_counts_df.columns = ["State_Display", "Count"]
    
    # Calculate summary metrics
    total_defects = len(df)
    new_count = int(state_counts_df.loc[state_counts_df["State_Display"]=="New", "Count"].sum()) if "New" in state_counts_df["State_Display"].values else 0
    reopen_count = int(state_counts_df.loc[state_counts_df["State_Display"]=="Reopen", "Count"].sum()) if "Reopen" in state_counts_df["State_Display"].values else 0
    closed_count = int(state_counts_df.loc[state_counts_df["State_Display"]=="Closed", "Count"].sum()) if "Closed" in state_counts_df["State_Display"].values else 0
    resolved_count = int(state_counts_df.loc[state_counts_df["State_Display"]=="Resolved", "Count"].sum()) if "Resolved" in state_counts_df["State_Display"].values else 0
    
    # Status Table - REDUCED HEIGHT
    status_table = dhtml.Table([
        dhtml.Thead(dhtml.Tr([
            dhtml.Th("New Defects", style={"padding": "10px 15px", "fontSize": "14px", "fontWeight": "bold", "color": "#2c3e50"}), 
            dhtml.Th("Reopen Defects", style={"padding": "10px 15px", "fontSize": "14px", "fontWeight": "bold", "color": "#2c3e50"}),
            dhtml.Th("Closed Defects", style={"padding": "10px 15px", "fontSize": "14px", "fontWeight": "bold", "color": "#2c3e50"}), 
            dhtml.Th("Resolved Defects", style={"padding": "10px 15px", "fontSize": "14px", "fontWeight": "bold", "color": "#2c3e50"}),
            dhtml.Th("Total Defects", style={"padding": "10px 15px", "fontSize": "14px", "fontWeight": "bold", "color": "#2c3e50"})
        ]), style={"backgroundColor": "#e9ecef"}),
        dhtml.Tbody(dhtml.Tr([
            dhtml.Td(new_count, style={"color": "white", "backgroundColor": "#dc3545", "fontWeight": "bold", 
                                      "textAlign": "center", "padding": "12px", "fontSize": "20px"}),
            dhtml.Td(reopen_count, style={"color": "white", "backgroundColor": "#7d1e2b", "fontWeight": "bold", 
                                         "textAlign": "center", "padding": "12px", "fontSize": "20px"}),
            dhtml.Td(closed_count, style={"color": "white", "backgroundColor": "#28a745", "fontWeight": "bold", 
                                         "textAlign": "center", "padding": "12px", "fontSize": "20px"}),
            dhtml.Td(resolved_count, style={"color": "white", "backgroundColor": "#fd7e14", "fontWeight": "bold", 
                                           "textAlign": "center", "padding": "12px", "fontSize": "20px"}),
            dhtml.Td(total_defects, style={"color": "white", "backgroundColor": "#6c757d", "fontWeight": "bold", 
                                          "textAlign": "center", "padding": "12px", "fontSize": "20px"})
        ]))
    ], style={"width": "90%", "margin": "auto", "marginBottom": "40px", "borderCollapse": "collapse",
              "boxShadow": "0 4px 6px rgba(0,0,0,0.1)", "borderRadius": "8px", "overflow": "hidden"})
    
    # Determine which state/severity is selected
    ctx = callback_context
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None
    selected_state = None
    selected_severity = None
    trigger_scroll = scroll_count
    
    if triggered_id == "pie-chart" and pie_click:
        selected_state = pie_click["points"][0]["label"]
        trigger_scroll = scroll_count + 1
    elif triggered_id == "bar-chart-state" and bar_state_click:
        selected_state = bar_state_click["points"][0]["x"]
        trigger_scroll = scroll_count + 1
    elif triggered_id == "bar-chart-severity" and bar_severity_click:
        selected_severity = bar_severity_click["points"][0]["x"]
        trigger_scroll = scroll_count + 1
    
    # Pie chart with enhanced styling - MAKE IT CLICKABLE - SHOW ALL STATES
    # Get all state counts in the correct order
    state_display_order = ["New", "Reopen", "Closed", "Resolved"]
    pie_labels = []
    pie_values = []
    pie_colors = []
    
    for state in state_display_order:
        if state in state_counts_df["State_Display"].values:
            count = state_counts_df.loc[state_counts_df["State_Display"]==state, "Count"].values[0]
            pie_labels.append(state)
            pie_values.append(count)
            pie_colors.append(state_colors.get(state, "#6c757d"))
    
    pie_fig = go.Figure(data=[go.Pie(
        labels=pie_labels,
        values=pie_values,
        hole=0.4,
        marker=dict(colors=pie_colors),
        textinfo='percent+label+value',
        textfont=dict(size=14),
        hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>',
        pull=[0.05 if selected_state == label else 0 for label in pie_labels]  # Highlight selected slice
    )])
    
    pie_fig.update_layout(
        title="<b>Defects by State</b>",
        title_font=dict(size=20, family="Arial, sans-serif", color="#2c3e50"),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        margin=dict(t=80, b=40, l=40, r=40),
        hoverlabel=dict(bgcolor="white", font_size=14),
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05)
    )
    
    # Bar chart by state with selection indicator - INCREASED TOP MARGIN
    bar_state_fig = go.Figure()
    for state in state_counts_df["State_Display"]:
        count = state_counts_df.loc[state_counts_df["State_Display"]==state, "Count"].values[0]
        is_selected = (selected_state == state)
        
        bar_state_fig.add_trace(go.Bar(
            x=[state],
            y=[count],
            name=state,
            marker=dict(
                color=state_colors.get(state, "#6c757d"),
                line=dict(color="#000000", width=4) if is_selected else dict(color=state_colors.get(state, "#6c757d"), width=0)
            ),
            text=[count],
            textposition='outside',
            textfont=dict(size=14, color="#2c3e50", family="Arial"),
            hovertemplate=f"<b>{state}</b><br>Defects: {count}<extra></extra>"
        ))
    
    # Calculate dynamic y-axis range
    max_count = state_counts_df["Count"].max()
    y_range = [0, max_count * 1.15]  # Add 15% padding at top
    
    bar_state_fig.update_layout(
        title="<b>Defects Count by State</b>",
        title_font=dict(size=20, family="Arial, sans-serif", color="#2c3e50"),
        xaxis_title="State",
        yaxis_title="Count",
        showlegend=False,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#f8f9fa",
        margin=dict(t=80, b=60, l=60, r=40),
        xaxis=dict(tickfont=dict(size=13, color="#2c3e50")),
        yaxis=dict(
            tickfont=dict(size=12, color="#2c3e50"), 
            gridcolor="#e9ecef",
            range=y_range
        ),
        bargap=0.3,
        hoverlabel=dict(bgcolor="white", font_size=14)
    )
    
    # Bar chart by severity with selection indicator - INCREASED TOP MARGIN
    colors_map = {
        "Critical": "#8B0000",
        "High": "#dc3545",
        "Medium": "#fd7e14",
        "Low": "#ffc107",
        "Suggestion": "#17a2b8"
    }
    
    bar_severity_fig = go.Figure()
    for severity in severity_order:
        count = severity_counts.loc[severity_counts["Severity"]==severity, "Count"].values[0]
        is_selected = (selected_severity == severity)
        
        bar_severity_fig.add_trace(go.Bar(
            x=[severity],
            y=[count],
            name=severity,
            marker=dict(
                color=colors_map.get(severity, "#6c757d"),
                line=dict(color="#000000", width=4) if is_selected else dict(color=colors_map.get(severity, "#6c757d"), width=0)
            ),
            text=[count],
            textposition='outside',
            textfont=dict(size=14, color="#2c3e50", family="Arial"),
            hovertemplate=f"<b>{severity}</b><br>Open Defects: {count}<extra></extra>"
        ))
    
    # Calculate dynamic y-axis range
    max_sev_count = severity_counts["Count"].max()
    y_sev_range = [0, max_sev_count * 1.15]  # Add 15% padding at top
    
    bar_severity_fig.update_layout(
        title="<b>Open Defects Count by Severity</b>",
        title_font=dict(size=20, family="Arial, sans-serif", color="#2c3e50"),
        xaxis_title="Severity",
        yaxis_title="Open Defects",
        showlegend=False,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#f8f9fa",
        margin=dict(t=80, b=60, l=60, r=40),
        xaxis=dict(tickfont=dict(size=13, color="#2c3e50")),
        yaxis=dict(
            tickfont=dict(size=12, color="#2c3e50"), 
            gridcolor="#e9ecef",
            range=y_sev_range
        ),
        bargap=0.3,
        hoverlabel=dict(bgcolor="white", font_size=14)
    )
    
    # Links container
    header = dhtml.Div([
        dhtml.Span("S.No", style={"fontWeight": "bold", "width": "50px", "display": "inline-block"}),
        dhtml.Span("Defect Link", style={"fontWeight": "bold", "width": "150px", "display": "inline-block"}),
        dhtml.Span("Severity", style={"fontWeight": "bold", "width": "150px", "display": "inline-block", "marginLeft": "40px"}),
    ], style={"marginBottom": "10px", "fontFamily": "Courier New, monospace",
              "borderBottom": "2px solid #000", "paddingBottom": "5px"})
    details_container = dhtml.Div([header], style={"marginTop": "10px"})

    filtered = pd.DataFrame()
    
    if selected_state:
        filtered = df[df["State"]=="Active"] if selected_state=="Reopen" else df[df["State_Display"]==selected_state]
    elif selected_severity:
        filtered = df_open[df_open["Severity"]==selected_severity]

    if not filtered.empty:
        filtered = filtered.sort_values(by=["Assigned To","ID"], na_position="last")
        filtered["S.No"] = filtered.groupby("Assigned To").cumcount() + 1

        groups = []
        for i, (assigned_to, group) in enumerate(filtered.groupby("Assigned To")):
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
                dhtml.Summary(assigned_to if assigned_to else "Unassigned", 
                            style={"fontWeight":"bold","color":"#007ACC",
                                   "cursor":"pointer","fontSize":"16px","fontFamily":"Arial"}),
                dhtml.Div(defect_rows, style={"marginLeft":"20px","marginTop":"6px"})
            ], open=False, id={"type":"assigned-details","index":i})
            groups.append(details_section)

        details_container = dhtml.Div([header]+groups, style={"marginTop":"10px"})
    
    last_updated = f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return status_table, pie_fig, bar_state_fig, bar_severity_fig, details_container, last_updated, trigger_scroll

# Clientside callback for smooth scroll
app.clientside_callback(
    """
    function(scroll_trigger) {
        if (scroll_trigger > 0) {
            const element = document.getElementById('defects-section');
            if (element) {
                element.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
        return '';
    }
    """,
    Output('scroll-output', 'children'),
    Input('scroll-trigger', 'data')
)

# Run (only for local development)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)