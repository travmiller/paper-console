# Deployment Workflow Documentation

This document describes the automated deployment workflow for PC-1 Paper Console, designed to allow AI agents and developers to easily commit changes locally and deploy them to a Raspberry Pi.

## Overview

The deployment system consists of three main components:

1. **`deploy.sh`** / **`deploy.bat`** - Enhanced shell scripts for manual deployment
2. **`scripts/deploy_automated.py`** - Python script designed for AI agent automation
3. **`.deploy_config`** - Configuration file for Pi connection details (gitignored)

## Quick Start

### 1. Initial Setup

First, copy the example configuration file and customize it for your Pi:

```bash
cp .deploy_config.example .deploy_config
```

Edit `.deploy_config` with your Pi's details:

```bash
PI_HOST=pc-1.local          # Your Pi's hostname or IP
PI_USER=admin              # SSH username
PI_PATH=~/paper-console    # Path to project on Pi
BRANCH=main                # Git branch to deploy
RESTART_SERVICE=true       # Whether to restart service after deployment
```

### 2. SSH Setup

Ensure you have passwordless SSH access to your Pi:

```bash
# Generate SSH key if you don't have one
ssh-keygen -t ed25519 -C "your_email@example.com"

# Copy your public key to the Pi
ssh-copy-id admin@pc-1.local

# Test the connection
ssh admin@pc-1.local
```

### 3. Using the Deployment Scripts

#### Manual Deployment (Linux/macOS/Git Bash)

```bash
./deploy.sh
```

#### Manual Deployment (Windows)

```cmd
deploy.bat
```

#### Automated Deployment (AI Agent / Python)

```bash
# Commit, push, and deploy
python scripts/deploy_automated.py --message "Your commit message"

# Skip committing (only push and deploy)
python scripts/deploy_automated.py --skip-commit

# Only commit and push (skip Pi deployment)
python scripts/deploy_automated.py --message "Your commit message" --skip-deploy
```

## AI Agent Usage

The `deploy_automated.py` script is designed for AI agents to use programmatically. It provides:

- **Automatic committing** with a provided message
- **Error handling** and status reporting
- **Flexible options** to skip steps if needed
- **Configuration loading** from `.deploy_config`

### Example AI Agent Workflow

When an AI agent makes changes and wants to deploy:

```python
# The AI agent can call:
python scripts/deploy_automated.py --message "Add new feature X"
```

This will:
1. Stage all changes (`git add -A`)
2. Commit with the provided message
3. Push to the remote repository
4. SSH into the Pi and pull changes
5. Restart the pc-1.service
6. Report status

## Workflow Details

### Step-by-Step Process

1. **Commit Changes** (optional)
   - Stages all changes (`git add -A`)
   - Creates a commit with the provided message

2. **Push to Remote**
   - Pushes commits to `origin/<branch>`
   - Verifies push was successful

3. **SSH Connection Test**
   - Tests SSH connectivity to the Pi
   - Validates credentials and network access

4. **Pull on Pi**
   - SSHs into the Pi
   - Changes to the project directory
   - Runs `git pull origin <branch>`

5. **Service Restart** (optional)
   - Restarts `pc-1.service` via systemctl
   - Checks service status

### Error Handling

The scripts include comprehensive error handling:

- **Uncommitted changes**: Warns before proceeding
- **Branch mismatch**: Warns if not on the expected branch
- **SSH failures**: Provides troubleshooting guidance
- **Git failures**: Stops deployment and reports errors
- **Service restart failures**: Reports but doesn't fail deployment

## Configuration Options

### `.deploy_config` Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PI_HOST` | `pc-1.local` | Raspberry Pi hostname or IP address |
| `PI_USER` | `admin` | SSH username for Pi |
| `PI_PATH` | `~/paper-console` | Path to project directory on Pi |
| `BRANCH` | `main` | Git branch to deploy |
| `RESTART_SERVICE` | `true` | Whether to restart pc-1.service after deployment |

### Command-Line Options (deploy_automated.py)

| Option | Description |
|--------|-------------|
| `--message`, `-m` | Commit message (required if committing) |
| `--skip-commit` | Skip committing changes |
| `--skip-push` | Skip pushing to remote |
| `--skip-deploy` | Skip deployment to Pi |

## Troubleshooting

### SSH Connection Issues

**Problem**: Cannot connect to Pi
- Verify Pi is powered on and on the network
- Check hostname/IP is correct: `ping pc-1.local`
- Ensure SSH is enabled: `sudo systemctl status ssh`
- Verify SSH key is authorized: `ssh admin@pc-1.local`

### Git Push Issues

**Problem**: Push fails
- Check you have write access to the repository
- Verify remote is configured: `git remote -v`
- Ensure you're authenticated with GitHub

### Service Restart Issues

**Problem**: Service won't restart
- Check service exists: `ssh admin@pc-1.local "systemctl list-units | grep pc-1"`
- Verify sudo permissions: `ssh admin@pc-1.local "sudo -n systemctl restart pc-1.service"`
- Check service logs: `ssh admin@pc-1.local "sudo journalctl -u pc-1.service -n 50"`

### Permission Issues

**Problem**: Permission denied errors
- Ensure user is in required groups: `groups`
- Check file permissions on Pi: `ls -la ~/paper-console`
- Verify sudoers configuration (see `scripts/setup_pi.sh`)

## Security Considerations

1. **SSH Keys**: Use SSH key authentication instead of passwords
2. **Config File**: `.deploy_config` is gitignored and should not be committed
3. **Sudo Access**: The Pi user should have passwordless sudo for service management (configured by `setup_pi.sh`)
4. **Network**: Ensure your network is secure, especially if deploying over the internet

## Integration with CI/CD

For more advanced workflows, you can integrate these scripts with CI/CD systems:

- **GitHub Actions**: Use SSH actions to deploy after tests pass
- **GitLab CI**: Add deployment jobs that SSH into the Pi
- **Local Hooks**: Use git hooks to trigger deployments automatically

## Best Practices

1. **Test Locally First**: Always test changes locally before deploying
2. **Commit Messages**: Use descriptive commit messages
3. **Branch Strategy**: Deploy from stable branches (main/master)
4. **Backup Config**: Keep `config.json` backed up (it's gitignored)
5. **Monitor Logs**: Check service logs after deployment: `sudo journalctl -u pc-1.service -f`

## Examples

### Deploy a Feature

```bash
# Make changes, then:
python scripts/deploy_automated.py --message "Add weather module improvements"
```

### Deploy Without Committing

```bash
# If changes are already committed:
python scripts/deploy_automated.py --skip-commit
```

### Deploy to Different Pi

```bash
# Temporarily override config:
PI_HOST=192.168.1.100 python scripts/deploy_automated.py --message "Deploy to test Pi"
```

### Manual Deployment with Confirmation

```bash
# Use the shell script for interactive deployment:
./deploy.sh
```
