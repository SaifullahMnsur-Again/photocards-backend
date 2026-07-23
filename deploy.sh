#!/bin/bash
set -e

APP_DIR="/var/www/photocards-backend"

echo "🚀 Starting Automated Server Deployment..."

cd "$APP_DIR" || { echo "❌ Failed to enter directory $APP_DIR"; exit 1; }

echo "📥 Pulling latest updates from GitHub..."
git fetch origin main
git reset --hard origin/main

echo "📦 Installing/updating dependencies..."
source "$APP_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

echo "🔄 Reloading systemd and restarting backend service..."
systemctl daemon-reload
systemctl restart photocards

echo "✅ Deployment completed successfully!"