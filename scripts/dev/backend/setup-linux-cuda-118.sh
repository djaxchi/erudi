#!/usr/bin/env bash
# Simple and efficient Python environment setup script for Erudi on macOS/Linux with CUDA 12.1
# Requirements: Python 3.9+

set -e  # Exit on error

# Helper functions for consistent status messages
write_status() { echo -e "\033[36m[STATUS] $1\033[0m"; }
write_error() { echo -e "\033[31m[ERROR] $1\033[0m"; exit 1; }

# Determine current directory and set venv + requirements paths
current_dir=$(basename "$PWD")
if [ "$current_dir" == "backend" ]; then
    echo "You are currently in erudi/backend/"
    req="./requirements/entrypoints/linux-cuda-118.txt"
    venv_path="./venv"
else
    echo "You are currently in erudi/ , don't forget to move in backend/ after the init to run the backend"
    req="./backend/requirements/entrypoints/linux-cuda-118.txt"
    venv_path="./backend/venv"
fi

# Check Python version (3.9+)
write_status "Checking Python version..."

python_candidates=("python3" "python" "py3" "py")
python_cmd=""
version=""

for cmd in "${python_candidates[@]}"; do
    if version=$($cmd --version 2>&1); then
        python_cmd=$cmd
        break
    fi
done

if [ -z "$python_cmd" ]; then
    write_error "No valid Python executable found in PATH (tried: ${python_candidates[*]})"
fi

if [[ $version =~ ([0-9]+)\.([0-9]+)\.([0-9]+) ]]; then
    major=${BASH_REMATCH[1]}
    minor=${BASH_REMATCH[2]}
    if (( major < 3 || (major == 3 && minor < 9) )); then
        write_error "Python 3.9+ required, found: $version"
    else
        write_status "Using Python: $python_cmd ($version)"
    fi
else
    write_error "Could not determine Python version from output: $version"
fi

# Check and create virtual environment
write_status "Checking virtual environment in $venv_path..."

if [ -d "$venv_path" ]; then
    read -p "A virtual env already exists in $venv_path. Do you want to delete it ? (Y/n) " venv_confirmation
    venv_confirmation=${venv_confirmation:-Y}
    if [[ "$venv_confirmation" =~ ^[Yy]$ ]]; then
        write_status "Removing existing virtual environment..."
        rm -rf "$venv_path"
        write_status "Creating venv..."
        $python_cmd -m venv "$venv_path" || write_error "Failed to create virtual environment"
    else
        write_status "Virtual environment already exists, requirements will be installed inside it."
    fi
else
    write_status "Creating venv..."
    $python_cmd -m venv "$venv_path" || write_error "Failed to create virtual environment"
fi

# Activate virtual environment
write_status "Activating virtual environment..."
# shellcheck disable=SC1090
source "$venv_path/bin/activate" || write_error "Failed to activate virtual environment"

venv_python="$venv_path/bin/python"

# Upgrade pip
write_status "Upgrading pip..."
$venv_python -m pip install --upgrade pip || write_error "Failed to upgrade pip"

# Install requirements
read -p "Do you want to --force-reinstall the requirements ? (Y/n) " force_reinstall_confirmation
force_reinstall_confirmation=${force_reinstall_confirmation:-Y}

write_status "Installing requirements from $req..."
if [[ "$force_reinstall_confirmation" =~ ^[Yy]$ ]]; then
    $venv_python -m pip install --no-cache-dir --force-reinstall -r "$req" || write_error "Failed to install requirements from $req"
else
    $venv_python -m pip install --no-cache-dir -r "$req" || write_error "Failed to install requirements from $req"
fi

echo
echo -e "\033[32mEnvironment setup complete! Welcome on-board at Erudi !\033[0m"
echo "You can now run: 'uvicorn src.main:app' inside backend/ and after sourcing the venv."
echo
