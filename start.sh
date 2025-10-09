#!/bin/bash
echo "🚀 Starting deployment process..."

# Run DevOps extraction
echo "📥 Extracting defects from Azure DevOps..."
python defectsextraction.py

# Run Jira extraction for techcarrot Time Sheet
echo "📥 Extracting defects from Jira (techcarrot Time Sheet)..."
JIRA_PROJECT_KEY="techcarrot Time Sheet" JIRA_LABEL_FILTER="techcarrot-timesheet-build1" python jiraextraction.py

# Run Jira extraction for Emirates Transport
echo "📥 Extracting defects from Jira (Emirates Transport)..."
JIRA_PROJECT_KEY="Emirates Transport" JIRA_LABEL_FILTER="Gitex-2025" python jiraextraction.py

echo "✅ All extractions completed"
echo "🌐 Starting dashboard server..."
python -m waitress --host=0.0.0.0 --port=$PORT app:server