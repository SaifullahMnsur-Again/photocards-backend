#!/bin/bash
echo "🚀 Deploying latest code from GitHub..."
cd /home/ubuntu/photocards-backend
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart fastapi_collector
echo "✅ Deployment completed successfully!"