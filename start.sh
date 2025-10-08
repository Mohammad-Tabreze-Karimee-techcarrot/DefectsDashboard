#!/bin/bash
echo "🚀 Starting deployment process..."

# Run DevOps extraction
echo "📥 Extracting defects from Azure DevOps..."
python defectsextraction.py

# Run Jira extraction
echo "📥 Extracting defects from Jira..."
python jiraextraction.py

echo "✅ All extractions completed"
echo "🌐 Starting dashboard server..."
python -m waitress --host=0.0.0.0 --port=$PORT app:server