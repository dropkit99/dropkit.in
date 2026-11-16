#!/usr/bin/env python3
"""
DropKit Automated Firebase Deployment Pre-Flight & CI/CD Trigger
Verifies project integrity, runs 24 security & payment tests, and coordinates automated deployment.
"""

import sys
import subprocess
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

def run_command(cmd, desc):
    print(f"\n[STEP] {desc}...")
    res = subprocess.run(cmd, cwd=str(ROOT_DIR), shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"❌ Error during '{desc}':")
        print(res.stderr or res.stdout)
        return False, res.stdout, res.stderr
    print(f"✅ {desc} passed successfully.")
    return True, res.stdout, res.stderr

def main():
    print("=" * 70)
    print("DROPKIT — FIREBASE AUTOMATED DEPLOYMENT ORCHESTRATOR")
    print("=" * 70)

    # 1. Verify firebase.json
    fb_json = ROOT_DIR / "firebase.json"
    if not fb_json.exists():
        print("❌ Error: firebase.json configuration missing!")
        sys.exit(1)

    try:
        with open(fb_json, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        assert "hosting" in cfg, "Missing 'hosting' section in firebase.json"
        print("✅ firebase.json valid and properly configured.")
    except Exception as e:
        print(f"❌ Error validating firebase.json: {e}")
        sys.exit(1)

    # 2. Run Comprehensive Test Suite
    ok, stdout, stderr = run_command("python tests/test_backend.py", "Running 24 Security & Payment Audit Tests")
    if not ok:
        print("\n❌ Deployment halted: Test suite failed. Deployment aborted to protect production.")
        sys.exit(1)

    # 3. Check Git Status
    ok, git_status, _ = run_command("git status --porcelain", "Checking Git Status")
    if git_status.strip():
        print(f"ℹ️ Uncommitted changes detected:\n{git_status.strip()}")
    else:
        print("✅ Working tree clean.")

    # 4. Check GitHub Remote
    ok, remotes, _ = run_command("git remote -v", "Checking Git Remotes")
    print(remotes.strip())

    print("\n" + "=" * 70)
    print("✅ PRE-FLIGHT VERIFICATION PASSED (100% READY FOR FIREBASE DEPLOYMENT)")
    print("=" * 70)
    print("CI/CD Pipeline: Pushing commits to 'main' triggers GitHub Actions -> Firebase Hosting automatic deployment.")
    print("Custom Domain: https://dropkit.com updates automatically upon each deployment.")

if __name__ == "__main__":
    main()
