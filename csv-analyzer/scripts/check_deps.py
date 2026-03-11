#!/usr/bin/env python3
"""
Dependency checker for CSV Analyzer skill.
Creates a virtual environment and installs missing dependencies.
"""

import subprocess
import sys
from pathlib import Path

REQUIRED_PACKAGES = [
    'pandas',
    'matplotlib',
    'seaborn',
    'numpy',
]


def check_import(package_name):
    """Check if a package can be imported."""
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False


def setup_environment():
    """Set up virtual environment and install dependencies."""
    skill_dir = Path(__file__).parent.parent
    scripts_dir = Path(__file__).parent
    venv_dir = scripts_dir / 'venv'

    print("Setting up CSV Analyzer environment...")

    if not venv_dir.exists():
        print(f"Creating virtual environment at {venv_dir}")
        subprocess.run([sys.executable, '-m', 'venv', str(venv_dir)], check=True)

    if sys.platform == 'win32':
        pip_path = venv_dir / 'Scripts' / 'pip'
    else:
        pip_path = venv_dir / 'bin' / 'pip'

    requirements_file = skill_dir / 'requirements.txt'
    if requirements_file.exists():
        print(f"Installing dependencies from {requirements_file}")
        subprocess.run([str(pip_path), 'install', '-q', '-r',
                        str(requirements_file)], check=True)
        print("Dependencies installed successfully")

    return venv_dir


def get_python_path():
    """Get the Python executable path from venv."""
    scripts_dir = Path(__file__).parent
    venv_dir = scripts_dir / 'venv'

    if sys.platform == 'win32':
        return str(venv_dir / 'Scripts' / 'python')
    return str(venv_dir / 'bin' / 'python3')


if __name__ == '__main__':
    in_venv = (hasattr(sys, 'real_prefix') or
               (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))

    if not in_venv:
        # Check system Python first
        missing = [p for p in REQUIRED_PACKAGES if not check_import(p)]
        if not missing:
            print("All dependencies are available in system Python")
            sys.exit(0)

        print(f"Missing packages: {', '.join(missing)}")
        print("Setting up virtual environment...")
        setup_environment()
        print(f"\nSetup complete!")
        print(f"Python path: {get_python_path()}")
    else:
        missing = [p for p in REQUIRED_PACKAGES if not check_import(p)]
        if missing:
            print(f"Missing packages: {', '.join(missing)}")
            print("Run: pip install -r requirements.txt")
            sys.exit(1)
        else:
            print("All dependencies are installed")
