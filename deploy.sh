#!/bin/bash
set -e

echo "🚀 Starting Automated Server Deployment..."

cd /home/ubuntu/photocards-backend

echo "📥 Pulling latest updates from GitHub..."
git pull origin main

echo "📦 Installing/updating dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "🔄 Running MongoDB migration check..."
python migrate_csv.py

echo "🔄 Reloading systemd and restarting backend service..."
sudo systemctl daemon-reload
sudo systemctl restart fastapi_collector

echo "✅ Deployment completed successfully!"