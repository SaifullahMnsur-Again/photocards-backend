#!/bin/bash
set -e  # Exit immediately if any command fails

echo "🚀 Starting Automated Server Deployment..."

# 1. Navigate to project root
cd /home/ubuntu/photocards-backend

# 2. Pull latest code from GitHub
echo "📥 Pulling latest updates from GitHub..."
git pull origin main

# 3. Activate virtual environment & install dependencies
echo "📦 Installing/updating dependencies in virtual environment..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Run CSV Migration (Safely imports legacy data if any remains)
echo "🔄 Running MongoDB migration check..."
python migrate_csv.py

# 5. Reload systemd daemon & restart FastAPI backend
echo "🔄 Reloading systemd and restarting backend service..."
sudo systemctl daemon-reload
sudo systemctl restart fastapi_collector

echo "✅ Deployment completed successfully!"