#!/usr/bin/env bash
# Erudi Backend Setup Script - Linux CPU
# Supports both development and production environments
# Compatible with interactive use and CI/CD pipelines
# Requirements: Python 3.9+

set -e  # Exit on error

# Colors for output
readonly COLOR_STATUS="\033[36m"
readonly COLOR_SUCCESS="\033[32m"
readonly COLOR_ERROR="\033[31m"
readonly COLOR_RESET="\033[0m"

# Helper functions
write_status() { echo -e "${COLOR_STATUS}[STATUS]${COLOR_RESET} $1"; }
write_success() { echo -e "${COLOR_SUCCESS}[SUCCESS]${COLOR_RESET} $1"; }
write_error() { echo -e "${COLOR_ERROR}[ERROR]${COLOR_RESET} $1"; exit 1; }

# Determine environment (CI/CD or interactive)
is_ci_mode() {
    [[ "${CI:-false}" == "true" ]] || [[ "${GITHUB_ACTIONS:-false}" == "true" ]] || [[ -n "${JENKINS_HOME:-}" ]]
}

# Determine current directory and set paths
current_dir=$(basename "$PWD")
if [ "$current_dir" == "backend" ]; then
    write_status "Running from erudi/backend/"
    req_dev="./requirements/entrypoints/dev/linux-cpu.txt"
    req_prod="./requirements/entrypoints/prod/linux-cpu-prod.txt"
    venv_path="./venv"
else
    write_status "Running from erudi/ (don't forget to cd backend/ after setup)"
    req_dev="./backend/requirements/entrypoints/dev/linux-cpu.txt"
    req_prod="./backend/requirements/entrypoints/prod/linux-cpu-prod.txt"
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

# Determine environment type (production or development)
install_type="dev"

if is_ci_mode; then
    write_status "CI/CD mode detected"
    # Check for INSTALL_TYPE environment variable in CI
    install_type="${INSTALL_TYPE:-prod}"
    write_status "Installing ${install_type} dependencies (set INSTALL_TYPE=dev/prod to change)"
else
    # Interactive mode
    echo
    echo "Choose installation type:"
    echo "  [1] Development (includes testing, linting, debugging tools)"
    echo "  [2] Production  (minimal dependencies only)"
    echo
    read -p "Enter choice [1/2] (default: 1): " choice
    choice=${choice:-1}

    case "$choice" in
        1) install_type="dev" ;;
        2) install_type="prod" ;;
        *) write_error "Invalid choice. Please enter 1 or 2." ;;
    esac
fi

if [ "$install_type" == "dev" ]; then
    req_file="$req_dev"
    write_status "Setting up DEVELOPMENT environment"
else
    req_file="$req_prod"
    write_status "Setting up PRODUCTION environment"
fi

# Handle existing virtual environment
write_status "Checking virtual environment in $venv_path..."

if [ -d "$venv_path" ]; then
    if is_ci_mode; then
        # In CI, always recreate
        write_status "CI mode: Removing existing virtual environment..."
        rm -rf "$venv_path"
        write_status "Creating fresh virtual environment..."
        $python_cmd -m venv "$venv_path" || write_error "Failed to create virtual environment"
    else
        # Interactive mode: ask user
        read -p "Virtual environment exists. Recreate it? [Y/n]: " venv_confirmation
        venv_confirmation=${venv_confirmation:-Y}
        if [[ "$venv_confirmation" =~ ^[Yy]$ ]]; then
            write_status "Removing existing virtual environment..."
            rm -rf "$venv_path"
            write_status "Creating fresh virtual environment..."
            $python_cmd -m venv "$venv_path" || write_error "Failed to create virtual environment"
        else
            write_status "Using existing virtual environment"
        fi
    fi
else
    write_status "Creating virtual environment..."
    $python_cmd -m venv "$venv_path" || write_error "Failed to create virtual environment"
fi

# Activate virtual environment
write_status "Activating virtual environment..."
# shellcheck disable=SC1090
source "$venv_path/bin/activate" || write_error "Failed to activate virtual environment"

venv_python="$venv_path/bin/python"

# Upgrade pip
write_status "Upgrading pip..."
$venv_python -m pip install --upgrade pip --quiet || write_error "Failed to upgrade pip"

# Install requirements
if is_ci_mode; then
    # In CI, always force reinstall for clean state
    write_status "Installing requirements from $req_file (force reinstall)..."
    $venv_python -m pip install --no-cache-dir --force-reinstall -r "$req_file" || write_error "Failed to install requirements"
else
    # Interactive mode: ask about force reinstall
    read -p "Force reinstall all packages? [Y/n]: " force_reinstall
    force_reinstall=${force_reinstall:-Y}

    if [[ "$force_reinstall" =~ ^[Yy]$ ]]; then
        write_status "Installing requirements from $req_file (force reinstall)..."
        $venv_python -m pip install --no-cache-dir --force-reinstall -r "$req_file" || write_error "Failed to install requirements"
    else
        write_status "Installing requirements from $req_file..."
        $venv_python -m pip install --no-cache-dir -r "$req_file" || write_error "Failed to install requirements"
    fi
fi

# Success message
echo
write_success "✓ Environment setup complete!"
echo
echo "Environment: ${install_type^^}"
echo "Python: $version"
echo "Virtual env: $venv_path"
echo
if [ "$current_dir" != "backend" ]; then
    echo "Next steps:"
    echo "  1. cd backend/"
    echo "  2. source venv/bin/activate"
    echo "  3. uvicorn src.main:app --reload"
else
    echo "Next steps:"
    echo "  1. source venv/bin/activate"
    echo "  2. uvicorn src.main:app --reload"
fi
echo
