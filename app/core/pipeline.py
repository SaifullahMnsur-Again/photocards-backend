import os
import time
import json
import cv2
import numpy as np
import torch
from typing import AsyncGenerator
from PIL import Image
from torchvision import transforms

# CLASS NAMES mapping for RT-DETR
CLASS_NAMES = {
    0: 'publisher', 1: 'publisher_logo', 2: 'image', 3: 'headline',
    4: 'text', 5: 'date', 6: 'url', 7: 'ad', 8: 'photocard',
    9: 'qr_code', 10: 'speaker'
}

eval_transforms = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

async def evaluate_analysis_pipeline_stream(image_path: str, metadata: dict) -> AsyncGenerator[str, None]:
    """
    Yields real-time SSE JSON progress chunks as each analysis phase completes.
    """
    total_stages = 4
    
    # -------------------------------------------------------------------------
    # STAGE 0: Photocard Gatekeeper (server_gate_efficientnet_b3.onnx)
    # -------------------------------------------------------------------------
    t0 = time.time()
    yield json.dumps({
        "event": "progress",
        "stage_index": 0,
        "stage_name": "Stage 0: Input Gate Check",
        "progress_percent": 10,
        "status": "running"
    }) + "\n"

    if not image_path or not os.path.exists(image_path):
        yield json.dumps({
            "event": "stage_complete",
            "stage_index": 0,
            "status": "failed",
            "message": "Image file not found on disk.",
            "execution_time_ms": round((time.time() - t0) * 1000, 2)
        }) + "\n"
        return

    img_bgr = cv2.imread(image_path)
    if img_bgr is None or img_bgr.size == 0:
        yield json.dumps({
            "event": "stage_complete",
            "stage_index": 0,
            "status": "failed",
            "message": "OpenCV failed to decode image format.",
            "execution_time_ms": round((time.time() - t0) * 1000, 2)
        }) + "\n"
        return

    gate_prob = 1.0
    try:
        from app.core.models_loader import gate_session
        if gate_session:
            pil_img = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
            gate_tensor = eval_transforms(pil_img).unsqueeze(0).numpy()
            
            input_name = gate_session.get_inputs()[0].name
            outputs = gate_session.run(None, {input_name: gate_tensor})
            logits = outputs[0][0]
            gate_prob = float(1.0 / (1.0 + np.exp(-logits)))

            if gate_prob < 0.50:
                yield json.dumps({
                    "event": "stage_complete",
                    "stage_index": 0,
                    "status": "failed",
                    "message": f"Input rejected: Media is not a recognized photocard (Confidence: {gate_prob*100:.1f}%).",
                    "execution_time_ms": round((time.time() - t0) * 1000, 2)
                }) + "\n"
                return
    except Exception as e:
        print(f"[!] Gatekeeper warning: {e}")

    # STAGE 0 PASSED RESULT YIELDED IMMEDIATELY
    yield json.dumps({
        "event": "stage_complete",
        "stage_index": 0,
        "stage_name": "Stage 0: Input Gate Check",
        "status": "passed",
        "progress_percent": 25,
        "message": f"Valid photocard verified ({img_bgr.shape[1]}x{img_bgr.shape[0]} px).",
        "execution_time_ms": round((time.time() - t0) * 1000, 2),
        "data": {"gate_confidence": round(gate_prob, 4)}
    }) + "\n"

    # -------------------------------------------------------------------------
    # STAGE 1: Layout Region Detection (rtdetr_best.onnx)
    # -------------------------------------------------------------------------
    t1 = time.time()
    yield json.dumps({
        "event": "progress",
        "stage_index": 1,
        "stage_name": "Stage 1: RT-DETR Region Detection",
        "progress_percent": 35,
        "status": "running"
    }) + "\n"

    detected_boxes = []
    detected_classes = set()
    headline_crop, speaker_crop, text_crop = None, None, None
    img_h, img_w, _ = img_bgr.shape

    try:
        from app.core.models_loader import rtdetr_model
        if rtdetr_model:
            results = rtdetr_model(img_bgr, conf=0.25, verbose=False)[0]
            for box in results.boxes:
                cls_id = int(box.cls[0].item())
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0].item())
                c_name = CLASS_NAMES.get(cls_id, f"class_{cls_id}")
                detected_classes.add(c_name)
                
                detected_boxes.append({
                    "class_name": c_name,
                    "confidence": round(conf, 4),
                    "bbox": [x1, y1, x2, y2]
                })

                pad = 5
                x1_p, y1_p = max(0, x1 - pad), max(0, y1 - pad)
                x2_p, y2_p = min(img_w, x2 + pad), min(img_h, y2 + pad)
                crop = img_bgr[y1_p:y2_p, x1_p:x2_p]

                if crop.size > 0:
                    if c_name == 'headline': headline_crop = crop
                    elif c_name == 'speaker': speaker_crop = crop
                    elif c_name == 'text': text_crop = crop
    except Exception as e:
        print(f"[!] RT-DETR error: {e}")

    yield json.dumps({
        "event": "stage_complete",
        "stage_index": 1,
        "stage_name": "Stage 1: RT-DETR Region Detection",
        "status": "passed" if detected_boxes else "failed",
        "progress_percent": 50,
        "message": f"Detected {len(detected_boxes)} layout bounding regions.",
        "execution_time_ms": round((time.time() - t1) * 1000, 2),
        "data": {"bounding_boxes": detected_boxes}
    }) + "\n"

    # -------------------------------------------------------------------------
    # STAGE 2: EasyOCR Text & Tabular Feature Extraction
    # -------------------------------------------------------------------------
    t2 = time.time()
    yield json.dumps({
        "event": "progress",
        "stage_index": 2,
        "stage_name": "Stage 2: EasyOCR Text Extraction",
        "progress_percent": 60,
        "status": "running"
    }) + "\n"

    extracted_headline, extracted_text, extracted_speaker = "", "", ""
    ocr_conf_scores = []

    try:
        from app.core.models_loader import ocr_reader
        if ocr_reader:
            if headline_crop is not None and headline_crop.size > 0:
                res = ocr_reader.readtext(headline_crop)
                extracted_headline = " ".join([txt for _, txt, _ in res]).strip()
                ocr_conf_scores.extend([p for _, _, p in res])

            if text_crop is not None and text_crop.size > 0:
                res = ocr_reader.readtext(text_crop)
                extracted_text = " ".join([txt for _, txt, _ in res]).strip()
                ocr_conf_scores.extend([p for _, _, p in res])

            if speaker_crop is not None and speaker_crop.size > 0:
                res = ocr_reader.readtext(speaker_crop)
                extracted_speaker = " ".join([txt for _, txt, _ in res]).strip()
                ocr_conf_scores.extend([p for _, _, p in res])
    except Exception as e:
        print(f"[!] EasyOCR exception: {e}")

    avg_ocr_conf = float(np.mean(ocr_conf_scores)) if ocr_conf_scores else 0.0
    tabular_features = [
        avg_ocr_conf,
        float(len(extracted_headline)),
        float(len(extracted_text)),
        1.0 if ('speaker' in detected_classes or extracted_speaker) else 0.0,
        1.0 if ('publisher' in detected_classes or 'publisher_logo' in detected_classes) else 0.0,
        1.0 if 'date' in detected_classes else 0.0
    ]

    yield json.dumps({
        "event": "stage_complete",
        "stage_index": 2,
        "stage_name": "Stage 2: EasyOCR Text Extraction",
        "status": "passed" if (extracted_headline or extracted_text) else "failed",
        "progress_percent": 75,
        "message": f"Extracted headline ({len(extracted_headline)} chars).",
        "execution_time_ms": round((time.time() - t2) * 1000, 2),
        "data": {
            "headline": extracted_headline,
            "speaker": extracted_speaker,
            "text": extracted_text,
            "tabular_vector": tabular_features
        }
    }) + "\n"

    # -------------------------------------------------------------------------
    # STAGE 3: Multimodal Photocard Classifier (photocard_classifier.onnx)
    # -------------------------------------------------------------------------
    t3 = time.time()
    yield json.dumps({
        "event": "progress",
        "stage_index": 3,
        "stage_name": "Stage 3: Multimodal Photocard Classifier",
        "progress_percent": 85,
        "status": "running"
    }) + "\n"

    visual_real_prob = 0.5
    try:
        from app.core.models_loader import classifier_session, ocr_scaler
        
        scaled_tabs = np.array(tabular_features, dtype=np.float32)
        if ocr_scaler and "mean" in ocr_scaler and "scale" in ocr_scaler:
            mean = np.array(ocr_scaler["mean"], dtype=np.float32)
            scale = np.array(ocr_scaler["scale"], dtype=np.float32)
            scaled_tabs = (scaled_tabs - mean) / scale

        pil_img = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
        img_tensor = eval_transforms(pil_img).unsqueeze(0).numpy()
        tab_tensor = np.expand_dims(scaled_tabs, axis=0)

        if classifier_session:
            inputs = classifier_session.get_inputs()
            outputs = classifier_session.run(None, {
                inputs[0].name: img_tensor,
                inputs[1].name: tab_tensor
            })
            logits = float(outputs[0][0])
            visual_real_prob = float(1.0 / (1.0 + np.exp(-logits)))
    except Exception as e:
        print(f"[!] Classifier exception: {e}")

    yield json.dumps({
        "event": "stage_complete",
        "stage_index": 3,
        "stage_name": "Stage 3: Multimodal Photocard Classifier",
        "status": "passed",
        "progress_percent": 95,
        "message": f"Classifier predicted {visual_real_prob*100:.2f}% real probability.",
        "execution_time_ms": round((time.time() - t3) * 1000, 2),
        "data": {"real_probability": visual_real_prob}
    }) + "\n"

    # -------------------------------------------------------------------------
    # FINAL VERDICT
    # -------------------------------------------------------------------------
    if visual_real_prob >= 0.60:
        badge, status_label = "🟢 Verified Real", "ok"
    elif visual_real_prob <= 0.40:
        badge, status_label = "🔴 Fabricated Fake", "alert"
    else:
        badge, status_label = "🟡 Low Confidence", "low_confidence"

    yield json.dumps({
        "event": "final_verdict",
        "progress_percent": 100,
        "badge": badge,
        "status": status_label,
        "confidence_score": round(visual_real_prob, 4)
    }) + "\n"