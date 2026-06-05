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
from nutrition import get_nutrition_with_fallback, get_healthy_recommendations

app = Flask(__name__)
CORS(app)

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, 'ML_models')
STATIC_DIR = os.path.join(BASE_DIR, 'navigation_menu')
CSS_DIR    = os.path.join(BASE_DIR, 'CSS')
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
JS_DIR     = os.path.join(BASE_DIR, 'JS')

DEVICE      = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
NUM_CLASSES = 30

# ── Build model architecture (phải khớp với train_v2.py) ─────────────────────
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

@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')

@app.route('/CSS/<path:filename>')
def serve_css(filename):
    return send_from_directory(CSS_DIR, filename)

@app.route('/JS/<path:filename>')
def serve_js(filename):
    return send_from_directory(JS_DIR, filename)

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory(ASSETS_DIR, filename)

@app.route('/navigation_menu/<path:filename>')
def serve_navigation(filename):
    return send_from_directory(STATIC_DIR, filename)

@app.route('/api/health')
def health():
    return jsonify({
        'status': 'healthy',
        'model_loaded': resnet_model is not None,
        'model_name': 'ResNet50 V2 (PyTorch)',
        'device': str(DEVICE),
        'total_classes': len(FOOD_CLASSES),
    })

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
            probs = F.softmax(resnet_model(tensor), dim=1).squeeze(0).cpu().numpy()

        top_indices = np.argsort(probs)[-3:][::-1]

        results = []
        for idx in top_indices:
            results.append({
                'name': FOOD_CLASSES[idx],
                'confidence': float(probs[idx] * 100),
                'index': int(idx)
            })
        
        # 1. Lấy tên món ăn được dự đoán cao nhất
        top_prediction_name = results[0]['name']
        
        # 2. Lấy thông tin dinh dưỡng món gốc
        nutrition_info = get_nutrition_with_fallback(top_prediction_name)
        
        # >>> PHẦN THÊM MỚI TẠI ĐÂY <<<
        # 3. Lấy danh sách 3 món ăn lành mạnh hơn để thay thế từ thuật toán lý thuyết đồ thị/khoảng cách
        healthy_recommendations = get_healthy_recommendations(top_prediction_name, top_k=3)
        # >>> --------------------- <<<
        
        return jsonify({
            'status': 'success',
            'model': 'ResNet50 V2',
            'predictions': results,
            'nutrition': nutrition_info,
            'recommendations': healthy_recommendations,  # Bổ sung key này để truyền mảng dữ liệu về Frontend
            'total_classes': len(FOOD_CLASSES)
        })
    
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/classes')
def get_classes():
    return jsonify({
        'food_classes': FOOD_CLASSES,
        'total_classes': len(FOOD_CLASSES),
        'model': 'ResNet50 V2 (PyTorch)'
    })

if __name__ == '__main__':
    print("Đang chạy Food Recognition API với ResNet50 V2 (PyTorch)")
    print(f"Device : {DEVICE}")
    print("Server : http://localhost:5000")
    app.run(host="0.0.0.0", port=5000)