# app/core/models_loader.py
import os
import json
import torch
import easyocr
from ultralytics import RTDETR
from app.config import MEDIA_DIR

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "../weights")
os.makedirs(WEIGHTS_DIR, exist_ok=True)

RTDETR_PATH = os.path.join(WEIGHTS_DIR, "rtdetr_best.pt")
SCALER_PATH = os.path.join(WEIGHTS_DIR, "ocr_scaler.json")

print("[*] Loading RT-DETR Detection Model...")
rtdetr_model = RTDETR(RTDETR_PATH) if os.path.exists(RTDETR_PATH) else None

print("[*] Initializing EasyOCR Engine...")
ocr_reader = easyocr.Reader(['bn', 'en'], gpu=torch.cuda.is_available())

ocr_scaler = None
if os.path.exists(SCALER_PATH):
    with open(SCALER_PATH, "r") as f:
        ocr_scaler = json.load(f)

# Load multimodal classifier model
classifier_model = None
# Instantiate and load model weights from export_bundle if present