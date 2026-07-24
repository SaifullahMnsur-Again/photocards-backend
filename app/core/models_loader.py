import os
import json
import onnxruntime as ort
import easyocr
from ultralytics import RTDETR
from app.config import WEIGHTS_DIR

print("[*] Loading Photocard Pipeline Models...")

# 1. Gatekeeper ONNX
GATE_MODEL_PATH = os.path.join(WEIGHTS_DIR, "server_gate_efficientnet_b3.onnx")
gate_session = None
if os.path.exists(GATE_MODEL_PATH):
    gate_session = ort.InferenceSession(GATE_MODEL_PATH, providers=['CPUExecutionProvider'])
    print("[+] Gatekeeper ONNX Loaded.")

# 2. RT-DETR PyTorch / ONNX
RTDETR_PATH = os.path.join(WEIGHTS_DIR, "rtdetr_best.pt") # or rtdetr_best.onnx
rtdetr_model = None
if os.path.exists(RTDETR_PATH):
    rtdetr_model = RTDETR(RTDETR_PATH)
    print("[+] RT-DETR Region Detector Loaded.")

# 3. EasyOCR Reader
ocr_reader = None
try:
    ocr_reader = easyocr.Reader(['bn', 'en'], gpu=False)
    print("[+] EasyOCR Reader Loaded.")
except Exception as e:
    print(f"[!] EasyOCR Load Error: {e}")

# 4. Multimodal Classifier ONNX & Scaler
CLASSIFIER_PATH = os.path.join(WEIGHTS_DIR, "photocard_classifier.onnx")
SCALER_PATH = os.path.join(WEIGHTS_DIR, "ocr_scaler.json")

classifier_session = None
if os.path.exists(CLASSIFIER_PATH):
    classifier_session = ort.InferenceSession(CLASSIFIER_PATH, providers=['CPUExecutionProvider'])
    print("[+] Multimodal Classifier Loaded.")

ocr_scaler = {}
if os.path.exists(SCALER_PATH):
    with open(SCALER_PATH, "r") as f:
        ocr_scaler = json.load(f)
    print("[+] Tabular Scaler Loaded.")