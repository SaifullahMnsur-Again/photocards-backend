import os
import json
import onnxruntime as ort
import easyocr
from app.config import WEIGHTS_DIR

print("[*] Loading Photocard Pipeline Models...")

# 1. Gatekeeper ONNX
GATE_MODEL_PATH = os.path.join(WEIGHTS_DIR, "server_gate_efficientnet_b3.onnx")
gate_session = None
if os.path.exists(GATE_MODEL_PATH):
    try:
        gate_session = ort.InferenceSession(GATE_MODEL_PATH, providers=['CPUExecutionProvider'])
        print("[+] Gatekeeper ONNX Loaded.")
    except Exception as e:
        print(f"[!] Gatekeeper ONNX Load Failed: {e}")

# 2. RT-DETR Model
RTDETR_PT_PATH = os.path.join(WEIGHTS_DIR, "rtdetr_best.pt")
RTDETR_ONNX_PATH = os.path.join(WEIGHTS_DIR, "rtdetr_best.onnx")
rtdetr_model = None

try:
    if os.path.exists(RTDETR_PT_PATH):
        from ultralytics import RTDETR
        rtdetr_model = RTDETR(RTDETR_PT_PATH)
        print(f"[+] RT-DETR PyTorch Model Loaded from {RTDETR_PT_PATH}")
    elif os.path.exists(RTDETR_ONNX_PATH):
        from ultralytics import RTDETR
        rtdetr_model = RTDETR(RTDETR_ONNX_PATH)
        print(f"[+] RT-DETR ONNX Model Loaded from {RTDETR_ONNX_PATH}")
    else:
        print(f"[!] RT-DETR weights missing.")
except Exception as e:
        print(f"[!] RT-DETR Load Failed: {e}")

# 3. EasyOCR Reader
ocr_reader = None
try:
    ocr_reader = easyocr.Reader(['bn', 'en'], gpu=False)
    print("[+] EasyOCR Reader Loaded.")
except Exception as e:
    print(f"[!] EasyOCR Load Failed: {e}")

# 4. Multimodal Classifier ONNX & Scaler
CLASSIFIER_PATH = os.path.join(WEIGHTS_DIR, "photocard_classifier.onnx")
SCALER_PATH = os.path.join(WEIGHTS_DIR, "ocr_scaler.json")

classifier_session = None
if os.path.exists(CLASSIFIER_PATH):
    try:
        classifier_session = ort.InferenceSession(CLASSIFIER_PATH, providers=['CPUExecutionProvider'])
        print("[+] Multimodal Classifier Loaded.")
    except Exception as e:
        print(f"[!] Classifier Load Failed: {e}")

ocr_scaler = {}
if os.path.exists(SCALER_PATH):
    try:
        with open(SCALER_PATH, "r") as f:
            ocr_scaler = json.load(f)
        print("[+] Tabular Scaler Loaded.")
    except Exception as e:
        print(f"[!] Scaler JSON Load Failed: {e}")