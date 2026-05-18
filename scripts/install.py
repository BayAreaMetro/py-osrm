#!/usr/bin/env python3
"""
Install py-osrm from GitHub Releases.
Detects platform/Python version and installs the matching wheel.
Falls back to source installation if no wheel is available.
"""

import json
import platform
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_OWNER = "BayAreaMetro"
REPO_NAME = "py-osrm"
BRANCH = "main"
GITHUB_API = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"


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


def pip_install(target):
    """Run uv pip install on a URL or package spec. Returns True on success."""
    cmd = ["uv", "pip", "install", target]
    print(f"Running: {' '.join(cmd)}")
    return subprocess.call(cmd) == 0


def main():
    print(f"Platform: {platform.system()} {platform.machine()}")
    print(f"Python:   {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}\n")

    # Try pre-built wheel from GitHub Releases
    wheel_url = find_wheel_url()
    if wheel_url:
        print(f"\nInstalling wheel: {wheel_url}")
        if pip_install(wheel_url):
            print("\nInstallation successful.")
            return 0
        print("\nWheel installation failed.")

    # Fall back to source install
    git_url = f"git+https://github.com/{REPO_OWNER}/{REPO_NAME}.git@{BRANCH}"
    print(f"\nNo pre-built wheel found. Installing from source (requires C++ toolchain).")
    print(f"Source: {git_url}\n")
    if pip_install(git_url):
        print("\nInstallation successful.")
        return 0

    print("\nInstallation failed. Ensure you have a C++ compiler and CMake installed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
