#!/usr/bin/env python3
"""
Install py-osrm into a clean virtual environment using uv.
Creates a fresh venv, detects platform/Python version, downloads the matching
wheel from GitHub Releases, and installs it along with all dependencies.
Falls back to source installation if no wheel is available.

Usage (from the repo root):
    uv run --no-project scripts/install.py

The --no-project flag is required to prevent uv from trying to build the
local C++ project before running the script.
"""

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_OWNER = "BayAreaMetro"
REPO_NAME = "py-osrm"
BRANCH = "main"
GITHUB_API = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"

DEPENDENCIES = [
    "aiohttp>=3.8",
    "numpy",
    "plotly",
    "polars",
    "polyline",
    "requests",
    "tqdm>=4.0",
    "ipykernel",
    "nbformat>=4.2.0",
]

DEFAULT_VENV_DIR = ".venv"


def get_wheel_tags():
    """Return (python_tag, platform_keywords) for the current environment.
    
    Platform keywords are substrings that must ALL appear in the wheel filename.
    This handles version differences in manylinux/macosx tags (e.g. manylinux_2_28
    vs manylinux_2_17, macosx_15_0 vs macosx_11_0).
    """
    cp = f"cp{sys.version_info.major}{sys.version_info.minor}"
    python_tag = f"{cp}-{cp}"

    system = platform.system().lower()
    machine = platform.machine().lower()

    # Each entry is a list of substrings that must all be present in the filename
    platform_map = {
        ("linux", "x86_64"): ["linux", "x86_64"],
        ("linux", "amd64"): ["linux", "x86_64"],
        ("linux", "aarch64"): ["linux", "aarch64"],
        ("linux", "arm64"): ["linux", "aarch64"],
        ("darwin", "x86_64"): ["macosx", "x86_64"],
        ("darwin", "amd64"): ["macosx", "x86_64"],
        ("darwin", "arm64"): ["macosx", "arm64"],
        ("windows", "x86_64"): ["win_amd64"],
        ("windows", "amd64"): ["win_amd64"],
    }
    platform_keywords = platform_map.get((system, machine))
    return python_tag, platform_keywords


def find_wheel_url():
    """Fetch latest GitHub release and return URL of matching wheel, or None."""
    try:
        req = Request(GITHUB_API, headers={"Accept": "application/vnd.github.v3+json"})
        with urlopen(req, timeout=10) as resp:
            release = json.loads(resp.read())
    except (HTTPError, URLError) as e:
        print(f"Could not fetch releases: {e}")
        return None

    python_tag, platform_keywords = get_wheel_tags()
    if not platform_keywords:
        print(f"Unsupported platform: {platform.system()} {platform.machine()}")
        return None

    print(f"Latest release: {release.get('tag_name', 'unknown')}")
    print(f"Looking for wheel matching: {python_tag} / {platform_keywords}")

    for asset in release.get("assets", []):
        name = asset["name"]
        if not name.endswith(".whl"):
            continue
        if python_tag not in name:
            continue
        if all(kw in name for kw in platform_keywords):
            return asset["browser_download_url"]

    return None


def uv(*args):
    """Run a uv command. Returns True on success."""
    cmd = ["uv", *args]
    print(f"Running: {' '.join(cmd)}")
    return subprocess.call(cmd) == 0


def uv_or_die(*args):
    """Run a uv command, exit on failure."""
    if not uv(*args):
        print(f"\nCommand failed: uv {' '.join(args)}")
        sys.exit(1)


def main():
    # Check uv is available
    if not shutil.which("uv"):
        print("ERROR: 'uv' not found. Install it from https://docs.astral.sh/uv/")
        return 1

    print(f"Platform: {platform.system()} {platform.machine()}")
    print(f"Python:   {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}\n")

    venv_dir = Path(DEFAULT_VENV_DIR).resolve()

    # Create a clean venv with uv (handles removal automatically)
    print(f"Creating clean venv: {venv_dir}\n")
    uv_or_die("venv", str(venv_dir), "--python", f"{sys.version_info.major}.{sys.version_info.minor}", "--seed")

    # Install dependencies
    print("\nInstalling dependencies...")
    uv_or_die("pip", "install", "--python", str(venv_dir), "--no-cache", *DEPENDENCIES)
    print()

    # Try pre-built wheel from GitHub Releases
    wheel_url = find_wheel_url()
    if wheel_url:
        print(f"\nInstalling wheel: {wheel_url}")
        if uv("pip", "install", "--python", str(venv_dir), "--no-cache", wheel_url):
            print(f"\nInstallation successful!")
            print(f"Activate the environment with:")
            if platform.system() == "Windows":
                print(f"  {venv_dir}\\Scripts\\activate")
            else:
                print(f"  source {venv_dir}/bin/activate")
            return 0
        print("\nWheel installation failed.")

    # Fall back to source install
    git_url = f"git+https://github.com/{REPO_OWNER}/{REPO_NAME}.git@{BRANCH}"
    print(f"\nNo pre-built wheel found. Installing from source (requires C++ toolchain).")
    print(f"Source: {git_url}\n")
    if uv("pip", "install", "--python", str(venv_dir), "--no-cache", git_url):
        print(f"\nInstallation successful!")
        print(f"Activate the environment with:")
        if platform.system() == "Windows":
            print(f"  {venv_dir}\\Scripts\\activate")
        else:
            print(f"  source {venv_dir}/bin/activate")
        return 0

    print("\nInstallation failed. Ensure you have a C++ compiler and CMake installed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
