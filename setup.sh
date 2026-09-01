#!/usr/bin/env bash
# =============================================================================
# Automated Setup Script for AI Gateway Perimetral
# Compatible with Linux, macOS, and Windows (Git Bash / MSYS2)
# =============================================================================

set -e

echo "=== [1/4] Checking Python runtime ==="
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python is not installed or not in PATH."
    exit 1
fi
echo "Using Python: $($PYTHON_CMD --version)"

echo ""
echo "=== [2/4] Setting up virtual environment (.venv) ==="
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv .venv
else
    echo "Virtual environment already exists."
fi

# Detect OS / Shell activation script
if [ -f ".venv/Scripts/activate" ]; then
    # Windows (Git Bash / MSYS)
    source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then
    # Linux / macOS
    source .venv/bin/activate
else
    echo "Error: Virtual environment activation script not found."
    exit 1
fi
echo "Virtual environment activated."

echo ""
echo "=== [3/4] Installing dependencies ==="
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt

echo ""
echo "=== [4/4] Configuring environment variables ==="
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "Created .env from .env.example."
        echo ">> Remember to edit .env to configure your BACKEND_API_KEY (Groq API Key)."
    else
        echo "Warning: .env.example not found."
    fi
else
    echo ".env file already exists."
fi

echo ""
echo "================================================================="
echo "Setup completed successfully!"
echo ""
echo "To start working:"
if [ -f ".venv/Scripts/activate" ]; then
    echo "  1. Activate the venv:  source .venv/Scripts/activate"
else
    echo "  1. Activate the venv:  source .venv/bin/activate"
fi
echo "  2. Configure your .env (Groq Key, PostgreSQL DATABASE_URL, Brevo SMTP)"
echo "  3. (Optional) Run SQL schema: psql -U <user> -d <database> -f sql/create_tables.sql"
echo "  4. Start the gateway:  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo "================================================================="
