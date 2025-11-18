import os
import pandas as pd
from io import StringIO
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html as dhtml, Input, Output, callback_context, State, clientside_callback
import dash
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
    "Smart FM Replacement (DevOps)": "Smart FM Defects through Python.xlsx",
    "Timesheet (Jira)": "Jira techcarrot Time Sheet Defects.xlsx",
    "Emirates Transport Career Page(Jira)": "Jira Emirates Transport Defects.xlsx",
    "Dr. RAM Ji Website Req V2 (Jira)": "Jira Doctor_Ramji_Website Defects.xlsx",
    "Al-Futtaim Group Intranet (Jira)": "Jira Al-Futtaim Group Defects.xlsx",
}

# Filter configurations for Smart FM project - FIXED: Added "Security" tag
SMART_FM_TAGS = ["Move In", "Move Out", "Master Data Setup", "Account Renewal", "Active Resident", "Security"]
SMART_FM_ENVIRONMENTS = ["SIT", "UAT"]

def load_data(project_name):
    """Load data from Excel file for a specific project"""
    excel_file = os.path.join(data_folder, PROJECTS.get(project_name))
    
    if not os.path.exists(excel_file):
        print(f"Warning: Excel file not found at {excel_file}")
        if os.path.exists(data_folder):
            available_files = os.listdir(data_folder)
            print(f"Available files in data folder: {available_files}")
        return pd.DataFrame(columns=["State", "ID", "Issue Links", "Severity", "Assigned To", "Title", "Tags", "Environment"])
    
    df = pd.read_excel(excel_file)
    
    # Handle different column structures (DevOps vs Jira)
    if "Original Jira State" in df.columns:
        df["State_Display"] = df["State"]
    else:
        state_mapping = {
            "Active": "Reopen",
            "New": "New",
            "Closed": "Closed",
            "Resolved": "Resolved",
        }
        df["State_Display"] = df["State"].map(state_mapping).fillna(df["State"])
    
    required_cols = ["State", "ID", "Issue Links", "Severity", "Assigned To", "Title", "Tags", "Environment"]
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
    
    print(f"Loaded {len(df)} records from {project_name}")
    return df

def refresh_data_from_sources():
    """Run extraction scripts for all data sources"""
    try:
        print(f"🔄 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Refreshing data from all sources...")
        
        devops_script = os.path.join(current_dir, "defectsextraction.py")
        if os.path.exists(devops_script):
            print("  🔥 Extracting from Azure DevOps...")
            result = subprocess.run(["python", devops_script], 
                                  capture_output=True, 
                                  text=True, 
                                  check=True)
            if result.returncode != 0:
                print(f"  ⚠️ DevOps extraction warning: {result.stderr}")
        
        jira_script = os.path.join(current_dir, "jiraextraction.py")
        if os.path.exists(jira_script):
            print("  🔥 Extracting from Jira...")
            result = subprocess.run(["python", jira_script], 
                                  capture_output=True, 
                                  text=True, 
                                  check=True)
            if result.returncode != 0:
                print(f"  ⚠️ Jira extraction warning: {result.stderr}")
        
        print(f"✅ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Data refresh completed")
    except subprocess.CalledProcessError as e:
        print(f"❌ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Extraction script failed:")
        print(f"   STDOUT: {e.stdout}")
        print(f"   STDERR: {e.stderr}")
    except Exception as e:
        print(f"❌ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error refreshing data: {str(e)}")

def schedule_data_refresh():
    """Background thread to refresh data every 2 minutes"""
    while True:
        time.sleep(120)
        refresh_data_from_sources()

# Start background refresh thread
refresh_thread = threading.Thread(target=schedule_data_refresh, daemon=True)
refresh_thread.start()

# Define colors
state_colors = {"New": "#E53935", "Reopen": "#C62828", "Closed": "#4CAF50", "Resolved": "#FF9800"}
severity_colors = {
    "Critical": "#E53935",
    "High": "#FF7043",
    "Medium": "#FFB300",
    "Low": "#42A5F5",
    "Suggestion": "#81C784"
}
severity_order = ["Critical", "High", "Medium", "Low", "Suggestion"]

# App
app = Dash(__name__, suppress_callback_exceptions=True)
server = app.server
app.title = "Projects Defects Dashboard"

# Layout
app.layout = dhtml.Div([
    dcc.Interval(
        id='interval-component',
        interval=120*1000,
        n_intervals=0
    ),
    dcc.Store(id='data-store'),
    dcc.Store(id='scroll-trigger', data=0),
    dcc.Store(id='collapse-trigger', data=0),
    dcc.Store(id='filter-state', data=None),
    dhtml.Div([
        dhtml.H1("Projects Defects Dashboard", 
                style={"textAlign": "center", "color": "#1C2833", "marginBottom": "10px",
                       "fontFamily": "Segoe UI, Arial, sans-serif", "fontWeight": "600"}),
        dhtml.Div(id="last-updated", style={"textAlign": "center", "color": "#708090", 
                                            "fontSize": "13px", "marginBottom": "20px"})
        dhtml.Div(id='refresh-status', style={"display": "inline-block"})
    ]),
    
    # Project Selector
    dhtml.Div([
        dhtml.Div("Select Project:", style={"fontWeight": "bold", "marginRight": "10px", 
                                               "fontSize": "15px", "color": "#1C2833"}),
        dcc.Dropdown(
            id='project-selector',
            options=[{'label': name, 'value': name} for name in PROJECTS.keys()],
            value=list(PROJECTS.keys())[0],
            style={"width": "350px", "boxShadow": "0 1px 3px rgba(0,0,0,0.1)"}
        )
    ], style={
        "textAlign": "center", 
        "marginBottom": "20px",
        "display": "flex", 
        "justifyContent": "center",
        "alignItems": "center"
    }),
    @app.callback(
    Output('data-store', 'data'),
    [Input('interval-component', 'n_intervals'),
     Input('project-selector', 'value')]
)
def update_data_store(n, selected_project):
    ctx = callback_context
    
    # If project changed, refresh the data first
    if ctx.triggered and ctx.triggered[0]['prop_id'] == 'project-selector.value':
        print(f"🔄 Project changed to '{selected_project}', refreshing extraction scripts...")
        refresh_data_from_sources()
    
    df = load_data(selected_project)
    return df.to_json(date_format='iso', orient='split')

    # In app.layout, ADD after the project selector:
dhtml.Div([
    dhtml.Button(
        "🔄 Refresh Data Now",
        id="refresh-button",
        n_clicks=0,
        style={
            "padding": "8px 16px",
            "backgroundColor": "#1976D2",
            "color": "white",
            "border": "none",
            "borderRadius": "4px",
            "cursor": "pointer",
            "fontWeight": "bold",
            "fontSize": "13px",
            "marginLeft": "20px"
        }
    )
], style={
    "display": "flex",
    "justifyContent": "center",
    "alignItems": "center",
    "marginBottom": "20px"
})

@app.callback(
    Output('refresh-status', 'children'),
    Input('refresh-button', 'n_clicks'),
    prevent_initial_call=True
)
def manual_refresh(n_clicks):
    """Manually refresh data on button click"""
    print(f"🔘 Manual refresh triggered (click #{n_clicks})")
    refresh_data_from_sources()
    return dhtml.Div("✅ Data refreshed!", style={"color": "green", "fontSize": "12px", "marginLeft": "20px"})

    # Smart FM Filters (conditionally displayed)
    dhtml.Div(id='smart-fm-filters', children=[
        dhtml.Div([
            # Tag Filter
            dhtml.Div([
                dhtml.Label("Filter by Tag:", style={"fontWeight": "bold", "marginRight": "10px", 
                                                      "fontSize": "14px", "color": "#1C2833"}),
                dcc.Dropdown(
                    id='tag-filter',
                    options=[{'label': 'All Tags', 'value': 'all'}] + 
                            [{'label': tag, 'value': tag} for tag in SMART_FM_TAGS],
                    value='all',
                    clearable=False,
                    style={"width": "250px", "boxShadow": "0 1px 3px rgba(0,0,0,0.1)"}
                )
            ], style={"display": "flex", "alignItems": "center", "marginRight": "20px"}),
            
            # Environment Filter
            dhtml.Div([
                dhtml.Label("Environment:", style={"fontWeight": "bold", "marginRight": "10px", 
                                                    "fontSize": "14px", "color": "#1C2833"}),
                dcc.Dropdown(
                    id='environment-filter',
                    options=[{'label': 'All Environments', 'value': 'all'}] + 
                            [{'label': env, 'value': env} for env in SMART_FM_ENVIRONMENTS],
                    value='all',
                    clearable=False,
                    style={"width": "200px", "boxShadow": "0 1px 3px rgba(0,0,0,0.1)"}
                )
            ], style={"display": "flex", "alignItems": "center"}),
        ], style={
            "display": "flex",
            "justifyContent": "center",
            "alignItems": "center",
            "marginBottom": "20px",
            "padding": "15px",
            "backgroundColor": "#ffffff",
            "borderRadius": "8px",
            "boxShadow": "0 2px 4px rgba(0,0,0,0.1)"
        })
    ], style={"display": "none"}),

    dhtml.Div(id="status-table"),

    # Charts section
    dhtml.Div([
        dcc.Graph(id="pie-chart", style={"width": "32%", "height": "350px", "margin": "0.5%"}, config={'displayModeBar': False}),
        dcc.Graph(id="bar-chart-state", style={"width": "32%", "height": "350px", "margin": "0.5%"}, config={'displayModeBar': False}),
        dcc.Graph(id="bar-chart-severity", style={"width": "32%", "height": "350px", "margin": "0.5%"}, config={'displayModeBar': False})
    ], style={"display": "flex", "flexDirection": "row", "justifyContent": "space-around",
              "alignItems": "flex-start", "flexWrap": "nowrap", "marginBottom": "30px",
              "padding": "0 10px"}),

    dhtml.H2("🔗 Defects with Details", 
            id="defects-section",
            style={"marginTop": "30px", "marginLeft": "20px", "color": "#1C2833",
                   "fontFamily": "Segoe UI, Arial, sans-serif", "fontWeight": "600"}),
    dhtml.Div(id="links-container", style={"marginTop": "20px", "padding": "0 20px", "maxWidth": "100%", "boxSizing": "border-box"}),
    
    # Hidden components for callbacks
    dhtml.Div(id='scroll-output', style={'display': 'none'}),
], style={"backgroundColor": "#f4f6f9", "minHeight": "100vh", "padding": "20px 0"})

@app.callback(
    Output('data-store', 'data'),
    [Input('interval-component', 'n_intervals'),
     Input('project-selector', 'value')]
)
def update_data_store(n, selected_project):
    df = load_data(selected_project)
    return df.to_json(date_format='iso', orient='split')

@app.callback(
    Output('smart-fm-filters', 'style'),
    [Input('project-selector', 'value')]
)
def toggle_smart_fm_filters(selected_project):
    """Show filters only for Smart FM project"""
    if selected_project == "Smart FM Replacement (DevOps)":
        return {"display": "block"}
    else:
        return {"display": "none"}

@app.callback(
    [Output("status-table", "children"),
     Output("pie-chart", "figure"),
     Output("bar-chart-state", "figure"),
     Output("bar-chart-severity", "figure"),
     Output("links-container", "children"),
     Output("last-updated", "children"),
     Output("scroll-trigger", "data"),
     Output("collapse-trigger", "data"),
     Output("filter-state", "data")],
    [Input('data-store', 'data'),
     Input("pie-chart", "clickData"),
     Input("bar-chart-state", "clickData"),
     Input("bar-chart-severity", "clickData"),
     Input('tag-filter', 'value'),
     Input('environment-filter', 'value'),
     Input('project-selector', 'value')],
    [State("scroll-trigger", "data"),
     State("collapse-trigger", "data"),
     State("filter-state", "data")]
)
def update_all(json_data, pie_click, bar_state_click, bar_severity_click, tag_filter, env_filter, selected_project, scroll_count, collapse_count, filter_state):
    if not json_data:
        return None, {}, {}, {}, None, "", scroll_count, collapse_count, None
    
    df = pd.read_json(StringIO(json_data), orient='split')
    
    if df.empty:
        return None, {}, {}, {}, None, "", scroll_count, collapse_count, None
    
    # === Apply Tag and Environment Filters for Smart FM ===
    if selected_project == "Smart FM Replacement (DevOps)":
        print(f"\n🔍 FILTER DEBUG - Smart FM Project Selected")
        print(f"   Tag Filter: {tag_filter}")
        print(f"   Environment Filter: {env_filter}")
        print(f"   Total records before filtering: {len(df)}")
        
        # Filter by Tag
        if tag_filter and tag_filter != 'all':
            if 'Tags' in df.columns:
                before_count = len(df)
                df = df[df['Tags'].fillna('').str.contains(tag_filter, case=False, na=False, regex=False)]
                print(f"   After Tag filter: {len(df)} records (removed {before_count - len(df)})")
        
        # FIXED: Filter by Environment - use exact match instead of contains
        if env_filter and env_filter != 'all':
            if 'Environment' in df.columns:
                before_count = len(df)
                
                # Debug: Show unique environment values
                unique_envs = df['Environment'].fillna('').unique()
                print(f"   Unique Environment values in data: {unique_envs}")
                
                # Debug: Show sample of environment values
                sample_envs = df['Environment'].fillna('').head(10).tolist()
                print(f"   Sample Environment values: {sample_envs}")
                
                # Apply filter
                df = df[df['Environment'].fillna('').str.strip().str.upper() == env_filter.upper()]
                print(f"   After Environment filter ({env_filter}): {len(df)} records (removed {before_count - len(df)})")
            else:
                print(f"   ⚠️ WARNING: 'Environment' column not found in dataframe!")
                print(f"   Available columns: {df.columns.tolist()}")
    
    # Filter for open defects
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
                dhtml.Div(str(total_defects), style={"fontSize": "24px", "fontWeight": "bold", "color": "#1C2833"}),
                dhtml.Div("Total Defects", style={"fontSize": "11px", "color": "#708090"})
            ], style={"textAlign": "center", "padding": "10px", "backgroundColor": "#EBF0F7",
                     "borderRadius": "6px", "margin": "6px", "flex": "1", "minWidth": "100px",
                     "boxShadow": "0 2px 4px rgba(0,0,0,0.05)"}),
            
            dhtml.Div([
                dhtml.Div(str(new_count), style={"fontSize": "24px", "fontWeight": "bold", "color": state_colors['New']}),
                dhtml.Div("New", style={"fontSize": "11px", "color": "#708090"})
            ], style={"textAlign": "center", "padding": "10px", "backgroundColor": "#FFEBEB",
                     "borderRadius": "6px", "margin": "6px", "flex": "1", "minWidth": "100px",
                     "boxShadow": "0 2px 4px rgba(0,0,0,0.05)"}),
            
            dhtml.Div([
                dhtml.Div(str(reopen_count), style={"fontSize": "24px", "fontWeight": "bold", "color": state_colors['Reopen']}),
                dhtml.Div("Reopen", style={"fontSize": "11px", "color": "#708090"})
            ], style={"textAlign": "center", "padding": "10px", "backgroundColor": "#FEE4E4",
                     "borderRadius": "6px", "margin": "6px", "flex": "1", "minWidth": "100px",
                     "boxShadow": "0 2px 4px rgba(0,0,0,0.05)"}),
            
            dhtml.Div([
                dhtml.Div(str(closed_count), style={"fontSize": "24px", "fontWeight": "bold", "color": state_colors['Closed']}),
                dhtml.Div("Closed", style={"fontSize": "11px", "color": "#708090"})
            ], style={"textAlign": "center", "padding": "10px", "backgroundColor": "#E8F5E9",
                     "borderRadius": "6px", "margin": "6px", "flex": "1", "minWidth": "100px",
                     "boxShadow": "0 2px 4px rgba(0,0,0,0.05)"}),
            
            dhtml.Div([
                dhtml.Div(str(resolved_count), style={"fontSize": "24px", "fontWeight": "bold", "color": state_colors['Resolved']}),
                dhtml.Div("Resolved", style={"fontSize": "11px", "color": "#708090"})
            ], style={"textAlign": "center", "padding": "10px", "backgroundColor": "#FFF8E1",
                     "borderRadius": "6px", "margin": "6px", "flex": "1", "minWidth": "100px",
                     "boxShadow": "0 2px 4px rgba(0,0,0,0.05)"}),
        ], style={"display": "flex", "flexDirection": "row", "justifyContent": "center", 
                 "flexWrap": "wrap", "padding": "0 20px"})
    ])
    
    # Pie Chart
    if severity_counts["Count"].sum() == 0:
        fig_pie = go.Figure()
        fig_pie.add_annotation(
            text="🎉<br>No Open Defects!",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20, color="#4CAF50", family="Segoe UI"),
            align="center"
        )
        fig_pie.update_layout(
            title="Open Defects by Severity",
            title_font_size=16,
            margin=dict(l=10, r=10, t=40, b=10),
            showlegend=False,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
    else:
        pie_colors = [severity_colors.get(sev, "#6c757d") for sev in severity_counts["Severity"]]
        fig_pie = go.Figure(data=[go.Pie(
            labels=severity_counts["Severity"],
            values=severity_counts["Count"],
            marker=dict(colors=pie_colors),
            textposition='inside',
            textinfo='percent+label+value',
            hovertemplate='%{label}: %{value}<extra></extra>'
        )])
        fig_pie.update_layout(
            title="Open Defects by Severity",
            title_font_size=16,
            margin=dict(l=10, r=10, t=40, b=10),
            showlegend=True,
            legend=dict(font=dict(size=10))
        )
    
    # Bar Chart (State Distribution)
    fig_bar_state = px.bar(state_counts_df, x="State_Display", y="Count", title="Defects by State",
                          color="State_Display", color_discrete_map=state_colors)
    fig_bar_state.update_traces(hovertemplate='%{x}: %{y}<extra></extra>')
    fig_bar_state.update_layout(xaxis_title="", yaxis_title="Count", showlegend=False,
                               title_font_size=16,
                               margin=dict(l=10, r=10, t=40, b=10))
    
    # Bar Chart (Severity Distribution)
    if severity_counts["Count"].sum() == 0:
        fig_bar_severity = go.Figure()
        fig_bar_severity.add_annotation(
            text="🎉<br>Congratulations!<br>No Open Defects Found",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="#4CAF50", family="Segoe UI"),
            align="center"
        )
        fig_bar_severity.update_layout(
            title="Open Defects by Severity",
            title_font_size=16,
            xaxis_title="",
            yaxis_title="Count",
            showlegend=False,
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
    else:
        bar_colors = [severity_colors.get(sev, "#6c757d") for sev in severity_counts["Severity"]]
        fig_bar_severity = go.Figure(data=[go.Bar(
            x=severity_counts["Severity"],
            y=severity_counts["Count"],
            marker=dict(color=bar_colors),
            hovertemplate='%{x}: %{y}<extra></extra>'
        )])
        fig_bar_severity.update_layout(
            title="Open Defects by Severity",
            title_font_size=16,
            xaxis_title="",
            yaxis_title="Count",
            showlegend=False,
            margin=dict(l=10, r=10, t=40, b=10)
        )
    
    # Determine filter based on clicks OR preserved state
    filtered_df = df_open.copy()
    new_scroll_count = scroll_count
    new_collapse_count = collapse_count
    new_filter_state = filter_state
    
    ctx = callback_context
    if ctx.triggered:
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        # Check if a chart was clicked
        if trigger_id in ['pie-chart', 'bar-chart-state', 'bar-chart-severity'] and ctx.triggered[0]['value']:
            new_scroll_count += 1
            new_collapse_count += 1
            
            if trigger_id == 'pie-chart':
                severity_clicked = pie_click['points'][0]['label']
                filtered_df = filtered_df[filtered_df["Severity"] == severity_clicked]
                new_filter_state = {'type': 'severity', 'value': severity_clicked}
            
            elif trigger_id == 'bar-chart-state':
                state_clicked = bar_state_click['points'][0]['x']
                filtered_df = df[df["State_Display"] == state_clicked]
                new_filter_state = {'type': 'state', 'value': state_clicked}
                
            elif trigger_id == 'bar-chart-severity':
                severity_clicked = bar_severity_click['points'][0]['x']
                filtered_df = filtered_df[filtered_df["Severity"] == severity_clicked]
                new_filter_state = {'type': 'severity', 'value': severity_clicked}
        
        # If data refreshed but filter exists, re-apply it
        elif trigger_id == 'data-store' and filter_state:
            if filter_state['type'] == 'severity':
                filtered_df = filtered_df[filtered_df["Severity"] == filter_state['value']]
            elif filter_state['type'] == 'state':
                filtered_df = df[df["State_Display"] == filter_state['value']]
    
    # Generate links grouped by assignee
    if filtered_df.empty:
        links_container = dhtml.Div([
            dhtml.Div([
                dhtml.Div("🎉", style={"fontSize": "80px", "marginBottom": "20px"}),
                dhtml.H3("All Defects Are Resolved!", 
                        style={"color": "#4CAF50", "marginBottom": "10px", "fontWeight": "bold"}),
                dhtml.P("Great job! There are no open defects at the moment.", 
                       style={"color": "#708090", "fontSize": "14px", "marginBottom": "20px"}),
                dhtml.Div([
                    dhtml.Div([
                        dhtml.Div(str(closed_count), style={"fontSize": "30px", "fontWeight": "bold", "color": state_colors['Closed']}),
                        dhtml.Div("Closed", style={"fontSize": "12px", "color": "#708090"})
                    ], style={"display": "inline-block", "margin": "0 15px", "padding": "10px"}),
                    dhtml.Div([
                        dhtml.Div(str(resolved_count), style={"fontSize": "30px", "fontWeight": "bold", "color": state_colors['Resolved']}),
                        dhtml.Div("Resolved", style={"fontSize": "12px", "color": "#708090"})
                    ], style={"display": "inline-block", "margin": "0 15px", "padding": "10px"})
                ], style={"marginTop": "20px"})
            ], style={
                "textAlign": "center", "padding": "30px 20px", "backgroundColor": "white",
                "borderRadius": "8px", "boxShadow": "0 4px 10px rgba(0,0,0,0.05)",
                "margin": "20px auto", "maxWidth": "450px"
            })
        ])
    else:
        assignee_groups = filtered_df.groupby("Assigned To")
        assignee_sections = []
        
        for idx, (assignee, group_df) in enumerate(assignee_groups):
            assignee_display = assignee if assignee and assignee != "N/A" else "Unassigned"
            defect_count = len(group_df)
            assignee_id = f"assignee-section-{idx}"
            
            defect_items = []
            for _, row in group_df.iterrows():
                state_style = {
                    "New": {"backgroundColor": state_colors['New'], "color": "white"},
                    "Reopen": {"backgroundColor": state_colors['Reopen'], "color": "white"},
                    "Closed": {"backgroundColor": state_colors['Closed'], "color": "white"},
                    "Resolved": {"backgroundColor": state_colors['Resolved'], "color": "white"}
                }.get(row.get("State_Display", ""), {"backgroundColor": "#607D8B", "color": "white"})
                
                severity_style = {
                    "Critical": {"backgroundColor": severity_colors['Critical'], "color": "white"},
                    "High": {"backgroundColor": severity_colors['High'], "color": "white"},
                    "Medium": {"backgroundColor": severity_colors['Medium'], "color": "white"},
                    "Low": {"backgroundColor": severity_colors['Low'], "color": "white"},
                    "Suggestion": {"backgroundColor": severity_colors['Suggestion'], "color": "white"}
                }.get(row.get("Severity", ""), {"backgroundColor": "#607D8B", "color": "white"})
                
                defect_title = str(row.get("Title", ""))
                if not defect_title or defect_title == "N/A" or defect_title == "nan":
                    defect_title = "No summary available"
                
                defect_item = dhtml.Div([
                    dhtml.Div([
                        dhtml.Span(f"{row.get('ID', 'N/A')}", 
                                  style={"fontWeight": "600", "marginRight": "15px", "color": "#1C2833", "fontSize": "13px"}),
                        dhtml.Span(row.get("State_Display", "N/A"), style={
                            "padding": "3px 8px", "borderRadius": "3px", "marginRight": "10px",
                            "fontSize": "11px", "fontWeight": "bold", **state_style
                        }),
                        dhtml.Span(row.get("Severity", "N/A"), style={
                            "padding": "3px 8px", "borderRadius": "3px", "marginRight": "10px",
                            "fontSize": "11px", "fontWeight": "bold", **severity_style
                        }),
                        dhtml.A("🔗 View", href=row.get("Issue Links", "#"), target="_blank",
                               style={"color": "#1976D2", "textDecoration": "none", "fontWeight": "bold", 
                                     "fontSize": "12px"})
                    ], style={
                        "display": "flex",
                        "alignItems": "center",
                        "flexWrap": "wrap",
                        "marginBottom": "8px"
                    }),
                    dhtml.Div([
                        dhtml.Span("Summary: ", style={"fontWeight": "600", "color": "#546E7A", "fontSize": "12px"}),
                        dhtml.Span(defect_title, style={"color": "#607D8B", "fontSize": "12px", "lineHeight": "1.5"})
                    ], style={
                        "paddingLeft": "0px",
                        "borderTop": "1px solid #E0E0E0",
                        "paddingTop": "6px"
                    })
                ], style={
                    "padding": "10px 15px",
                    "marginBottom": "8px",
                    "backgroundColor": "#ffffff",
                    "borderRadius": "5px",
                    "border": "1px solid #CFD8DC",
                    "boxShadow": "0 1px 2px rgba(0,0,0,0.05)"
                })
                
                defect_items.append(defect_item)
            
            assignee_section = dhtml.Div([
                dhtml.Div([
                    dhtml.Span("▶", 
                              id=f"arrow-{assignee_id}",
                              style={"marginRight": "10px", "fontSize": "14px", "display": "inline-block", "width": "15px", "transition": "transform 0.2s ease"}),
                    dhtml.Span(f"{assignee_display}", 
                              style={
                                  "fontWeight": "bold", 
                                  "fontSize": "16px", 
                                  "color": "#1C2833",
                                  "flexShrink": 1,
                                  "minWidth": "0",
                                  "overflow": "hidden", 
                                  "textOverflow": "ellipsis", 
                                  "whiteSpace": "nowrap", 
                                  "marginRight": "10px"
                              }),
                    dhtml.Span(f"({defect_count})", 
                              style={"fontSize": "13px", "color": "#708090", "flexShrink": 0})
                ], 
                id=f"toggle-{assignee_id}",
                n_clicks=0,
                style={
                    "width": "calc(100% - 4px)",
                    "padding": "10px 15px",
                    "backgroundColor": "#ffffff",
                    "border": "1px solid #1976D2",
                    "borderRadius": "6px",
                    "cursor": "pointer",
                    "textAlign": "left",
                    "fontSize": "16px",
                    "marginBottom": "8px",
                    "boxShadow": "0 2px 5px rgba(0,0,0,0.1)",
                    "transition": "all 0.3s ease",
                    "display": "flex",
                    "alignItems": "center",
                    "boxSizing": "border-box"
                }),
                
                dhtml.Div(
                    defect_items,
                    id=f"content-{assignee_id}",
                    style={
                        "display": "none",
                        "padding": "5px 0",
                        "marginBottom": "10px"
                    }
                )
            ], id=assignee_id, style={"marginBottom": "8px", "maxWidth": "100%", "boxSizing": "border-box"})
            
            assignee_sections.append(assignee_section)
        
        links_container = dhtml.Div(assignee_sections, style={"maxWidth": "100%", "overflow": "hidden"})
    
    last_updated = f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return status_table, fig_pie, fig_bar_state, fig_bar_severity, links_container, last_updated, new_scroll_count, new_collapse_count, new_filter_state

# Clientside Callbacks for UI/UX
clientside_callback(
    """
    function(n_clicks) {
        const toggleId = dash_clientside.callback_context.triggered[0].prop_id.split('.')[0];
        
        if (toggleId && toggleId.startsWith('toggle-assignee-section-')) {
            const sectionId = toggleId.replace('toggle-', '');
            const content = document.getElementById('content-' + sectionId);
            const arrow = document.getElementById('arrow-' + sectionId);
            const toggleElement = document.getElementById(toggleId);

            if (content && arrow && toggleElement) {
                const isCollapsed = content.style.display === 'none' || content.style.display === '';
                content.style.display = isCollapsed ? 'block' : 'none';
                arrow.textContent = isCollapsed ? '▼' : '▶';
                toggleElement.style.borderColor = isCollapsed ? '#007bff' : '#1976D2';
            }
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output('scroll-output', 'children'),
    [Input({'type': 'toggle', 'index': dash.ALL}, 'n_clicks')],
    prevent_initial_call=True
)

clientside_callback(
    """
    function(data_store_data, collapse_trigger) {
        if (!data_store_data) {
            return '';
        }
        
        function collapseAllSections() {
            const toggleButtons = document.querySelectorAll('[id^="toggle-assignee-section-"]');
            toggleButtons.forEach(toggleElement => {
                const sectionId = toggleElement.id.replace('toggle-', '');
                const content = document.getElementById('content-' + sectionId);
                const arrow = document.getElementById('arrow-' + sectionId);
                
                if (content && arrow && content.style.display !== 'none') {
                    content.style.display = 'none';
                    arrow.textContent = '▶';
                    toggleElement.style.borderColor = '#1976D2';
                }
            });
        }
        
        if (dash_clientside.callback_context.triggered.length > 0 && 
            dash_clientside.callback_context.triggered[0].prop_id.startsWith('collapse-trigger')) {
            setTimeout(collapseAllSections, 100); 
        }

        if (!window.assigneeToggleListenerAttached) {
            document.addEventListener('click', function(e) {
                let toggleElement = e.target.closest('[id^="toggle-assignee-section-"]');
                if (toggleElement) {
                    const sectionId = toggleElement.id.replace('toggle-', '');
                    const content = document.getElementById('content-' + sectionId);
                    const arrow = document.getElementById('arrow-' + sectionId);
                    
                    if (content && arrow) {
                        const isCollapsed = content.style.display === 'none' || content.style.display === '';
                        content.style.display = isCollapsed ? 'block' : 'none';
                        arrow.textContent = isCollapsed ? '▼' : '▶';
                        toggleElement.style.borderColor = isCollapsed ? '#1976D2' : '#2196F3';
                    }
                }
            });
            window.assigneeToggleListenerAttached = true;
        }
        
        return '';
    }
    """,
    Output('scroll-output', 'style', allow_duplicate=True),
    [Input('data-store', 'data'),
     Input('collapse-trigger', 'data')],
    prevent_initial_call=True 
)

clientside_callback(
    """
    function(scroll_trigger) {
        if (scroll_trigger && scroll_trigger > 0) {
            setTimeout(function() {
                const element = document.getElementById('defects-section');
                if (element) {
                    element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }, 200);
        }
        return {display: 'none'};
    }
    """,
    Output('scroll-output', 'children', allow_duplicate=True),
    Input('scroll-trigger', 'data'),
    prevent_initial_call=True
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)