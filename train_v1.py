"""
Train ResNet50 - Vietnamese Food Recognition (FIXED - anti-overfitting)
Fixes: stronger augmentation, L2 regularization, label smoothing,
       fewer unfrozen layers (layer4 only), lower EarlyStopping patience.
"""
import os, time, copy
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms, models
from torch.optim.lr_scheduler import ReduceLROnPlateau
from sklearn.metrics import classification_report

# ── Config ───────────────────────────────────────────────────────────────────
IMG_SIZE    = 224
BATCH_SIZE  = 64
NUM_CLASSES = 30
DEVICE      = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

_BASE = os.path.dirname(os.path.abspath(__file__))

def _resolve_paths():
    if os.path.exists('/content'):
        try:
            import kagglehub
            _dl = kagglehub.dataset_download('quandang/vietnamese-foods')
            return os.path.join(_dl, 'Images'), os.path.join(_BASE, 'ML_models')
        except Exception:
            return '/content/drive/MyDrive/vietnamese-foods/Images', os.path.join(_BASE, 'ML_models')
    return os.path.join(_BASE, 'data', 'Images'), os.path.join(_BASE, 'ML_models')

DATASET_BASE, SAVE_DIR = _resolve_paths()
TRAIN_DIR = os.path.join(DATASET_BASE, 'Train')
VAL_DIR   = os.path.join(DATASET_BASE, 'Validate')
TEST_DIR  = os.path.join(DATASET_BASE, 'Test')
os.makedirs(SAVE_DIR, exist_ok=True)

print(f'Device: {DEVICE}')
if DEVICE.type == 'cuda':
    print(f'GPU: {torch.cuda.get_device_name(0)}')

# ── Data transforms ──────────────────────────────────────────────────────────
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

train_transform = transforms.Compose([
    transforms.RandomResizedCrop(IMG_SIZE, scale=(0.7, 1.0)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(25),
    transforms.RandomAffine(degrees=0, shear=10, translate=(0.1, 0.1)),
    transforms.ColorJitter(brightness=0.3, contrast=0.2, saturation=0.2),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])

val_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(IMG_SIZE),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])

train_ds = datasets.ImageFolder(TRAIN_DIR, transform=train_transform)
val_ds   = datasets.ImageFolder(VAL_DIR,   transform=val_transform)
test_ds  = datasets.ImageFolder(TEST_DIR,  transform=val_transform)

train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,  num_workers=4, pin_memory=True)
val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False, num_workers=4, pin_memory=True)
test_loader  = DataLoader(test_ds,  batch_size=BATCH_SIZE, shuffle=False, num_workers=4, pin_memory=True)

print(f'Train: {len(train_ds)} | Val: {len(val_ds)} | Test: {len(test_ds)}')

# ── Model ────────────────────────────────────────────────────────────────────
def build_model():
    model = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
    # Freeze toàn bộ backbone
    for p in model.parameters():
        p.requires_grad = False
    # Thay head: Dense(512,l2) + Drop(0.5) + Dense(256,l2) + Drop(0.3) + Dense(30)
    in_features = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Linear(in_features, 512),
        nn.ReLU(inplace=True),
        nn.Dropout(0.5),
        nn.Linear(512, 256),
        nn.ReLU(inplace=True),
        nn.Dropout(0.3),
        nn.Linear(256, NUM_CLASSES),
    )
    return model

# ── Training loop ────────────────────────────────────────────────────────────
def train_one_epoch(model, loader, optimizer, criterion):
    model.train()
    total_loss, correct, total = 0.0, 0, 0
    for imgs, labels in loader:
        imgs, labels = imgs.to(DEVICE), labels.to(DEVICE)
        optimizer.zero_grad()
        outputs = model(imgs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * imgs.size(0)
        correct    += (outputs.argmax(1) == labels).sum().item()
        total      += imgs.size(0)
    return total_loss / total, correct / total

@torch.no_grad()
def evaluate(model, loader, criterion):
    model.eval()
    total_loss, correct, total = 0.0, 0, 0
    for imgs, labels in loader:
        imgs, labels = imgs.to(DEVICE), labels.to(DEVICE)
        outputs = model(imgs)
        loss = criterion(outputs, labels)
        total_loss += loss.item() * imgs.size(0)
        correct    += (outputs.argmax(1) == labels).sum().item()
        total      += imgs.size(0)
    return total_loss / total, correct / total

def fit(model, train_loader, val_loader, optimizer, criterion, scheduler,
        epochs, save_path, patience=5, stage_name=''):
    best_val_acc  = 0.0
    best_weights  = copy.deepcopy(model.state_dict())
    patience_cnt  = 0
    best_val_loss = float('inf')
    history = {'train_acc': [], 'val_acc': [], 'train_loss': [], 'val_loss': []}

    for ep in range(1, epochs + 1):
        t0 = time.time()
        tr_loss, tr_acc = train_one_epoch(model, train_loader, optimizer, criterion)
        vl_loss, vl_acc = evaluate(model, val_loader, criterion)
        scheduler.step(vl_loss)

        history['train_acc'].append(tr_acc)
        history['val_acc'].append(vl_acc)
        history['train_loss'].append(tr_loss)
        history['val_loss'].append(vl_loss)

        gap = tr_acc - vl_acc
        print(f'[{stage_name}] Ep{ep:02d}/{epochs} '
              f'train={tr_acc:.4f} val={vl_acc:.4f} gap={gap:+.4f} '
              f'val_loss={vl_loss:.4f} lr={optimizer.param_groups[0]["lr"]:.2e} '
              f'({time.time()-t0:.0f}s)')

        if vl_acc > best_val_acc:
            best_val_acc = vl_acc
            best_weights = copy.deepcopy(model.state_dict())
            torch.save(best_weights, save_path)

        if vl_loss < best_val_loss:
            best_val_loss = vl_loss
            patience_cnt  = 0
        else:
            patience_cnt += 1
            if patience_cnt >= patience:
                print(f'  EarlyStopping triggered at epoch {ep}')
                break

    model.load_state_dict(best_weights)
    return history

# ── Stage 1: train head, backbone frozen ─────────────────────────────────────
print('\n' + '='*60)
print('STAGE 1: Train head (backbone frozen)')
print('='*60)

model = build_model().to(DEVICE)

# Chỉ optimize head, weight_decay = L2 regularization
optimizer1 = torch.optim.Adam(model.fc.parameters(), lr=1e-3, weight_decay=1e-4)
scheduler1 = ReduceLROnPlateau(optimizer1, factor=0.5, patience=4, min_lr=1e-7)
criterion  = nn.CrossEntropyLoss(label_smoothing=0.1)

history1 = fit(model, train_loader, val_loader, optimizer1, criterion, scheduler1,
               epochs=20, save_path=f'{SAVE_DIR}/stage1.pth',
               patience=7, stage_name='S1')

# ── Stage 2: unfreeze layer4 (conv5 block) chỉ ────────────────────────────────
print('\n' + '='*60)
print('STAGE 2: Fine-tune layer4 (conv5 block cuoi, ~12 layers)')
print('='*60)

# Load best stage1 weights
model.load_state_dict(torch.load(f'{SAVE_DIR}/stage1.pth'))

# Unfreeze chỉ layer4 (tương đương 12 layers cuối của ResNet50 trong Keras)
for p in model.layer4.parameters():
    p.requires_grad = True

trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f'Trainable params: {trainable_params:,}')

optimizer2 = torch.optim.Adam(
    filter(lambda p: p.requires_grad, model.parameters()),
    lr=1e-4, weight_decay=1e-4
)
scheduler2 = ReduceLROnPlateau(optimizer2, factor=0.5, patience=3, min_lr=1e-8)

history2 = fit(model, train_loader, val_loader, optimizer2, criterion, scheduler2,
               epochs=20, save_path=f'{SAVE_DIR}/stage2_fixed.pth',
               patience=5, stage_name='S2')

# ── Phân tích overfitting ─────────────────────────────────────────────────────
print('\n' + '='*60)
print('OVERFITTING ANALYSIS')
print('='*60)

for name, h in [('Stage 1', history1), ('Stage 2', history2)]:
    ta, va = h['train_acc'], h['val_acc']
    tl, vl = h['train_loss'], h['val_loss']
    best_ep = int(np.argmax(va))
    print(f'\n{name}:')
    print(f'  Best  (ep{best_ep+1:02d}): train={ta[best_ep]:.4f}  val={va[best_ep]:.4f}  gap={ta[best_ep]-va[best_ep]:+.4f}')
    print(f'  Final (ep{len(ta):02d}): train={ta[-1]:.4f}  val={va[-1]:.4f}  gap={ta[-1]-va[-1]:+.4f}')
    print(f'  Val loss start→end: {vl[0]:.4f} → {vl[-1]:.4f}  ({"diverging" if vl[-1]>vl[0] else "stable/improving"})')

# ── Evaluate on test set ──────────────────────────────────────────────────────
print('\n' + '='*60)
print('TEST SET EVALUATION')
print('='*60)

model.load_state_dict(torch.load(f'{SAVE_DIR}/stage2_fixed.pth'))
model.eval()

all_preds, all_labels = [], []
with torch.no_grad():
    for imgs, labels in test_loader:
        preds = model(imgs.to(DEVICE)).argmax(1).cpu()
        all_preds.extend(preds.numpy())
        all_labels.extend(labels.numpy())

class_names = [c.replace('_', ' ').title() for c in train_ds.classes]
print(classification_report(all_labels, all_preds, target_names=class_names))

# ── Plot learning curves ──────────────────────────────────────────────────────
import matplotlib.pyplot as plt

fig, axes = plt.subplots(2, 2, figsize=(14, 10))
for row, (h, name) in enumerate([(history1, 'Stage 1'), (history2, 'Stage 2')]):
    axes[row, 0].plot(h['train_acc'], label='Train')
    axes[row, 0].plot(h['val_acc'],   label='Val')
    axes[row, 0].set_title(f'{name}: Accuracy')
    axes[row, 0].legend(); axes[row, 0].grid(alpha=0.3)

    axes[row, 1].plot(h['train_loss'], label='Train')
    axes[row, 1].plot(h['val_loss'],   label='Val')
    axes[row, 1].set_title(f'{name}: Loss')
    axes[row, 1].legend(); axes[row, 1].grid(alpha=0.3)

plt.tight_layout()
plt.savefig(f'{SAVE_DIR}/training_curves_fixed.png', dpi=120)
print(f'\nPlot saved: {SAVE_DIR}/training_curves_fixed.png')
