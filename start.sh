#!/bin/bash

echo "🚀 Starting deployment process..."

# Run the defects extraction first
echo "📥 Extracting defects from DevOps..."
python defectsextraction.py

# Check if extraction was successful
if [ $? -eq 0 ]; then
    echo "✅ Defects extraction completed successfully"
else
    echo "⚠️ Warning: Defects extraction had issues, but continuing..."
fi

# Start the Dash app using waitress (production server)
echo "🌐 Starting dashboard server..."
python -m waitress --host=0.0.0.0 --port=$PORT app:server