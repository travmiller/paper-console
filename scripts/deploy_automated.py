#!/usr/bin/env python3
"""
Automated deployment script for PC-1 Paper Console
Designed for use by AI agents to commit and deploy changes automatically.

Usage:
    python scripts/deploy_automated.py [--message "commit message"] [--skip-commit]
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path

# Configuration file path
CONFIG_FILE = Path(".deploy_config")

def load_config():
    """Load deployment configuration from .deploy_config file."""
    config = {
        "PI_HOST": "pc-1.local",
        "PI_USER": "admin",
        "PI_PATH": "~/paper-console",
        "RESTART_SERVICE": "true",
        "BRANCH": "main"
    }
    
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"\'')
                    if key in config:
                        config[key] = value
    
    return config

def run_command(cmd, check=True, capture_output=False):
    """Run a shell command and return the result."""
    print(f"[*] Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            check=check,
            capture_output=capture_output,
            text=True
        )
        if capture_output:
            return result.stdout.strip()
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"[X] Command failed: {e}")
        if capture_output and e.stdout:
            print(f"   Output: {e.stdout}")
        if capture_output and e.stderr:
            print(f"   Error: {e.stderr}")
        raise

def check_git_status():
    """Check if there are uncommitted changes."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

def get_current_branch():
    """Get the current git branch."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

def commit_changes(message):
    """Commit all changes with the given message."""
    # Check if there are changes to commit
    status = check_git_status()
    if not status:
        print("[i] No changes to commit")
        return False
    
    print(f"[*] Committing changes: {message}")
    
    # Stage all changes
    run_command(["git", "add", "-A"])
    
    # Commit
    run_command(["git", "commit", "-m", message])
    
    return True

def push_to_remote(branch):
    """Push changes to remote repository."""
    print(f"[*] Pushing to origin/{branch}...")
    run_command(["git", "push", "origin", branch])
    print("[OK] Successfully pushed to remote")
    return True

def deploy_to_pi(config):
    """Deploy changes to Raspberry Pi."""
    pi_host = config["PI_HOST"]
    pi_user = config["PI_USER"]
    pi_path = config["PI_PATH"]
    branch = config["BRANCH"]
    restart_service = config["RESTART_SERVICE"].lower() == "true"
    
    print(f"\n[*] Connecting to {pi_user}@{pi_host}...")
    
    # Test SSH connection
    ssh_test_cmd = [
        "ssh",
        "-o", "ConnectTimeout=5",
        "-o", "BatchMode=yes",
        f"{pi_user}@{pi_host}",
        "exit"
    ]
    
    try:
        run_command(ssh_test_cmd, check=False)
    except Exception:
        print(f"[X] Cannot connect to {pi_user}@{pi_host}")
        print("   Make sure:")
        print("   1. The Pi is powered on and connected to the network")
        print("   2. SSH is enabled on the Pi")
        print("   3. Your SSH key is authorized")
        print("   4. The hostname/IP is correct")
        return False
    
    print("[OK] SSH connection successful")
    
    # Pull changes on Pi
    print(f"\n[*] Pulling changes on {pi_host}...")
    pull_cmd = [
        "ssh",
        f"{pi_user}@{pi_host}",
        f"cd {pi_path} && git pull origin {branch}"
    ]
    
    try:
        run_command(pull_cmd)
        print("[OK] Successfully pulled changes on Pi")
    except Exception:
        print("[X] Failed to pull changes on Pi")
        return False
    
    # Restart service if requested
    if restart_service:
        print("\n[*] Restarting pc-1.service...")
        restart_cmd = [
            "ssh",
            f"{pi_user}@{pi_host}",
            "sudo systemctl restart pc-1.service"
        ]
        
        try:
            run_command(restart_cmd)
            print("[OK] Service restarted")
            
            # Check status
            print("\n[*] Service status:")
            status_cmd = [
                "ssh",
                f"{pi_user}@{pi_host}",
                "sudo systemctl status pc-1.service --no-pager -l"
            ]
            run_command(status_cmd, check=False)
        except Exception:
            print("[!] Failed to restart service (may need manual intervention)")
    
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Automated deployment script for PC-1 Paper Console"
    )
    parser.add_argument(
        "--message", "-m",
        help="Commit message (required if committing)",
        default=None
    )
    parser.add_argument(
        "--skip-commit",
        action="store_true",
        help="Skip committing changes (only push and deploy)"
    )
    parser.add_argument(
        "--skip-push",
        action="store_true",
        help="Skip pushing to remote (only deploy existing commits)"
    )
    parser.add_argument(
        "--skip-deploy",
        action="store_true",
        help="Skip deployment to Pi (only commit and push)"
    )
    
    args = parser.parse_args()
    
    print("==========================================")
    print("  PC-1 Automated Deployment")
    print("==========================================")
    print()
    
    # Load configuration
    config = load_config()
    branch = config["BRANCH"]
    current_branch = get_current_branch()
    
    print(f"Current branch: {current_branch}")
    print(f"Target branch: {branch}")
    print(f"Pi Host: {config['PI_HOST']}")
    print()
    
    if current_branch != branch:
        print(f"[!] Warning: You're on branch '{current_branch}', not '{branch}'")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Deployment cancelled.")
            return 1
    
    # Commit changes if requested
    committed = False
    if not args.skip_commit:
        if not args.message:
            print("[X] Error: --message is required when committing")
            print("   Use --skip-commit to skip committing")
            return 1
        
        committed = commit_changes(args.message)
    
    # Push to remote if requested
    if not args.skip_push:
        if committed or check_git_status():
            # Check if there are commits to push
            try:
                run_command(["git", "push", "origin", branch])
                print("[OK] Successfully pushed to remote")
            except Exception:
                print("[!] No new commits to push or push failed")
        else:
            print("[i] No commits to push")
    
    # Deploy to Pi if requested
    if not args.skip_deploy:
        if deploy_to_pi(config):
            print("\n==========================================")
            print("  [OK] Deployment Complete!")
            print("==========================================")
            print(f"\nYour Pi should now be running the latest code.")
            print(f"Access it at: http://{config['PI_HOST']}")
        else:
            print("\n[X] Deployment failed")
            return 1
    else:
        print("\n[OK] Commit and push complete (deployment skipped)")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
