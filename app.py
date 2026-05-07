from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.resnet50 import preprocess_input
import numpy as np
from PIL import Image
import io
import os
from nutrition import get_nutrition_with_fallback

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, 'ML_models')
STATIC_DIR = os.path.join(BASE_DIR, 'navigation_menu')
CSS_DIR = os.path.join(BASE_DIR, 'CSS')
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
JS_DIR = os.path.join(BASE_DIR, 'JS')

try:
    resnet_model = load_model(os.path.join(MODEL_DIR, 'final_model.h5'))
    print("Model ResNet50 load thành công")
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

def preprocess_image(img):
    if img.mode != 'RGB':
        img = img.convert('RGB')
    img = img.resize((224, 224))
    img_array = image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0)
    img_array = preprocess_input(img_array)
    return img_array

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
        'model_name': 'ResNet50',
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
        
        processed_img = preprocess_image(img)
        predictions = resnet_model.predict(processed_img, verbose=0)
        
        top_indices = np.argsort(predictions[0])[-3:][::-1]
        
        results = []
        for idx in top_indices:
            if idx < len(FOOD_CLASSES):
                confidence = float(predictions[0][idx] * 100)
                results.append({
                    'name': FOOD_CLASSES[idx],
                    'confidence': confidence,
                    'index': int(idx)
                })
        
        top_prediction_name = results[0]['name']
        nutrition_info = get_nutrition_with_fallback(top_prediction_name)
        
        return jsonify({
            'status': 'success',
            'model': 'ResNet50',
            'predictions': results,
            'nutrition': nutrition_info,
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
        'model': 'ResNet50'
    })

if __name__ == '__main__':
    print("Đang chạy Food Recognition API với ResNet50")
    print("Server: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000)