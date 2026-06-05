"""
Sinh ảnh dự đoán hàng loạt — layout 3x3 (9 cặp/trang)
Mỗi ô: ảnh gốc + nhãn Thực tế / Dự đoán
Dùng model v2_stage3.pth (best)
"""
import os, math
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms, models
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── Config ────────────────────────────────────────────────────────────────────
IMG_SIZE     = 224
BATCH_SIZE   = 64
DEVICE       = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
NUM_CLASSES  = 30

_BASE = os.path.dirname(os.path.abspath(__file__))

def _resolve_paths():
    if os.path.exists('/content'):
        try:
            import kagglehub
            _dl = kagglehub.dataset_download('quandang/vietnamese-foods')
            return os.path.join(_dl, 'Images', 'Test')
        except Exception:
            return '/content/drive/MyDrive/vietnamese-foods/Images/Test'
    return os.path.join(_BASE, 'data', 'Images', 'Test')

TEST_DIR   = _resolve_paths()
MODEL_PATH = os.path.join(_BASE, 'ML_models', 'v2_stage3.pth')
OUT_DIR    = os.path.join(_BASE, 'ML_models', 'predictions')
os.makedirs(OUT_DIR, exist_ok=True)

MEAN = [0.485, 0.456, 0.406]
STD  = [0.229, 0.224, 0.225]

print(f'Device : {DEVICE}')
if DEVICE.type == 'cuda':
    print(f'GPU    : {torch.cuda.get_device_name(0)}')

# ── Model ─────────────────────────────────────────────────────────────────────
def build_model():
    m = models.resnet50(weights=None)
    m.fc = nn.Sequential(
        nn.Linear(m.fc.in_features, 512), nn.ReLU(inplace=True), nn.Dropout(0.5),
        nn.Linear(512, 256),              nn.ReLU(inplace=True), nn.Dropout(0.3),
        nn.Linear(256, NUM_CLASSES),
    )
    return m

model = build_model().to(DEVICE)
model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
model.eval()
print(f'Loaded : {MODEL_PATH}')

# ── Dataset ───────────────────────────────────────────────────────────────────
test_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(IMG_SIZE),
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD),
])
test_ds     = datasets.ImageFolder(TEST_DIR, transform=test_transform)
test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False,
                         num_workers=4, pin_memory=True)

class_names = [c.replace('_', ' ').title() for c in test_ds.classes]
print(f'Test   : {len(test_ds)} ảnh | {NUM_CLASSES} class')

# ── Predict toàn bộ test set ──────────────────────────────────────────────────
all_preds, all_labels, all_confs = [], [], []
with torch.no_grad():
    for imgs, labels in test_loader:
        logits = model(imgs.to(DEVICE))
        probs  = torch.softmax(logits, dim=1)
        conf, pred = probs.max(1)
        all_preds.extend(pred.cpu().numpy())
        all_labels.extend(labels.numpy())
        all_confs.extend(conf.cpu().numpy())

all_preds  = np.array(all_preds)
all_labels = np.array(all_labels)
all_confs  = np.array(all_confs)
acc = np.mean(all_preds == all_labels)
print(f'Acc    : {acc*100:.2f}%')

# ── Hàm vẽ 1 trang 3x3 ───────────────────────────────────────────────────────
def denormalize(tensor):
    mean = np.array(MEAN); std = np.array(STD)
    img = tensor.permute(1, 2, 0).numpy()
    img = img * std + mean
    return np.clip(img, 0, 1)

def save_page(indices, page_num, tag=''):
    fig, axes = plt.subplots(3, 3, figsize=(13, 13))
    fig.patch.set_facecolor('#1a1a2e')

    for ax_i, idx in enumerate(indices):
        ax = axes[ax_i // 3][ax_i % 3]

        # Load ảnh gốc (không normalize)
        img_path = test_ds.imgs[idx][0]
        img_raw  = Image.open(img_path).convert('RGB')
        img_raw  = img_raw.resize((IMG_SIZE, IMG_SIZE))

        true_name = class_names[all_labels[idx]]
        pred_name = class_names[all_preds[idx]]
        conf      = all_confs[idx] * 100
        correct   = all_preds[idx] == all_labels[idx]

        ax.imshow(img_raw)
        ax.axis('off')

        # Viền màu: xanh = đúng, đỏ = sai
        border_color = '#00e676' if correct else '#ff1744'
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_edgecolor(border_color)
            spine.set_linewidth(3)

        # Label bên dưới ảnh
        bg_color = '#1b5e20' if correct else '#b71c1c'
        ax.set_title(
            f'✓ {pred_name}  ({conf:.1f}%)' if correct
            else f'✗ Pred: {pred_name}  ({conf:.1f}%)\n   True: {true_name}',
            fontsize=9, color='white', pad=4,
            bbox=dict(boxstyle='round,pad=0.3', facecolor=bg_color, alpha=0.85)
        )

    # Điền ô trống nếu < 9
    for ax_i in range(len(indices), 9):
        axes[ax_i // 3][ax_i % 3].axis('off')

    correct_count = sum(all_preds[i] == all_labels[i] for i in indices)
    fig.suptitle(
        f'{tag} — Trang {page_num:03d}   ({correct_count}/9 đúng)',
        fontsize=13, color='white', fontweight='bold', y=0.995
    )
    plt.tight_layout(rect=[0, 0, 1, 0.99])
    path = f'{OUT_DIR}/{tag}_page{page_num:03d}.png'
    plt.savefig(path, dpi=110, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close()
    return path

# ── 1. Sinh ảnh ngẫu nhiên (5 trang) ────────────────────────────────────────
print('\n--- Sinh trang ngẫu nhiên ---')
rng  = np.random.default_rng(42)
rand_idx = rng.choice(len(test_ds), size=min(45, len(test_ds)), replace=False)
for page in range(5):
    chunk = rand_idx[page*9 : page*9+9]
    path  = save_page(chunk, page+1, tag='random')
    print(f'  {path}')

# ── 2. Sinh ảnh SAI (5 trang) ────────────────────────────────────────────────
print('\n--- Sinh trang dự đoán SAI ---')
wrong_idx = np.where(all_preds != all_labels)[0]
rng.shuffle(wrong_idx)
n_wrong_pages = min(5, math.ceil(len(wrong_idx) / 9))
for page in range(n_wrong_pages):
    chunk = wrong_idx[page*9 : page*9+9]
    path  = save_page(chunk, page+1, tag='wrong')
    print(f'  {path}')

# ── 3. Sinh ảnh ĐÚNG (3 trang) ───────────────────────────────────────────────
print('\n--- Sinh trang dự đoán ĐÚNG ---')
correct_idx = np.where(all_preds == all_labels)[0]
rng.shuffle(correct_idx)
for page in range(3):
    chunk = correct_idx[page*9 : page*9+9]
    path  = save_page(chunk, page+1, tag='correct')
    print(f'  {path}')

print(f'\nTất cả ảnh lưu tại: {OUT_DIR}')
print(f'  random_page001-005.png  — mẫu ngẫu nhiên')
print(f'  wrong_page001-00{n_wrong_pages}.png    — dự đoán sai')
print(f'  correct_page001-003.png — dự đoán đúng')
