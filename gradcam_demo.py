"""
gradcam_demo.py
  - gradcam_single.png : 1 ảnh, so sánh original | heatmap | overlay
  - gradcam_3x3.png    : 9 ảnh dạng lưới 3×3
Ảnh input: cắt từ correct_page001.png (không cần dataset gốc)
"""
import os
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import transforms, models
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.cm as cm_plt

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'ML_models', 'v2_stage3.pth')
PRED_PAGE  = os.path.join(BASE_DIR, 'ML_models', 'predictions', 'correct_page001.png')
OUT_DIR    = os.path.join(BASE_DIR, 'ML_models')

DEVICE      = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
NUM_CLASSES = 30
FOOD_CLASSES = [
    'Banh beo', 'Banh bot loc', 'Banh can', 'Banh canh', 'Banh chung',
    'Banh cuon', 'Banh duc', 'Banh gio', 'Banh khot', 'Banh mi',
    'Banh pia', 'Banh tet', 'Banh trang nuong', 'Banh xeo', 'Bun bo Hue',
    'Bun dau mam tom', 'Bun mam', 'Bun rieu', 'Bun thit nuong', 'Ca kho to',
    'Canh chua', 'Cao lau', 'Chao long', 'Com tam', 'Goi cuon',
    'Hu tieu', 'Mi quang', 'Nem chua', 'Pho', 'Xoi xeo',
]

TRANSFORM = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

# ── Load model ────────────────────────────────────────────────────────────────
def build_model():
    m = models.resnet50(weights=None)
    m.fc = nn.Sequential(
        nn.Linear(m.fc.in_features, 512), nn.ReLU(inplace=True), nn.Dropout(0.5),
        nn.Linear(512, 256),              nn.ReLU(inplace=True), nn.Dropout(0.3),
        nn.Linear(256, NUM_CLASSES),
    )
    return m

model = build_model()
model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
model.to(DEVICE).eval()
print(f'Model loaded  [{DEVICE}]')

# ── GradCAM ───────────────────────────────────────────────────────────────────
class GradCAM:
    def __init__(self, model, target_layer):
        self.gradients  = None
        self.activations = None
        target_layer.register_forward_hook(self._fwd)
        target_layer.register_full_backward_hook(self._bwd)

    def _fwd(self, _, __, output):
        self.activations = output.detach()

    def _bwd(self, _, __, grad_output):
        self.gradients = grad_output[0].detach()

    def generate(self, tensor):
        """
        tensor: (1,3,224,224) on DEVICE
        Returns: cam (H,W) 0-1, class_idx, confidence
        """
        model.zero_grad()
        out = model(tensor)
        idx  = out.argmax(dim=1).item()
        conf = out.softmax(dim=1)[0, idx].item()
        out[0, idx].backward()

        weights = self.gradients.mean(dim=(2, 3), keepdim=True)   # (1,C,1,1)
        cam = (weights * self.activations).sum(dim=1).squeeze()    # (H,W)
        cam = F.relu(cam).cpu().numpy()
        cam -= cam.min()
        cam /= (cam.max() + 1e-8)
        return cam, idx, conf

gradcam = GradCAM(model, model.layer4[-1])

# ── Helpers ───────────────────────────────────────────────────────────────────
def preprocess(pil_img):
    return TRANSFORM(pil_img.convert('RGB')).unsqueeze(0).to(DEVICE)

def make_overlay(pil_img, cam, alpha=0.45):
    """Blend original image with jet-colormap GradCAM heatmap."""
    img_224  = pil_img.convert('RGB').resize((224, 224))
    img_np   = np.array(img_224) / 255.0

    cam_pil  = Image.fromarray((cam * 255).astype(np.uint8))
    cam_224  = np.array(cam_pil.resize((224, 224), Image.BILINEAR)) / 255.0

    heatmap  = cm_plt.jet(cam_224)[:, :, :3]           # (H,W,3) RGB
    overlay  = (1 - alpha) * img_np + alpha * heatmap
    return np.clip(overlay, 0, 1), img_np, cam_224

def extract_grid_cells(page_path, n_rows=3, n_cols=3, title_h=30, label_h=18):
    """Cắt 9 ô ảnh từ prediction page PNG."""
    page = Image.open(page_path).convert('RGB')
    W, H = page.size
    cell_w = W // n_cols
    cell_h = (H - title_h) // n_rows
    crops = []
    for row in range(n_rows):
        for col in range(n_cols):
            x0 = col * cell_w
            y0 = title_h + row * cell_h + label_h   # bỏ dòng label nhỏ trên đầu
            x1 = x0 + cell_w
            y1 = title_h + (row + 1) * cell_h
            crops.append(page.crop((x0, y0, x1, y1)))
    return crops

# ── Extract crops ─────────────────────────────────────────────────────────────
crops = extract_grid_cells(PRED_PAGE)
print(f'Extracted {len(crops)} crops from prediction page')

results = []
for i, crop in enumerate(crops):
    tensor = preprocess(crop)
    with torch.enable_grad():
        cam, cls_idx, conf = gradcam.generate(tensor)
    overlay, img_np, heat = make_overlay(crop, cam)
    results.append({
        'img'    : img_np,
        'overlay': overlay,
        'heat'   : heat,
        'label'  : FOOD_CLASSES[cls_idx],
        'conf'   : conf,
    })
    print(f'  [{i+1}] {FOOD_CLASSES[cls_idx]:22s}  {conf*100:.1f}%')


# ════════════════════════════════════════════════════════════════════════════════
# 1. SINGLE — 3 panels: original | heatmap | overlay
# ════════════════════════════════════════════════════════════════════════════════
r = results[0]
fig, axes = plt.subplots(1, 3, figsize=(12, 4))
fig.suptitle(f'GradCAM — {r["label"].title()}  (confidence {r["conf"]*100:.1f}%)',
             fontsize=13, fontweight='bold')

axes[0].imshow(r['img']);        axes[0].set_title('Ảnh gốc',          fontsize=11)
axes[1].imshow(r['heat'],
               cmap='jet',
               vmin=0, vmax=1);  axes[1].set_title('GradCAM Heatmap',  fontsize=11)
axes[2].imshow(r['overlay']);    axes[2].set_title('Overlay (α = 0.45)', fontsize=11)

for ax in axes:
    ax.axis('off')

plt.colorbar(plt.cm.ScalarMappable(cmap='jet'), ax=axes[1],
             fraction=0.046, pad=0.04, label='Activation intensity')
plt.tight_layout()
out1 = os.path.join(OUT_DIR, 'gradcam_single.png')
plt.savefig(out1, dpi=130, bbox_inches='tight')
plt.close()
print(f'\nSaved: {out1}')


# ════════════════════════════════════════════════════════════════════════════════
# 2. 3×3 GRID — overlay cho cả 9 ảnh
# ════════════════════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(3, 3, figsize=(13, 13))
fig.suptitle('GradCAM Visualization — ResNet50 V2  (layer4, 9 mẫu đúng)',
             fontsize=14, fontweight='bold', y=0.98)

for i, (ax, r) in enumerate(zip(axes.flat, results)):
    ax.imshow(r['overlay'])
    ax.set_title(f"{r['label'].title()}\n{r['conf']*100:.1f}%",
                 fontsize=9, fontweight='bold', pad=3)
    ax.axis('off')

    # Viền màu xanh lá (dự đoán đúng — lấy từ correct page)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_edgecolor('#2E7D32')
        spine.set_linewidth(2.5)

plt.subplots_adjust(hspace=0.12, wspace=0.05)

# Colorbar chung bên phải
cbar_ax = fig.add_axes([0.92, 0.15, 0.015, 0.7])
sm = plt.cm.ScalarMappable(cmap='jet')
sm.set_array([])
fig.colorbar(sm, cax=cbar_ax, label='GradCAM activation')

out2 = os.path.join(OUT_DIR, 'gradcam_3x3.png')
plt.savefig(out2, dpi=130, bbox_inches='tight')
plt.close()
print(f'Saved: {out2}')
print('\nDone.')
