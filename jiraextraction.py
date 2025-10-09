import requests
from requests.auth import HTTPBasicAuth
import openpyxl
from openpyxl.utils import get_column_letter
import os
import time
import json

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

# ✅ FIXED: Use the NEW /rest/api/3/search/jql endpoint (not /search)
search_url = f"{jira_url}/rest/api/3/search/jql"

# Prepare request headers for POST
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}

auth = HTTPBasicAuth(jira_email, jira_api_token)

# Pagination parameters
start_at = 0
max_results = 100
all_issues = []

# ✅ FIXED: Use POST method with JSON body (not GET with params)
while True:
    payload = {
        'jql': jql_query,
        'startAt': start_at,
        'maxResults': max_results,
        'fields': ['summary', 'status', 'assignee', 'priority', 'created', 'updated', 'issuetype', 'labels']
    }
    
    try:
        # POST request with JSON body
        response = requests.post(search_url, headers=headers, auth=auth, data=json.dumps(payload), timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Error fetching issues: {response.status_code} - {response.text}")
            break
        
        data = response.json()
        issues = data.get('issues', [])
        all_issues.extend(issues)
        
        total = data.get('total', 0)
        print(f"   Fetched {len(all_issues)}/{total} issues...")
        
        if len(all_issues) >= total:
            break
        
        start_at += max_results
        
    except requests.exceptions.Timeout:
        print(f"⚠️ Timeout occurred at startAt={start_at}")
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

# Process each issue
for idx, issue in enumerate(all_issues, start=2):
    issue_key = issue.get('key', '')
    fields = issue.get('fields', {})
    
    # Extract fields
    issue_type = fields.get('issuetype', {}).get('name', 'Bug')
    summary = fields.get('summary', '')
    
    # Status - Get original and map
    jira_status = fields.get('status', {}).get('name', 'Unknown')
    mapped_state = STATE_MAPPING.get(jira_status, jira_status)
    
    # Assignee
    assignee = fields.get('assignee', {})
    assignee_name = assignee.get('displayName', '') if assignee else 'Unassigned'
    
    # Priority (map to Severity)
    priority = fields.get('priority', {})
    priority_name = priority.get('name', 'Medium') if priority else 'Medium'
    
    severity_map = {
        'Highest': '1 - Critical',
        'High': '2 - High',
        'Medium': '3 - Medium',
        'Low': '4 - Low',
        'Lowest': '5 - Suggestion'
    }
    severity = severity_map.get(priority_name, f'3 - {priority_name}')
    
    # Labels/Tags
    labels = fields.get('labels', [])
    tags = ', '.join(labels) if labels else ''
    
    # Issue URL
    issue_url = f"{jira_url}/browse/{issue_key}"
    
    # Write to Excel
    sheet.cell(row=idx, column=1, value=issue_key)
    sheet.cell(row=idx, column=2, value=issue_type)
    sheet.cell(row=idx, column=3, value=summary)
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