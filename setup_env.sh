#!/bin/bash
# This script creates a Python virtual environment and installs dependencies.

# Add uv's installation directory to PATH if it's not already there
export PATH="/home/emo/.local/bin:$PATH"

# Exit immediately if a command exits with a non-zero status.
set -e

VENV_NAME=".venv_quiz_iq"
PYTHON_INTERPRETER="python3"

echo "Looking for uv..."
if ! command -v uv &> /dev/null
then
    echo "uv could not be found. Please install it first:"
    echo "curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "Creating virtual environment '$VENV_NAME'..."
uv venv $VENV_NAME -p $PYTHON_INTERPRETER

echo "Activating virtual environment..."
# In bash, the 'source' command executes the script in the current shell.
source $VENV_NAME/bin/activate

echo "Installing dependencies from requirements.txt..."
uv pip install -r requirements.txt

echo "Setup complete. Virtual environment '$VENV_NAME' is ready."
echo "To activate it in your shell, run: source $VENV_NAME/bin/activate"
