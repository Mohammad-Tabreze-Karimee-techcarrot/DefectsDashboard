import requests
from requests.auth import HTTPBasicAuth
import openpyxl
from openpyxl.utils import get_column_letter
import os
import time

# Jira Configuration
jira_url = os.getenv("JIRA_URL", "https://your-domain.atlassian.net")
jira_email = os.getenv("JIRA_EMAIL")
jira_api_token = os.getenv("JIRA_API_TOKEN")
jira_project_key = os.getenv("JIRA_PROJECT_KEY", "PROJ")
jira_label_filter = os.getenv("JIRA_LABEL_FILTER", "")  # NEW: Label filter for build versions

# State mapping from Jira to Azure DevOps - UPDATED
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

# JQL query - UPDATED to include label filter if provided
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

# Jira API v2 endpoint (more compatible)
search_url = f"{jira_url}/rest/api/2/search"

# Prepare authentication
auth = HTTPBasicAuth(jira_email, jira_api_token)

# Pagination parameters
start_at = 0
max_results = 100
all_issues = []

# Fetch all issues (handle pagination) - Using GET method
while True:
    # Query parameters for GET request
    params = {
        'jql': jql_query,
        'startAt': start_at,
        'maxResults': max_results,
        'fields': 'summary,status,assignee,priority,created,updated'
    }
    
    try:
        response = requests.get(search_url, params=params, auth=auth, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Error fetching issues: {response.status_code} - {response.text}")
            break
        
        data = response.json()
        issues = data.get('issues', [])
        all_issues.extend(issues)
        
        total = data.get('total', 0)
        print(f"   Fetched {len(all_issues)}/{total} issues...")
        
        # Check if we've fetched all issues
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
    # Create empty Excel file to avoid errors
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
    issue_type = "Bug"  # Default to Bug since issuetype is not available
    
    # Title - Try summary field
    title = fields.get('summary', '') or fields.get('work', '') or issue_key
    
    # Status - Get original and map to Azure DevOps state
    status_field = fields.get('status', {})
    jira_status = status_field.get('name', 'Unknown') if isinstance(status_field, dict) else str(status_field)
    mapped_state = STATE_MAPPING.get(jira_status, jira_status)
    
    # Assignee
    assignee = fields.get('assignee', {})
    if isinstance(assignee, dict):
        assignee_name = assignee.get('displayName', '') or assignee.get('name', '')
    else:
        assignee_name = str(assignee) if assignee else ''
    
    if not assignee_name:
        assignee_name = 'Unassigned'
    
    # Priority (map to Severity)
    priority = fields.get('priority', {})
    if isinstance(priority, dict):
        priority_name = priority.get('name', 'Medium')
    else:
        priority_name = str(priority) if priority else 'Medium'
    
    # Map Jira priority to DevOps-style severity
    severity_map = {
        'Highest': '1 - Critical',
        'High': '2 - High',
        'Medium': '3 - Medium',
        'Low': '4 - Low',
        'Lowest': '5 - Suggestion'
    }
    severity = severity_map.get(priority_name, f'3 - {priority_name}')
    
    # Tags - empty since labels are not available
    tags = ''
    
    # Issue URL
    issue_url = f"{jira_url}/browse/{issue_key}"
    
    # Write to Excel
    sheet.cell(row=idx, column=1, value=issue_key)
    sheet.cell(row=idx, column=2, value=issue_type)
    sheet.cell(row=idx, column=3, value=title)
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