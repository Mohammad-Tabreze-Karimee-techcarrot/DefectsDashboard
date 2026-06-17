#!/bin/bash
echo "🚀 Starting deployment process..."

# Run DevOps extraction
echo "📥 Extracting defects from Azure DevOps..." 
python defectsextraction.py

# Run Jira extraction for Mediclinic
echo "📥 Extracting defects from Jira (Mediclinic)..."
JIRA_PROJECT_KEY="techcarrot Time Sheet" JIRA_LABEL_FILTER="techcarrot-timesheet-build1" python jiraextraction.py

# Run Jira extraction for techcarrot Time Sheet
echo "📥 Extracting defects from Jira (techcarrot Time Sheet)..."
JIRA_PROJECT_KEY="techcarrot Time Sheet" JIRA_LABEL_FILTER="techcarrot-timesheet-build1" python jiraextraction.py

# Run Jira extraction for Emirates Transport
echo "📥 Extracting defects from Jira (Emirates Transport)..."
JIRA_PROJECT_KEY="Emirates Transport" JIRA_LABEL_FILTER="Career_page" python jiraextraction.py

# Run Jira extraction for RAM Ji Website Req V2
echo "📥 Extracting defects from Jira (RAM Ji Website Req V2)..."
JIRA_PROJECT_KEY="Doctor_Ramji_Website" JIRA_LABEL_FILTER="Dr._Ram_Ji_Website_Requirements_V2" python jiraextraction.py

# Run Jira extraction for AFG Intranet
echo "📥 Extracting defects from Jira (AFG Intranet)..."
JIRA_PROJECT_KEY="Al-Futtaim Group" JIRA_LABEL_FILTER="AFG-Intranet" python jiraextraction.py

echo "✅ All extractions completed"
echo "🌐 Starting dashboard server..."
python -m waitress --host=0.0.0.0 --port=$PORT app:server