# Nhận diện món ăn Việt Nam bằng Deep Learning

Đồ án tốt nghiệp — Nhóm DL22  
Mô hình: **ResNet50 V2** (IMAGENET1K_V2) — 3 giai đoạn transfer learning  
Tập dữ liệu: **30 món ăn Việt Nam**, 25.136 ảnh  
Kết quả: **85.02%** (normal) | **86.59%** (TTA ×5)

---

## Cấu trúc thư mục

```
luan-van-tot-nghiep/
├── data/                        # Dataset (tạo thủ công — xem hướng dẫn bên dưới)
│   └── Images/
│       ├── Train/
│       │   ├── Banh_beo/
│       │   ├── Banh_bot_loc/
│       │   └── ...              # 30 thư mục tương ứng 30 lớp
│       ├── Validate/
│       └── Test/
├── ML_models/                   # Model weights + charts (tự sinh khi train)
│   ├── v2_stage1.pth
│   ├── v2_stage2.pth
│   ├── v2_stage3.pth            # Model tốt nhất — dùng cho inference
│   └── predictions/
├── navigation_menu/             # Frontend HTML
├── CSS/ / JS/ / assets/
├── app.py                       # Flask API server
├── nutrition.py                 # Module dinh dưỡng + gợi ý món thay thế
├── train_v2.py                  # Script huấn luyện (ResNet50 V2) — KHUYẾN NGHỊ
├── train_v1.py                  # Script huấn luyện v1 (tham khảo)
├── test_predict.py              # Sinh ảnh dự đoán hàng loạt (3×3 grid)
└── gradcam_demo.py              # GradCAM visualization
```

---

## Yêu cầu

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install flask flask-cors pillow scikit-learn matplotlib seaborn numpy
```

> Nếu chạy trên Colab, thêm:
> ```bash
> pip install kagglehub
> ```

---

## Tải dataset

Dataset: [30 Vietnamese Foods](https://www.kaggle.com/datasets/quandang/vietnamese-foods) trên Kaggle.

### Cách 1 — Tải thủ công (Local)

1. Đăng nhập Kaggle → tải file zip về máy
2. Giải nén, đặt đúng cấu trúc sau:

```
luan-van-tot-nghiep/
└── data/
    └── Images/
        ├── Train/
        ├── Validate/
        └── Test/
```

### Cách 2 — Kaggle API (Local hoặc Colab)

```bash
# Cài Kaggle CLI
pip install kaggle

# Đặt file kaggle.json vào ~/.kaggle/ (lấy từ Account → API → Create New Token)
kaggle datasets download -d quandang/vietnamese-foods
unzip vietnamese-foods.zip -d data/
```

### Cách 3 — kagglehub (Colab, tự động)

Khi chạy trên **Google Colab**, các script tự động gọi `kagglehub` để tải về — không cần thao tác thêm:

```python
import kagglehub
path = kagglehub.dataset_download('quandang/vietnamese-foods')
```

> Cần đăng nhập Kaggle trong Colab: `kaggle.json` upload lên hoặc dùng Colab Secrets.

---

## Chạy trên Local

### 1. Huấn luyện mô hình

```bash
python train_v2.py
```

Script tự nhận diện môi trường và đọc data từ `data/Images/`.  
Sau khi train xong, toàn bộ model weights và biểu đồ được lưu vào `ML_models/`.

### 2. Sinh ảnh dự đoán (3×3 grid)

```bash
python test_predict.py
```

Kết quả lưu tại `ML_models/predictions/`.

### 3. GradCAM visualization

```bash
python gradcam_demo.py
```

Kết quả: `ML_models/gradcam_single.png` và `ML_models/gradcam_3x3.png`.

### 4. Khởi động web app

```bash
python app.py
```

Truy cập: `http://localhost:5000`

---

## Chạy trên Google Colab

```python
# 1. Clone repo
!git clone https://github.com/<your-username>/luan-van-tot-nghiep.git
%cd luan-van-tot-nghiep

# 2. Cài thư viện
!pip install kagglehub flask flask-cors scikit-learn matplotlib seaborn

# 3. Đăng nhập Kaggle (upload kaggle.json hoặc dùng Secrets)
from google.colab import files
files.upload()           # chọn kaggle.json
!mkdir -p ~/.kaggle && mv kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json

# 4. Huấn luyện — script tự tải data qua kagglehub
!python train_v2.py
```

> **Lưu ý Colab:** Để giữ model sau khi session kết thúc, mount Google Drive trước:
> ```python
> from google.colab import drive
> drive.mount('/content/drive')
> # Sau đó copy ML_models/ sang Drive
> !cp -r ML_models/ /content/drive/MyDrive/
> ```

---

## Kết quả mô hình (ResNet50 V2)

| Giai đoạn | Cấu hình | Val Accuracy (best) |
|-----------|----------|---------------------|
| Stage 1   | Head only, backbone frozen | 71.21% |
| Stage 2   | Fine-tune layer4 + Mixup   | 84.73% |
| Stage 3   | Fine-tune layer3+4 + Mixup | **85.49%** |

| Metric | Normal Inference | TTA (×5 views) |
|--------|-----------------|----------------|
| Test Accuracy | 85.02% | **86.59%** |
| Macro F1      | 0.85   | 0.866 |

---

## Mô tả các file chính

| File | Mô tả |
|------|-------|
| `train_v2.py` | Huấn luyện 3 giai đoạn, tự sinh 7 biểu đồ, lưu model |
| `train_v1.py` | Phiên bản cũ (ResNet50 V1, 2 giai đoạn) — lưu tham khảo |
| `test_predict.py` | Chạy inference hàng loạt, xuất grid 3×3 ảnh đúng/sai |
| `gradcam_demo.py` | Sinh GradCAM heatmap giải thích quyết định mô hình |
| `app.py` | Flask API: `/api/predict` nhận ảnh → trả nhãn + dinh dưỡng + gợi ý |
| `nutrition.py` | Cơ sở dữ liệu dinh dưỡng + thuật toán gợi ý món thay thế |
