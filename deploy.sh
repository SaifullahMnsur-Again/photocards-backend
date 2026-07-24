#!/bin/bash
set -e

APP_DIR="/var/www/photocards-backend"
WEIGHTS_DIR="$APP_DIR/app/weights"
STORAGE_BASE="https://storage.saifullahmnsur.dev/download"

echo "🚀 Starting Production Server Deployment..."

cd "$APP_DIR" || { echo "❌ Failed to enter directory $APP_DIR"; exit 1; }

# Ensure local weights directory exists
mkdir -p "$WEIGHTS_DIR"

echo "📦 Checking and Synchronizing Model Weights & Scaler Artifacts..."

# 1. Stage 0: Gatekeeper EfficientNet-B3 ONNX (Photocard vs Non-Photocard)
if [ -f "$WEIGHTS_DIR/server_gate_efficientnet_b3.onnx" ]; then
    echo "  [✔] server_gate_efficientnet_b3.onnx found locally."
else
    echo "  [*] Downloading Stage 0 Gatekeeper ONNX model..."
    curl -sL -o "$WEIGHTS_DIR/server_gate_efficientnet_b3.onnx" "$STORAGE_BASE/phase1_research_artifacts/server_gate_efficientnet_b3.onnx" || true
    echo "  [+] Saved Gatekeeper ONNX model!"
fi

# 2. Stage 1: RT-DETR Layout Region Detector ONNX (125 MB)
if [ -f "$WEIGHTS_DIR/rtdetr_best.onnx" ]; then
    echo "  [✔] rtdetr_best.onnx found locally."
else
    echo "  [*] Downloading RT-DETR Layout Detector ONNX model..."
    curl -sL -o "$WEIGHTS_DIR/rtdetr_best.onnx" "$STORAGE_BASE/rtdetr_complete_artifacts/models/rtdetr_best.onnx"
    echo "  [+] Saved RT-DETR ONNX model!"
fi

# 3. Stage 3: Multimodal Photocard Classifier ONNX (15.61 MB)
if [ -f "$WEIGHTS_DIR/photocard_classifier.onnx" ]; then
    echo "  [✔] photocard_classifier.onnx found locally."
else
    echo "  [*] Downloading Multimodal Classifier ONNX model..."
    curl -sL -o "$WEIGHTS_DIR/photocard_classifier.onnx" "$STORAGE_BASE/multimodal_classifier_artifacts/models/photocard_classifier.onnx"
    echo "  [+] Saved Multimodal Classifier ONNX model!"
fi

# 4. Feature Scaler Config (ocr_scaler.json)
if [ -f "$WEIGHTS_DIR/ocr_scaler.json" ]; then
    echo "  [✔] ocr_scaler.json found locally."
else
    echo "  [*] Downloading Tabular Feature Scaler config..."
    curl -sL -o "$WEIGHTS_DIR/ocr_scaler.json" "$STORAGE_BASE/multimodal_classifier_artifacts/metrics/ocr_scaler.json"
    echo "  [+] Saved ocr_scaler.json!"
fi

echo "📥 Pulling latest codebase from GitHub main branch..."
git fetch origin main
git reset --hard origin/main

echo "📦 Upgrading pip and installing Python dependencies..."
source "$APP_DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

echo "🔄 Reloading systemd and restarting backend service..."
systemctl daemon-reload
systemctl restart photocards

echo "✅ Deployment completed successfully!"