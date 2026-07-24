#!/bin/bash
set -e

APP_DIR="/var/www/photocards-backend"
WEIGHTS_DIR="$APP_DIR/app/weights"
STORAGE_BASE="https://storage.saifullahmnsur.dev/download"

echo "🚀 Starting Full Production Deployment..."

cd "$APP_DIR" || { echo "❌ Failed to enter directory $APP_DIR"; exit 1; }

mkdir -p "$WEIGHTS_DIR"

echo "📦 1/4 Checking & Downloading ONNX Model Artifacts..."

# Stage 0: Gatekeeper EfficientNet-B3 ONNX
if [ ! -f "$WEIGHTS_DIR/server_gate_efficientnet_b3.onnx" ]; then
    echo "  [*] Downloading server_gate_efficientnet_b3.onnx..."
    curl -sL -o "$WEIGHTS_DIR/server_gate_efficientnet_b3.onnx" "$STORAGE_BASE/phase1_research_artifacts/server_gate_efficientnet_b3.onnx"
fi

# Stage 1: RT-DETR Region Detector ONNX
if [ ! -f "$WEIGHTS_DIR/rtdetr_best.onnx" ]; then
    echo "  [*] Downloading rtdetr_best.onnx..."
    curl -sL -o "$WEIGHTS_DIR/rtdetr_best.onnx" "$STORAGE_BASE/rtdetr_complete_artifacts/models/rtdetr_best.onnx"
fi

# Stage 3: Multimodal Classifier ONNX
if [ ! -f "$WEIGHTS_DIR/photocard_classifier.onnx" ]; then
    echo "  [*] Downloading photocard_classifier.onnx..."
    curl -sL -o "$WEIGHTS_DIR/photocard_classifier.onnx" "$STORAGE_BASE/multimodal_classifier_artifacts/models/photocard_classifier.onnx"
fi

# Scaler Config
if [ ! -f "$WEIGHTS_DIR/ocr_scaler.json" ]; then
    echo "  [*] Downloading ocr_scaler.json..."
    curl -sL -o "$WEIGHTS_DIR/ocr_scaler.json" "$STORAGE_BASE/multimodal_classifier_artifacts/metrics/ocr_scaler.json"
fi

echo "📥 2/4 Pulling latest Git updates..."
git fetch origin main
git reset --hard origin/main

echo "📦 3/4 Installing Python requirements..."
source "$APP_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

echo "🔄 4/4 Restarting System Services..."
systemctl daemon-reload
systemctl restart photocards
systemctl restart nginx

echo "✅ Deployment & Restoration Complete! System is LIVE."