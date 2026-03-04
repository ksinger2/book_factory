#!/bin/bash
# Double-click this file to start Book Factory Studio
cd "$(dirname "$0")"

# Install dependencies if needed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "Installing dependencies (first time only)..."
    pip3 install --break-system-packages -r requirements.txt 2>/dev/null || pip3 install -r requirements.txt
    python3 -m playwright install chromium 2>/dev/null
fi

echo ""
echo "  Starting Book Factory Studio..."
echo "  Opening http://localhost:5555"
echo ""
python3 run.py
