import requests
from requests.auth import HTTPBasicAuth
import openpyxl
from openpyxl.utils import get_column_letter
import os
import time

# Jira Configuration
jira_url = os.getenv("JIRA_URL", "https://techcarrot-team-aqqopo6gxdmd.atlassian.net")
jira_email = os.getenv("JIRA_EMAIL")
jira_api_token = os.getenv("JIRA_API_TOKEN")
jira_project_key = os.getenv("JIRA_PROJECT_KEY", "PROJ")
jira_label_filter = os.getenv("JIRA_LABEL_FILTER", "")

# State mapping from Jira to Azure DevOps
STATE_MAPPING = {
    "Open": "New",
    "New": "New",
    "To Do": "Reopen",
    "Reopen": "Reopen",
    "In Progress": "New",
    "In Development": "New",
    "Done": "Closed",
    "Closed": "Closed",
    "Resolved": "Resolved"
}

print("🔄 Starting Jira defects extraction...")
start_time = time.time()

# JQL query with label filter
if jira_label_filter:
    if ' ' in jira_project_key:
        jql_query = f'project = "{jira_project_key}" AND type = Bug AND labels = "{jira_label_filter}" ORDER BY created DESC'
    else:
        jql_query = f'project = {jira_project_key} AND type = Bug AND labels = "{jira_label_filter}" ORDER BY created DESC'
    print(f"🏷️  Using label filter: {jira_label_filter}")
else:
    if ' ' in jira_project_key:
        jql_query = f'project = "{jira_project_key}" AND type = Bug ORDER BY created DESC'
    else:
        jql_query = f'project = {jira_project_key} AND type = Bug ORDER BY created DESC'

print(f"📋 Fetching issues from Jira project: {jira_project_key}")
print(f"🔍 JQL Query: {jql_query}")

# Use NEW Jira API v3 search/jql endpoint (required as of 2025)
search_url = f"{jira_url}/rest/api/3/search/jql"

auth = HTTPBasicAuth(jira_email, jira_api_token)

# Pagination parameters - NEW API uses cursor-based pagination
next_page_token = None
all_issues = []
max_results = 100

# Fetch all issues with GET method and new pagination
while True:
    params = {
        "jql": jql_query,
        "maxResults": max_results,
        "fields": "*all"
    }
    
    # Add pagination token if it exists
    if next_page_token:
        params["nextPageToken"] = next_page_token
    
    try:
        # GET request with query parameters (NEW Jira v3 API /search/jql)
        response = requests.get(
            search_url, 
            params=params,
            auth=auth, 
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Error fetching issues: {response.status_code} - {response.text}")
            break
        
        data = response.json()
        issues = data.get('issues', [])
        all_issues.extend(issues)
        
        total = data.get('total', len(all_issues))
        print(f"   Fetched {len(all_issues)}/{total} issues...")
        
        # NEW API pagination - check for next page
        next_page_token = data.get('nextPageToken')
        is_last = data.get('isLast', True)
        
        if is_last or not next_page_token:
            break
        
    except requests.exceptions.Timeout:
        print(f"⚠️ Timeout occurred")
        break
    except Exception as e:
        print(f"⚠️ Error: {str(e)}")
        break

if not all_issues:
    print("⚠️ No issues found.")
    # Create empty Excel file
    wb = openpyxl.Workbook()
    sheet = wb.active
    sheet.title = "Jira Defects"
    sheet.append(["ID", "Work Item Type", "Title", "State", "Original Jira State", "Assigned To", "Tags", "Severity", "Issue Links"])
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(current_dir, "data")
    os.makedirs(data_folder, exist_ok=True)
    
    save_path = os.path.join(data_folder, f"Jira {jira_project_key} Defects.xlsx")
    wb.save(save_path)
    print(f"✅ Empty Excel file created at: {save_path}")
    exit()

print(f"✅ Found {len(all_issues)} issues. Processing...")

# Create Excel
wb = openpyxl.Workbook()
sheet = wb.active
sheet.title = "Jira Defects"
sheet.append(["ID", "Work Item Type", "Title", "State", "Original Jira State", "Assigned To", "Tags", "Severity", "Issue Links"])

# Process each issue with flexible field mapping
for idx, issue in enumerate(all_issues, start=2):
    issue_key = issue.get('key', '')
    fields = issue.get('fields', {})
    
    # Extract issue type - try different field names
    issue_type_obj = fields.get('issuetype') or fields.get('Type') or fields.get('type')
    if isinstance(issue_type_obj, dict):
        issue_type = issue_type_obj.get('name', 'Bug')
    else:
        issue_type = str(issue_type_obj) if issue_type_obj else 'Bug'
    
    # Extract title/summary - try multiple field names (Work, summary, etc.)
    title = (
        fields.get('Work') or 
        fields.get('work') or 
        fields.get('summary') or 
        fields.get('Summary') or 
        issue_key
    )
    if isinstance(title, dict):
        title = title.get('content', '') or str(title)
    
    # Status - flexible extraction
    status_obj = fields.get('status') or fields.get('Status')
    if isinstance(status_obj, dict):
        jira_status = status_obj.get('name', 'Unknown')
    else:
        jira_status = str(status_obj) if status_obj else 'Unknown'
    
    mapped_state = STATE_MAPPING.get(jira_status, jira_status)
    
    # Assignee - flexible extraction
    assignee_obj = fields.get('assignee') or fields.get('Assignee')
    if isinstance(assignee_obj, dict):
        assignee_name = (
            assignee_obj.get('displayName') or 
            assignee_obj.get('name') or 
            assignee_obj.get('emailAddress', '').split('@')[0] or
            'Unassigned'
        )
    else:
        assignee_name = str(assignee_obj) if assignee_obj else 'Unassigned'
    
    # Priority - flexible extraction
    priority_obj = fields.get('priority') or fields.get('Priority')
    if isinstance(priority_obj, dict):
        priority_name = priority_obj.get('name', 'Medium')
    else:
        priority_name = str(priority_obj) if priority_obj else 'Medium'
    
    # Map Jira priority to DevOps-style severity
    severity_map = {
        'Highest': '1 - Critical',
        'High': '2 - High',
        'Medium': '3 - Medium',
        'Low': '4 - Low',
        'Lowest': '5 - Suggestion',
        'Critical': '1 - Critical'
    }
    severity = severity_map.get(priority_name, f'3 - {priority_name}')
    
    # Labels/Tags
    labels_obj = fields.get('labels') or fields.get('Labels') or []
    if isinstance(labels_obj, list):
        tags = ', '.join(str(label) for label in labels_obj)
    else:
        tags = str(labels_obj) if labels_obj else ''
    
    # Issue URL
    issue_url = f"{jira_url}/browse/{issue_key}"
    
    # Write to Excel
    sheet.cell(row=idx, column=1, value=issue_key)
    sheet.cell(row=idx, column=2, value=issue_type)
    sheet.cell(row=idx, column=3, value=str(title))
    sheet.cell(row=idx, column=4, value=mapped_state)
    sheet.cell(row=idx, column=5, value=jira_status)
    sheet.cell(row=idx, column=6, value=assignee_name)
    sheet.cell(row=idx, column=7, value=tags)
    sheet.cell(row=idx, column=8, value=severity)
    sheet.cell(row=idx, column=9, value=issue_url)

# Adjust column widths
for col in range(1, 10):
    sheet.column_dimensions[get_column_letter(col)].width = 40

# Save Excel
current_dir = os.path.dirname(os.path.abspath(__file__))
data_folder = os.path.join(current_dir, "data")
os.makedirs(data_folder, exist_ok=True)

save_path = os.path.join(data_folder, f"Jira {jira_project_key} Defects.xlsx")
wb.save(save_path)

end_time = time.time()
elapsed_time = round(end_time - start_time, 2)

print(f"✅ Excel file saved at: {save_path}")
print(f"⏱️ Total execution time: {elapsed_time} seconds")
print(f"📊 Total defects extracted: {len(all_issues)}")