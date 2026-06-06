from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import transforms, models
import numpy as np
from PIL import Image
import io
import os
import cv2  # <--- Bổ sung OpenCV để bóc tách khung hình video
from nutrition import get_nutrition_with_fallback, get_healthy_recommendations

app = Flask(__name__)
CORS(app)

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, 'ML_models')
STATIC_DIR = os.path.join(BASE_DIR, 'navigation_menu')
CSS_DIR    = os.path.join(BASE_DIR, 'CSS')
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
JS_DIR     = os.path.join(BASE_DIR, 'JS')
TMP_DIR    = os.path.join(BASE_DIR, 'tmp') # Thư mục tạm lưu video

if not os.path.exists(TMP_DIR):
    os.makedirs(TMP_DIR)

DEVICE      = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
NUM_CLASSES = 30

# ── Build model architecture ─────────────────────────────────────────────────
def _build_resnet():
    m = models.resnet50(weights=None)
    m.fc = nn.Sequential(
        nn.Linear(m.fc.in_features, 512), nn.ReLU(inplace=True), nn.Dropout(0.5),
        nn.Linear(512, 256),              nn.ReLU(inplace=True), nn.Dropout(0.3),
        nn.Linear(256, NUM_CLASSES),
    )
    return m

try:
    resnet_model = _build_resnet()
    resnet_model.load_state_dict(
        torch.load(os.path.join(MODEL_DIR, 'v2_stage3.pth'), map_location=DEVICE)
    )
    resnet_model.to(DEVICE).eval()
    print(f"Model ResNet50 V2 load thành công  [{DEVICE}]")
except Exception as e:
    print(f"Lỗi load model: {e}")
    resnet_model = None

FOOD_CLASSES = [
    'Banh beo', 'Banh bot loc', 'Banh can', 'Banh canh', 'Banh chung',
    'Banh cuon', 'Banh duc', 'Banh gio', 'Banh khot', 'Banh mi',
    'Banh pia', 'Banh tet', 'Banh trang nuong', 'Banh xeo', 'Bun bo Hue',
    'Bun dau mam tom', 'Bun mam', 'Bun rieu', 'Bun thit nuong', 'Ca kho to',
    'Canh chua', 'Cao lau', 'Chao long', 'Com tam', 'Goi cuon',
    'Hu tieu', 'Mi quang', 'Nem chua', 'Pho', 'Xoi xeo'
]

_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225]),
])

def preprocess_image(img: Image.Image) -> torch.Tensor:
    if img.mode != 'RGB':
        img = img.convert('RGB')
    return _transform(img).unsqueeze(0).to(DEVICE)

# Các hàm serve file tĩnh giữ nguyên...
@app.route('/')
def index(): return send_from_directory(STATIC_DIR, 'index.html')

@app.route('/CSS/<path:filename>')
def serve_css(filename): return send_from_directory(CSS_DIR, filename)

@app.route('/JS/<path:filename>')
def serve_js(filename): return send_from_directory(JS_DIR, filename)

@app.route('/assets/<path:filename>')
def serve_assets(filename): return send_from_directory(ASSETS_DIR, filename)

@app.route('/navigation_menu/<path:filename>')
def serve_navigation(filename): return send_from_directory(STATIC_DIR, filename)

@app.route('/api/health')
def health():
    return jsonify({
        'status': 'healthy',
        'model_loaded': resnet_model is not None,
        'device': str(DEVICE),
        'total_classes': len(FOOD_CLASSES),
    })

# API dự đoán ảnh tĩnh giữ nguyên của bạn...
@app.route('/api/predict', methods=['POST'])
def predict():
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        if resnet_model is None:
            return jsonify({'error': 'ResNet model not loaded'}), 500

        img_bytes = file.read()
        img = Image.open(io.BytesIO(img_bytes))
        tensor = preprocess_image(img)
        
        with torch.no_grad():
            outputs = resnet_model(tensor)
            probs = F.softmax(outputs, dim=1).squeeze(0).cpu().numpy()

        top_indices = np.argsort(probs)[-3:][::-1]
        results = [{'name': FOOD_CLASSES[idx], 'confidence': float(probs[idx] * 100), 'index': int(idx)} for idx in top_indices]
        
        top_prediction_name = results[0]['name']
        nutrition_info = get_nutrition_with_fallback(top_prediction_name)
        healthy_recommendations = get_healthy_recommendations(top_prediction_name, top_k=3)
        
        return jsonify({
            'status': 'success',
            'predictions': results,
            'nutrition': nutrition_info,
            'recommendations': healthy_recommendations
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ── NEW API: XỬ LÝ VIDEO VÀ CAMERA STREAM ────────────────────────────────────
@app.route('/api/predict-video', methods=['POST'])
def predict_video():
    try:
        if 'video' not in request.files:
            return jsonify({'error': 'No video file provided'}), 400
        
        file = request.files['video']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        if resnet_model is None:
            return jsonify({'error': 'ResNet model not loaded'}), 500

        # Lưu video tạm thời xuống đĩa để OpenCV có thể đọc theo luồng
        video_path = os.path.join(TMP_DIR, file.filename)
        file.save(video_path)

        cap = cv2.VideoCapture(video_path)
        frame_idx = 0
        all_probabilities = []

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # KỸ THUẬT SKIPPING FRAMES: Cứ mỗi 5 khung hình mới lấy 1 hình đưa vào AI để giảm tải cho CPU/GPU
            if frame_idx % 5 == 0:
                # Chuyển đổi hệ màu từ BGR (OpenCV) sang RGB (PIL)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)
                
                # Biến đổi thành Tensor và dự đoán
                tensor = preprocess_image(pil_img)
                with torch.no_grad():
                    outputs = resnet_model(tensor)
                    probs = F.softmax(outputs, dim=1).squeeze(0).cpu().numpy()
                all_probabilities.append(probs)
                
            frame_idx += 1

        cap.release()
        if os.path.exists(video_path):
            os.remove(video_path)  # Giải phóng file tạm lập tức

        if len(all_probabilities) == 0:
            return jsonify({'error': 'Video does not contain any valid frames'}), 400

        # Tính trung bình xác suất hội tụ của toàn bộ video (Ensemble Voting)
        avg_probs = np.mean(all_probabilities, axis=0)
        top_indices = np.argsort(avg_probs)[-3:][::-1]
        
        results = [{'name': FOOD_CLASSES[idx], 'confidence': float(avg_probs[idx] * 100), 'index': int(idx)} for idx in top_indices]
        
        top_prediction_name = results[0]['name']
        nutrition_info = get_nutrition_with_fallback(top_prediction_name)
        healthy_recommendations = get_healthy_recommendations(top_prediction_name, top_k=3)

        return jsonify({
            'status': 'success',
            'predictions': results,
            'nutrition': nutrition_info,
            'recommendations': healthy_recommendations
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)