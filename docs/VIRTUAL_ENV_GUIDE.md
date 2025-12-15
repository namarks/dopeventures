# Virtual Environment Guide

## How to Check Your Virtual Environment

### Method 1: Check if One is Active

```bash
echo $VIRTUAL_ENV
```

If it shows a path, you have one active. If it's empty, you don't.

### Method 2: Check Your Command Prompt

If your prompt shows `(venv)` or `(dopetracks_env)` at the beginning, you have one active:
```
(venv) nmarks@Nicks-MacBook-Pro dopeventures %
```

### Method 3: Check Which Python You're Using

```bash
which python3
```

- If it shows `/path/to/venv/bin/python3` → Virtual env is active
- If it shows `/usr/bin/python3` or `/usr/local/bin/python3` → No virtual env

## Finding Your Virtual Environment

### Check Common Locations

```bash
# Check project root
ls -la | grep venv

# Check if you have the external venv mentioned in README
ls -la /Users/nmarks/root_code_repo/venvs/dopetracks_env 2>/dev/null && echo "Found external venv" || echo "External venv not found"
```

## Setting Up a Virtual Environment

### Option 1: Create One in Project (Recommended)

```bash
# From project root
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Option 2: Use External Venv (If You Prefer)

```bash
# Create external venv
python3 -m venv /Users/nmarks/root_code_repo/venvs/dopetracks_env

# Activate it
source /Users/nmarks/root_code_repo/venvs/dopetracks_env/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Activating Your Virtual Environment

### If it's in project root:
```bash
source venv/bin/activate
```

### If it's external:
```bash
source /Users/nmarks/root_code_repo/venvs/dopetracks_env/bin/activate
```

### Verify it's active:
```bash
which python3  # Should show path to venv
echo $VIRTUAL_ENV  # Should show venv path
```

## Deactivating

```bash
deactivate
```

## Quick Setup Script

Run this to set everything up:

```bash
#!/bin/bash
# Setup script for Dopetracks

# Check if venv exists, if not create it
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

echo "✅ Setup complete!"
echo "To start the app, run: python3 start_multiuser.py"
```

Save as `setup.sh` and run: `bash setup.sh`
