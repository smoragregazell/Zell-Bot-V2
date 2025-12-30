#!/bin/bash

# Zell-Bot Redeploy Service Setup Script
# Run this script after cloning the repository
# This script automatically cleans up any existing services

set -e

echo "🚀 Setting up Zell-Bot Redeploy Service..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "📁 Working directory: $SCRIPT_DIR"

# Check if required files exist
if [ ! -f "$SCRIPT_DIR/redeploy-service-host.py" ]; then
    echo "❌ redeploy-service-host.py not found in $SCRIPT_DIR"
    echo "   Please run this script from the Zell-Bot directory"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/redeploy.sh" ]; then
    echo "❌ redeploy.sh not found in $SCRIPT_DIR"
    echo "   Please run this script from the Zell-Bot directory"
    exit 1
fi

# Clean up any existing zell-bot-redeploy service
echo "🧹 Cleaning up any existing zell-bot-redeploy service..."
if systemctl is-active --quiet zell-bot-redeploy 2>/dev/null; then
    echo "   Stopping existing zell-bot-redeploy service..."
    systemctl stop zell-bot-redeploy
fi

if systemctl is-enabled --quiet zell-bot-redeploy 2>/dev/null; then
    echo "   Disabling existing zell-bot-redeploy service..."
    systemctl disable zell-bot-redeploy
fi

# Remove old systemd service file if it exists
if [ -f "/etc/systemd/system/zell-bot-redeploy.service" ]; then
    echo "   Removing old systemd service file..."
    rm -f /etc/systemd/system/zell-bot-redeploy.service
fi

echo "✅ Cleanup complete!"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install fastapi uvicorn python-dotenv

# Ask for GitHub webhook secret
echo ""
echo "🔐 GitHub Webhook Configuration"
echo "================================"
read -p "Enter your GitHub webhook secret: " GITHUB_WEBHOOK_SECRET

if [ -z "$GITHUB_WEBHOOK_SECRET" ]; then
    echo "❌ Webhook secret cannot be empty"
    exit 1
fi

# Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x "$SCRIPT_DIR/redeploy.sh"
chmod +x "$SCRIPT_DIR/redeploy-service-host.py"

# Create wrapper script for dynamic path resolution
echo "🔧 Creating wrapper script for dynamic paths..."
cat > "$SCRIPT_DIR/redeploy-service-wrapper.sh" << 'EOF'
#!/bin/bash

# Wrapper script for Zell-Bot redeploy service that finds the script location dynamically
# This allows the systemd service to work from any location

# Get the directory where this wrapper script is located
WRAPPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to that directory and run the Python script
cd "$WRAPPER_DIR"
exec /usr/bin/python3 "$WRAPPER_DIR/redeploy-service-host.py"
EOF

chmod +x "$SCRIPT_DIR/redeploy-service-wrapper.sh"

# Create systemd service that uses the wrapper (completely dynamic)
echo "🔧 Setting up systemd service with completely dynamic paths..."
cat > /etc/systemd/system/zell-bot-redeploy.service << EOF
[Unit]
Description=Zell-Bot Redeploy Service
After=network.target

[Service]
Type=simple
User=root
ExecStart=$SCRIPT_DIR/redeploy-service-wrapper.sh
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1
Environment=GITHUB_WEBHOOK_SECRET=$GITHUB_WEBHOOK_SECRET

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Systemd service created with completely dynamic paths:"
echo "   ExecStart: $SCRIPT_DIR/redeploy-service-wrapper.sh"
echo "   Wrapper script finds Python script location dynamically"
echo "   Python script calculates all paths from its location"

# Reload systemd and start service
echo "🔧 Starting systemd service..."
systemctl daemon-reload
systemctl enable zell-bot-redeploy
systemctl start zell-bot-redeploy

# Check service status
echo "📊 Checking service status..."
systemctl status zell-bot-redeploy --no-pager

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Configure GitHub webhook: http://your-server-ip:8002/webhook"
echo "2. Use the same webhook secret you just entered: $GITHUB_WEBHOOK_SECRET"
echo "3. Test with: curl http://localhost:8002/health"
echo ""
echo "📊 Useful commands:"
echo "- View logs: journalctl -u zell-bot-redeploy -f"
echo "- Check status: systemctl status zell-bot-redeploy"
echo "- Restart service: systemctl restart zell-bot-redeploy"
echo ""
echo "🔄 This script automatically cleans up any existing services,"
echo "   so you can safely run it from any location!"
