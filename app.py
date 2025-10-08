import os
import pandas as pd
from io import StringIO
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html as dhtml, Input, Output, callback_context, State
from datetime import datetime
import subprocess
import threading
import time
import glob

# Paths and data
current_dir = os.path.dirname(os.path.abspath(__file__))
data_folder = os.path.join(current_dir, "data")

# Define your projects
PROJECTS = {
    "Smart FM (DevOps)": "Smart FM Defects through Python.xlsx",
    "Jira Project 1": "Jira PROJ Defects.xlsx",
    # Add more projects here as needed
    # "Jira Project 2": "Jira PROJ2 Defects.xlsx",
}

def load_data(project_name):
    """Load data from Excel file for a specific project"""
    excel_file = os.path.join(data_folder, PROJECTS.get(project_name))
    
    if not os.path.exists(excel_file):
        print(f"Warning: Excel file not found at {excel_file}")
        return pd.DataFrame(columns=["State", "ID", "Issue Links", "Severity", "Assigned To"])
    
    df = pd.read_excel(excel_file)
    
    # Handle different column structures (DevOps vs Jira)
    # Jira files have "Original Jira State" column, DevOps doesn't
    if "Original Jira State" in df.columns:
        # This is a Jira file - State column already has mapped values
        # We'll use State_Display = State for consistency
        df["State_Display"] = df["State"]
    else:
        # This is a DevOps file - need to map states
        state_mapping = {
            "Active": "Reopen",
            "New": "New",
            "Closed": "Closed",
            "Resolved": "Resolved",
        }
        df["State_Display"] = df["State"].map(state_mapping).fillna(df["State"])
    
    required_cols = ["State", "ID", "Issue Links", "Severity", "Assigned To"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = "N/A"
    
    # Clean and standardize the Severity column
    df["Severity"] = df["Severity"].astype(str).str.replace(r"^\d+\s*-\s*", "", regex=True).str.strip()
    
    # Map severity levels
    severity_map = {
        "Suggestion": "Suggestion",
        "Low": "Low",
        "Medium": "Medium",
        "High": "High",
        "Critical": "Critical"
    }
    df["Severity"] = df["Severity"].map(severity_map).fillna("Unknown")
    
    return df

def load_all_projects():
    """Load data from all projects and combine"""
    all_data = []
    for project_name in PROJECTS.keys():
        df = load_data(project_name)
        df["Project"] = project_name
        all_data.append(df)
    
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        return combined_df
    return pd.DataFrame()

def refresh_data_from_sources():
    """Run extraction scripts for all data sources"""
    try:
        print(f"🔄 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Refreshing data from all sources...")
        
        # Run DevOps extraction
        devops_script = os.path.join(current_dir, "defectsextraction.py")
        if os.path.exists(devops_script):
            print("  📥 Extracting from Azure DevOps...")
            subprocess.run(["python", devops_script], check=True)
        
        # Run Jira extraction
        jira_script = os.path.join(current_dir, "jiraextraction.py")
        if os.path.exists(jira_script):
            print("  📥 Extracting from Jira...")
            subprocess.run(["python", jira_script], check=True)
        
        print(f"✅ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Data refresh completed")
    except Exception as e:
        print(f"❌ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error refreshing data: {str(e)}")

def schedule_data_refresh():
    """Background thread to refresh data every 5 minutes"""
    while True:
        time.sleep(300)  # 5 minutes
        refresh_data_from_sources()

# Start background refresh thread
refresh_thread = threading.Thread(target=schedule_data_refresh, daemon=True)
refresh_thread.start()

# Define colors
state_colors = {"New": "#dc3545", "Reopen": "#7d1e2b", "Closed": "#28a745", "Resolved": "#fd7e14"}
severity_order = ["Critical", "High", "Medium", "Low", "Suggestion"]

# App
app = Dash(__name__)
server = app.server
app.title = "Multi-Project Defects Dashboard"

# Layout
app.layout = dhtml.Div([
    dcc.Interval(
        id='interval-component',
        interval=300*1000,  # Refresh every 5 minutes
        n_intervals=0
    ),
    dcc.Store(id='data-store'),
    dcc.Store(id='scroll-trigger', data=0),
    
    dhtml.Div([
        dhtml.H1("Multi-Project Defects Dashboard", 
                style={"textAlign": "center", "color": "#2c3e50", "marginBottom": "10px",
                       "fontFamily": "Arial, sans-serif", "fontWeight": "bold"}),
        dhtml.Div(id="last-updated", style={"textAlign": "center", "color": "#7f8c8d", 
                                            "fontSize": "14px", "marginBottom": "20px"})
    ]),
    
    # Project Selector
    dhtml.Div([
        dhtml.Label("Select Project:", style={"fontWeight": "bold", "marginRight": "10px", 
                                               "fontSize": "16px", "color": "#2c3e50"}),
        dcc.Dropdown(
            id='project-selector',
            options=[{'label': 'All Projects (Combined)', 'value': 'ALL'}] + 
                    [{'label': name, 'value': name} for name in PROJECTS.keys()],
            value='ALL',
            style={"width": "400px", "display": "inline-block"}
        )
    ], style={"textAlign": "center", "marginBottom": "30px"}),

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
    
    dhtml.Div(id='scroll-output', style={'display': 'none'})
], style={"backgroundColor": "#f8f9fa", "minHeight": "100vh", "padding": "20px 0"})

# Callback to load data
@app.callback(
    Output('data-store', 'data'),
    [Input('interval-component', 'n_intervals'),
     Input('project-selector', 'value')]
)
def update_data_store(n, selected_project):
    if selected_project == 'ALL':
        df = load_all_projects()
    else:
        df = load_data(selected_project)
        df["Project"] = selected_project
    
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
    
    # FIXED: Use StringIO to wrap JSON string
    df = pd.read_json(StringIO(json_data), orient='split')
    
    if df.empty:
        return None, {}, {}, {}, None, "", scroll_count
    
    # Filter for open defects (exclude Closed and Resolved)
    df_open = df[~df["State_Display"].str.lower().isin(["closed", "resolved"])]
    
    # Aggregate counts
    severity_counts = df_open["Severity"].value_counts().reindex(severity_order, fill_value=0).reset_index()
    severity_counts.columns = ["Severity", "Count"]
    
    state_counts_df = df["State_Display"].value_counts().reset_index()
    state_counts_df.columns = ["State_Display", "Count"]
    
    # Calculate metrics
    total_defects = len(df)
    new_count = int(state_counts_df.loc[state_counts_df["State_Display"]=="New", "Count"].sum()) if "New" in state_counts_df["State_Display"].values else 0
    reopen_count = int(state_counts_df.loc[state_counts_df["State_Display"]=="Reopen", "Count"].sum()) if "Reopen" in state_counts_df["State_Display"].values else 0
    closed_count = int(state_counts_df.loc[state_counts_df["State_Display"]=="Closed", "Count"].sum()) if "Closed" in state_counts_df["State_Display"].values else 0
    resolved_count = int(state_counts_df.loc[state_counts_df["State_Display"]=="Resolved", "Count"].sum()) if "Resolved" in state_counts_df["State_Display"].values else 0
    
    # Status Table
    status_table = dhtml.Div([
        dhtml.Div([
            dhtml.Div([
                dhtml.Div(str(total_defects), style={"fontSize": "36px", "fontWeight": "bold", "color": "#2c3e50"}),
                dhtml.Div("Total Defects", style={"fontSize": "14px", "color": "#7f8c8d"})
            ], style={"textAlign": "center", "padding": "20px", "backgroundColor": "#e9ecef", 
                     "borderRadius": "10px", "margin": "10px", "flex": "1"}),
            
            dhtml.Div([
                dhtml.Div(str(new_count), style={"fontSize": "36px", "fontWeight": "bold", "color": "#dc3545"}),
                dhtml.Div("New", style={"fontSize": "14px", "color": "#7f8c8d"})
            ], style={"textAlign": "center", "padding": "20px", "backgroundColor": "#f8d7da", 
                     "borderRadius": "10px", "margin": "10px", "flex": "1"}),
            
            dhtml.Div([
                dhtml.Div(str(reopen_count), style={"fontSize": "36px", "fontWeight": "bold", "color": "#7d1e2b"}),
                dhtml.Div("Reopen", style={"fontSize": "14px", "color": "#7f8c8d"})
            ], style={"textAlign": "center", "padding": "20px", "backgroundColor": "#f5c6cb", 
                     "borderRadius": "10px", "margin": "10px", "flex": "1"}),
            
            dhtml.Div([
                dhtml.Div(str(closed_count), style={"fontSize": "36px", "fontWeight": "bold", "color": "#28a745"}),
                dhtml.Div("Closed", style={"fontSize": "14px", "color": "#7f8c8d"})
            ], style={"textAlign": "center", "padding": "20px", "backgroundColor": "#d4edda", 
                     "borderRadius": "10px", "margin": "10px", "flex": "1"}),
            
            dhtml.Div([
                dhtml.Div(str(resolved_count), style={"fontSize": "36px", "fontWeight": "bold", "color": "#fd7e14"}),
                dhtml.Div("Resolved", style={"fontSize": "14px", "color": "#7f8c8d"})
            ], style={"textAlign": "center", "padding": "20px", "backgroundColor": "#ffe5d0", 
                     "borderRadius": "10px", "margin": "10px", "flex": "1"}),
        ], style={"display": "flex", "flexDirection": "row", "justifyContent": "space-around", 
                 "flexWrap": "wrap", "padding": "0 20px"})
    ])
    
    # Pie Chart (Severity Distribution)
    fig_pie = px.pie(severity_counts, names="Severity", values="Count", title="Open Defects by Severity",
                     color_discrete_sequence=px.colors.sequential.RdBu)
    fig_pie.update_traces(textposition='inside', textinfo='percent+label+value', hovertemplate='%{label}: %{value}<extra></extra>')
    fig_pie.update_layout(margin=dict(l=20, r=20, t=40, b=20), showlegend=True)
    
    # Bar Chart (State Distribution)
    fig_bar_state = px.bar(state_counts_df, x="State_Display", y="Count", title="Defects by State",
                          color="State_Display", color_discrete_map=state_colors)
    fig_bar_state.update_traces(hovertemplate='%{x}: %{y}<extra></extra>')
    fig_bar_state.update_layout(xaxis_title="", yaxis_title="Count", showlegend=False,
                               margin=dict(l=20, r=20, t=40, b=20))
    
    # Bar Chart (Severity Distribution)
    fig_bar_severity = px.bar(severity_counts, x="Severity", y="Count", title="Open Defects by Severity",
                             color="Severity", color_discrete_sequence=px.colors.sequential.Reds_r)
    fig_bar_severity.update_traces(hovertemplate='%{x}: %{y}<extra></extra>')
    fig_bar_severity.update_layout(xaxis_title="", yaxis_title="Count", showlegend=False,
                                  margin=dict(l=20, r=20, t=40, b=20))
    
    # Determine filter based on clicks
    filtered_df = df_open.copy()
    filter_applied = False
    new_scroll_count = scroll_count
    
    ctx = callback_context
    if ctx.triggered:
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        if trigger_id == 'pie-chart' and pie_click:
            severity_clicked = pie_click['points'][0]['label']
            filtered_df = filtered_df[filtered_df["Severity"] == severity_clicked]
            filter_applied = True
            new_scroll_count += 1
        
        elif trigger_id == 'bar-chart-state' and bar_state_click:
            state_clicked = bar_state_click['points'][0]['x']
            filtered_df = df[df["State_Display"] == state_clicked]
            filter_applied = True
            new_scroll_count += 1
        
        elif trigger_id == 'bar-chart-severity' and bar_severity_click:
            severity_clicked = bar_severity_click['points'][0]['x']
            filtered_df = filtered_df[filtered_df["Severity"] == severity_clicked]
            filter_applied = True
            new_scroll_count += 1
    
    # Generate links
    links_list = []
    for _, row in filtered_df.iterrows():
        state_style = {
            "New": {"backgroundColor": "#dc3545", "color": "white"},
            "Reopen": {"backgroundColor": "#7d1e2b", "color": "white"},
            "Closed": {"backgroundColor": "#28a745", "color": "white"},
            "Resolved": {"backgroundColor": "#fd7e14", "color": "white"}
        }.get(row.get("State_Display", ""), {"backgroundColor": "#6c757d", "color": "white"})
        
        severity_style = {
            "Critical": {"backgroundColor": "#8b0000", "color": "white"},
            "High": {"backgroundColor": "#dc3545", "color": "white"},
            "Medium": {"backgroundColor": "#ffc107", "color": "black"},
            "Low": {"backgroundColor": "#28a745", "color": "white"},
            "Suggestion": {"backgroundColor": "#17a2b8", "color": "white"}
        }.get(row.get("Severity", ""), {"backgroundColor": "#6c757d", "color": "white"})
        
        project_name = row.get("Project", "Unknown")
        
        link_item = dhtml.Div([
            dhtml.Span(f"[{project_name}] ", style={"fontWeight": "bold", "color": "#6c757d", "marginRight": "10px"}),
            dhtml.Span(f"{row.get('ID', 'N/A')}", style={"fontWeight": "bold", "marginRight": "10px", "color": "#2c3e50"}),
            dhtml.Span(row.get("State_Display", "N/A"), style={
                "padding": "3px 8px", "borderRadius": "4px", "marginRight": "10px",
                "fontSize": "12px", "fontWeight": "bold", **state_style
            }),
            dhtml.Span(row.get("Severity", "N/A"), style={
                "padding": "3px 8px", "borderRadius": "4px", "marginRight": "10px",
                "fontSize": "12px", "fontWeight": "bold", **severity_style
            }),
            dhtml.Span(f"Assigned: {row.get('Assigned To', 'Unassigned')}", 
                      style={"marginRight": "10px", "color": "#495057", "fontSize": "14px"}),
            dhtml.A("🔗 View", href=row.get("Issue Links", "#"), target="_blank",
                   style={"color": "#007bff", "textDecoration": "none", "fontWeight": "bold"})
        ], style={"padding": "10px", "marginBottom": "10px", "backgroundColor": "white",
                 "borderRadius": "5px", "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
                 "display": "flex", "alignItems": "center", "flexWrap": "wrap"})
        
        links_list.append(link_item)
    
    links_container = dhtml.Div(links_list if links_list else [
        dhtml.Div("No defects found matching the filter.", 
                 style={"textAlign": "center", "padding": "20px", "color": "#7f8c8d"})
    ])
    
    last_updated = f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return status_table, fig_pie, fig_bar_state, fig_bar_severity, links_container, last_updated, new_scroll_count

# Clientside callback for scroll
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)