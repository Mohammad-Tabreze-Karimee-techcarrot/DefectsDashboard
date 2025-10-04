import dash
from dash import dcc, html, dash_table
import plotly.express as px
import pandas as pd
import os

# Read Excel file
current_dir = os.path.dirname(os.path.abspath(__file__))
data_folder = os.path.join(current_dir, "data")
file_path = os.path.join(data_folder, "Smart FM Defects through Python.xlsx")

df = pd.read_excel(file_path)

# Rename columns to avoid issues
df = df.rename(columns=lambda x: x.strip())

# Ensure required columns exist
required_cols = ["ID", "Work Item Type", "Title", "Issue Links", "State", "Assigned To", "Severity", "Tags"]
for col in required_cols:
    if col not in df.columns:
        df[col] = ""

# 🔹 Create clickable Title
df["Title (Link)"] = df.apply(
    lambda row: f"[{row['Title']}]({row['Issue Links']})" if pd.notna(row["Issue Links"]) and row["Issue Links"].strip() != "" else row["Title"],
    axis=1
)

# 🔹 Create color-coded Tags badges (HTML spans with tooltips)
def format_tags(tag_string):
    if pd.isna(tag_string) or str(tag_string).strip() == "":
        return ""
    tags = [t.strip() for t in str(tag_string).split(";") if t.strip()]
    colors = ["#ff5733", "#33c1ff", "#75ff33", "#f033ff", "#ffc300", "#a569bd"]
    styled_tags = [
        f"<span title='{tag}' style='background-color:{colors[i % len(colors)]}; "
        f"color:white; padding:3px 8px; border-radius:12px; margin-right:4px; "
        f"font-size:12px; display:inline-block; cursor:pointer;'>{tag}</span>"
        for i, tag in enumerate(tags)
    ]
    return " ".join(styled_tags)

df["Formatted Tags"] = df["Tags"].apply(format_tags)

# 🔹 1. Defect status summary
status_counts = df["State"].value_counts().to_dict()
new_count = status_counts.get("New", 0)
reopen_count = status_counts.get("Reopen", 0)
closed_count = status_counts.get("Closed", 0)
resolved_count = status_counts.get("Resolved", 0)

status_table = pd.DataFrame({
    "Status": ["New", "Reopen", "Closed", "Resolved"],
    "Count": [new_count, reopen_count, closed_count, resolved_count]
})

status_colors = {
    "New": "red",
    "Reopen": "maroon",
    "Closed": "green",
    "Resolved": "orange"
}

# 🔹 2. Pie Chart (Defect by Status)
fig_status = px.pie(
    status_table,
    names="Status",
    values="Count",
    color="Status",
    color_discrete_map=status_colors,
    hole=0.4
)
fig_status.update_traces(textinfo="percent+label+value", pull=[0.05]*4)
fig_status.update_layout(title="Defect Distribution by Status")

# 🔹 3. Severity Chart
severity_order = ["High", "Medium", "Low", "Suggestion"]
df["Severity"] = df["Severity"].astype(str).str.replace(r"^\d+-", "", regex=True)
severity_counts = df["Severity"].value_counts().reindex(severity_order, fill_value=0)

fig_severity = px.bar(
    x=severity_counts.index,
    y=severity_counts.values,
    text=severity_counts.values,
    labels={"x": "Severity", "y": "Defect Count"},
    color=severity_counts.index,
    color_discrete_map={"High": "red", "Medium": "orange", "Low": "blue", "Suggestion": "gray"}
)
fig_severity.update_traces(textposition="outside")
fig_severity.update_layout(title="Open Defect Count by Severity")

# 🔹 4. Defects with Detail
detail_columns = [
    "ID", "Work Item Type", "Title (Link)", "State", "Assigned To", "Severity", "Formatted Tags"
]

detail_table = dash_table.DataTable(
    columns=[{"name": col, "id": col, "presentation": "markdown" if col in ["Title (Link)", "Formatted Tags"] else "markdown"} for col in detail_columns],
    data=df[detail_columns].to_dict("records"),
    style_table={"overflowX": "auto"},
    style_cell={"textAlign": "left", "padding": "8px", "whiteSpace": "normal"},
    style_header={"backgroundColor": "#f4f4f4", "fontWeight": "bold"},
    markdown_options={"html": True}  # Safe for older Dash versions
)

# 🔹 5. Dash App
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("Smart FM Defects Dashboard", style={"textAlign": "center"}),

    # Status table
    html.H3("Defect Status Summary"),
    dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in status_table.columns],
        data=status_table.to_dict("records"),
        style_cell={"textAlign": "center", "padding": "8px"},
        style_header={"backgroundColor": "#f4f4f4", "fontWeight": "bold"},
        style_data_conditional=[
            {"if": {"filter_query": "{Status} = 'New'"}, "backgroundColor": "red", "color": "white"},
            {"if": {"filter_query": "{Status} = 'Reopen'"}, "backgroundColor": "maroon", "color": "white"},
            {"if": {"filter_query": "{Status} = 'Closed'"}, "backgroundColor": "green", "color": "white"},
            {"if": {"filter_query": "{Status} = 'Resolved'"}, "backgroundColor": "orange", "color": "white"},
        ],
    ),

    # Charts
    html.Div([
        html.Div([dcc.Graph(figure=fig_status)], style={"width": "50%", "display": "inline-block"}),
        html.Div([dcc.Graph(figure=fig_severity)], style={"width": "50%", "display": "inline-block"}),
    ]),

    html.H3("Defects with Detail"),
    detail_table
])

if __name__ == "__main__":
    app.run_server(debug=True)
