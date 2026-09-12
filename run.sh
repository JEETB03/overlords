#!/usr/bin/env bash
set -e

echo "================================================================="
echo "       OVERLORD // Autonomous UAV & UGV Tactical C2 System       "
echo "================================================================="

# Navigate to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Detect Python 3
if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "[ERROR] Python 3 was not found in PATH. Please install Python 3.10+."
    exit 1
fi

echo "[+] Using Python: $($PYTHON_BIN --version)"

# 2. Setup Virtual Environment
if [ ! -d ".venv" ]; then
    echo "[+] Creating virtual environment (.venv)..."
    $PYTHON_BIN -m venv .venv
else
    echo "[+] Existing virtual environment detected."
fi

# 3. Activate Virtual Environment
source .venv/bin/activate

# 4. Install / Update Dependencies
echo "[+] Ensuring dependencies are installed from requirements.txt..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

# 5. Ensure storage directories exist
mkdir -p storage/snapshots

echo ""
echo "================================================================="
echo " [OK] OVERLORD Tactical C2 Dashboard is starting up..."
echo " [>] Open in browser: http://localhost:8000"
echo "================================================================="
echo ""

# 6. Start Dashboard Server
exec python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
