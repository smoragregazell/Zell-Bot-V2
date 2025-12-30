#!/usr/bin/env python3
"""
Redeploy service for GitHub webhooks - Zell-Bot version.
Runs directly on the host instead of in a Docker container.
"""

import os
import hmac
import hashlib
import subprocess
import json
import sys
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
import uvicorn

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.absolute()

app = FastAPI(title="Zell-Bot Redeploy Service", version="1.0.0")

# Configuration - webhook secret comes from systemd environment variable
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
REDEPLOY_SCRIPT_PATH = str(SCRIPT_DIR / "redeploy.sh")
PROJECT_DIR = str(SCRIPT_DIR)

def verify_github_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature using HMAC-SHA256."""
    if not signature or not secret:
        return False
    
    # Remove 'sha256=' prefix if present
    if signature.startswith('sha256='):
        signature = signature[7:]
    
    # Create expected signature
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(signature, expected_signature)

def get_current_branch() -> str:
    """Get the current git branch name."""
    try:
        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True,
            text=True,
            check=True,
            cwd=PROJECT_DIR
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get current branch: {e}")

def execute_redeploy() -> dict:
    """Execute the redeploy script on the host."""
    try:
        print(f"DEBUG: Executing redeploy script: {REDEPLOY_SCRIPT_PATH}")
        result = subprocess.run(
            ['bash', REDEPLOY_SCRIPT_PATH],
            capture_output=True,
            text=True,
            check=True,
            cwd=PROJECT_DIR
        )
        print(f"DEBUG: Redeploy completed successfully")
        return {
            "success": True,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        }
    except subprocess.CalledProcessError as e:
        print(f"DEBUG: Redeploy failed with return code {e.returncode}")
        print(f"DEBUG: stderr: {e.stderr}")
        return {
            "success": False,
            "stdout": e.stdout,
            "stderr": e.stderr,
            "return_code": e.returncode
        }

@app.post("/webhook")
async def webhook(request: Request):
    """Single endpoint for GitHub webhooks."""
    
    # Get headers and body
    event = request.headers.get("X-GitHub-Event", "unknown")
    signature = request.headers.get("X-Hub-Signature-256", "")
    body = await request.body()
    
    print(f"DEBUG: Received webhook - Event: {event}")
    print(f"DEBUG: Signature header: {signature}")
    
    # Check webhook secret
    if not GITHUB_WEBHOOK_SECRET:
        print("DEBUG: No webhook secret configured")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    
    # Verify signature
    if not verify_github_signature(body, signature, GITHUB_WEBHOOK_SECRET):
        print(f"DEBUG: Signature verification failed")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse webhook payload
    try:
        payload = json.loads(body.decode('utf-8'))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    # Handle push events
    if event == "push":
        print(f"DEBUG: Processing push event")
        try:
            # Get current branch
            current_branch = get_current_branch()
            print(f"DEBUG: Current branch: {current_branch}")
            
            # Get pushed branch from payload
            pushed_branch = payload.get("ref", "").replace("refs/heads/", "")
            print(f"DEBUG: Pushed branch: {pushed_branch}")
            
            # Only redeploy if push is to current branch
            if pushed_branch == current_branch:
                print(f"DEBUG: Branch match! Executing redeploy...")
                # Execute redeploy
                redeploy_result = execute_redeploy()
                print(f"DEBUG: Redeploy result: {redeploy_result}")
                
                if redeploy_result["success"]:
                    return {"status": "success", "message": "Redeploy completed", "output": redeploy_result["stdout"]}
                else:
                    return {"status": "error", "message": "Redeploy failed", "details": redeploy_result["stderr"]}
            else:
                print(f"DEBUG: Branch mismatch - ignoring push to {pushed_branch}, current is {current_branch}")
                return {"status": "ignored", "message": f"Push to {pushed_branch}, current branch is {current_branch}"}
                
        except Exception as e:
            print(f"DEBUG: Exception during redeploy: {str(e)}")
            return {"status": "error", "message": f"Error during redeploy: {str(e)}"}
    
    return {"status": "ignored", "message": f"Event {event} not handled"}

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "zell-bot-redeploy"}

@app.post("/test-webhook")
async def test_webhook(request: Request):
    """Test endpoint that bypasses signature verification."""
    body = await request.body()
    try:
        payload = json.loads(body.decode('utf-8'))
        return {"status": "success", "message": "Test webhook received", "payload": payload}
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON payload"}

if __name__ == "__main__":
    print(f"Starting Zell-Bot redeploy service on host...")
    print(f"Script directory: {SCRIPT_DIR}")
    print(f"Project directory: {PROJECT_DIR}")
    print(f"Redeploy script: {REDEPLOY_SCRIPT_PATH}")
    print(f"GitHub webhook secret configured: {bool(GITHUB_WEBHOOK_SECRET)}")
    
    uvicorn.run(app, host="0.0.0.0", port=8002)
