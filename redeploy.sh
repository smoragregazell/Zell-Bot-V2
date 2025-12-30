#!/bin/bash

# Redeploy script for Zell-Bot
# Fetches latest changes from current branch and rebuilds Docker containers

set -e  # Exit on any error

echo "🚀 Starting Zell-Bot redeploy process..."

# Get the current branch name
CURRENT_BRANCH=$(git branch --show-current)
echo "📋 Current branch: $CURRENT_BRANCH"

# Fetch latest changes from the current branch
echo "📥 Fetching latest changes from origin/$CURRENT_BRANCH..."
git fetch origin "$CURRENT_BRANCH"

# Pull the latest changes
echo "⬇️  Pulling latest changes..."
git pull origin "$CURRENT_BRANCH"

# Stop and remove existing containers
echo "🛑 Stopping and removing existing containers..."
docker compose down

# Remove the existing image to force a fresh build
echo "🗑️  Removing existing image..."
docker rmi zell-bot:latest 2>/dev/null || echo "Image not found, continuing..."

# Build the new image
echo "🔨 Building new Docker image..."
docker compose build --no-cache

# Start the containers
echo "▶️  Starting containers..."
docker compose up -d

# Show container status
echo "📊 Container status:"
docker compose ps

echo "✅ Zell-Bot redeploy completed successfully!"
