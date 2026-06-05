"""
Train ResNet50 V2 — Vietnamese Food Recognition
Improvements vs v1:
  - ResNet50 IMAGENET1K_V2 weights (80.9% vs 76.1%)
  - RandomErasing augmentation
  - Mixup augmentation (stage 2 & 3)
  - CosineAnnealingLR (smooth decay)
  - Stage 3: unfreeze layer3 + layer4
  - TTA at inference
  - Full logs + charts
"""
import os, time, copy, csv
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torchvision import datasets, transforms, models
from torch.optim.lr_scheduler import CosineAnnealingLR
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

torch.manual_seed(42)
np.random.seed(42)

# ── Config ───────────────────────────────────────────────────────────────────
IMG_SIZE    = 224
BATCH_SIZE  = 64
NUM_CLASSES = 30
DEVICE      = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

_BASE = os.path.dirname(os.path.abspath(__file__))

def _resolve_paths():
    """Tự động phát hiện môi trường: Google Colab hoặc Local."""
    if os.path.exists('/content'):                      # Google Colab
        try:
            import kagglehub
            _dl = kagglehub.dataset_download('quandang/vietnamese-foods')
            return os.path.join(_dl, 'Images'), os.path.join(_BASE, 'ML_models')
        except Exception:                               # fallback: Google Drive
            gdrive = '/content/drive/MyDrive/vietnamese-foods/Images'
            return gdrive, os.path.join(_BASE, 'ML_models')
    # Local: đặt data tại <project>/data/Images/
    return os.path.join(_BASE, 'data', 'Images'), os.path.join(_BASE, 'ML_models')

DATASET_BASE, SAVE_DIR = _resolve_paths()
TRAIN_DIR = os.path.join(DATASET_BASE, 'Train')
VAL_DIR   = os.path.join(DATASET_BASE, 'Validate')
TEST_DIR  = os.path.join(DATASET_BASE, 'Test')
LOG_CSV   = os.path.join(SAVE_DIR, 'training_log_v2.csv')
os.makedirs(SAVE_DIR, exist_ok=True)

print(f'Device : {DEVICE}')
if DEVICE.type == 'cuda':
    print(f'GPU    : {torch.cuda.get_device_name(0)}')

# ── Data transforms ──────────────────────────────────────────────────────────
MEAN = [0.485, 0.456, 0.406]
STD  = [0.229, 0.224, 0.225]

train_transform = transforms.Compose([
    transforms.RandomResizedCrop(IMG_SIZE, scale=(0.7, 1.0)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(25),
    transforms.RandomAffine(degrees=0, shear=10, translate=(0.1, 0.1)),
    transforms.ColorJitter(brightness=0.3, contrast=0.2, saturation=0.2, hue=0.05),
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD),
    transforms.RandomErasing(p=0.3, scale=(0.02, 0.2), ratio=(0.3, 3.3)),
])

val_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(IMG_SIZE),
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD),
])

# TTA: 5 views khác nhau để average lúc inference
tta_transforms = [
    transforms.Compose([transforms.Resize(256), transforms.CenterCrop(IMG_SIZE),
                        transforms.ToTensor(), transforms.Normalize(MEAN, STD)]),
    transforms.Compose([transforms.Resize(256), transforms.CenterCrop(IMG_SIZE),
                        transforms.RandomHorizontalFlip(p=1.0),
                        transforms.ToTensor(), transforms.Normalize(MEAN, STD)]),
    transforms.Compose([transforms.Resize(280), transforms.CenterCrop(IMG_SIZE),
                        transforms.ToTensor(), transforms.Normalize(MEAN, STD)]),
    transforms.Compose([transforms.RandomResizedCrop(IMG_SIZE, scale=(0.85, 1.0)),
                        transforms.ToTensor(), transforms.Normalize(MEAN, STD)]),
    transforms.Compose([transforms.Resize(256), transforms.CenterCrop(IMG_SIZE),
                        transforms.RandomRotation(10),
                        transforms.ToTensor(), transforms.Normalize(MEAN, STD)]),
]

train_ds = datasets.ImageFolder(TRAIN_DIR, transform=train_transform)
val_ds   = datasets.ImageFolder(VAL_DIR,   transform=val_transform)
test_ds  = datasets.ImageFolder(TEST_DIR,  transform=val_transform)

train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,
                          num_workers=4, pin_memory=True)
val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False,
                          num_workers=4, pin_memory=True)
test_loader  = DataLoader(test_ds,  batch_size=BATCH_SIZE, shuffle=False,
                          num_workers=4, pin_memory=True)

print(f'Train : {len(train_ds)} | Val : {len(val_ds)} | Test : {len(test_ds)}')
class_names = [c.replace('_', ' ').title() for c in train_ds.classes]

# ── Mixup ────────────────────────────────────────────────────────────────────
def mixup_data(x, y, alpha=0.2):
    lam = np.random.beta(alpha, alpha) if alpha > 0 else 1.0
    idx = torch.randperm(x.size(0), device=x.device)
    return lam * x + (1 - lam) * x[idx], y, y[idx], lam

def mixup_loss(criterion, pred, y_a, y_b, lam):
    return lam * criterion(pred, y_a) + (1 - lam) * criterion(pred, y_b)

# ── Model ─────────────────────────────────────────────────────────────────────
def build_model():
    # V2 weights: ImageNet top-1 = 80.9% (vs V1 = 76.1%)
    model = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V2)
    for p in model.parameters():
        p.requires_grad = False
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

# ── Training / eval loops ─────────────────────────────────────────────────────
def train_one_epoch(model, loader, optimizer, criterion, use_mixup=False):
    model.train()
    total_loss, correct, total = 0.0, 0, 0
    for imgs, labels in loader:
        imgs, labels = imgs.to(DEVICE), labels.to(DEVICE)
        optimizer.zero_grad()
        if use_mixup:
            imgs, y_a, y_b, lam = mixup_data(imgs, labels)
            outputs = model(imgs)
            loss = mixup_loss(criterion, outputs, y_a, y_b, lam)
            preds = outputs.argmax(1)
            correct += (lam * (preds == y_a).float() +
                        (1 - lam) * (preds == y_b).float()).sum().item()
        else:
            outputs = model(imgs)
            loss = criterion(outputs, labels)
            correct += (outputs.argmax(1) == labels).sum().item()
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * imgs.size(0)
        total      += imgs.size(0)
    return total_loss / total, correct / total

@torch.no_grad()
def evaluate(model, loader, criterion):
    model.eval()
    total_loss, correct, total = 0.0, 0, 0
    for imgs, labels in loader:
        imgs, labels = imgs.to(DEVICE), labels.to(DEVICE)
        out = model(imgs)
        total_loss += criterion(out, labels).item() * imgs.size(0)
        correct    += (out.argmax(1) == labels).sum().item()
        total      += imgs.size(0)
    return total_loss / total, correct / total

@torch.no_grad()
def predict_tta(model, dataset):
    """Predict với TTA: average softmax của 5 transform views."""
    model.eval()
    all_probs, all_labels = [], []
    for idx in range(len(dataset)):
        img_path = dataset.imgs[idx][0]
        label    = dataset.imgs[idx][1]
        from PIL import Image
        img = Image.open(img_path).convert('RGB')
        probs = []
        for tfm in tta_transforms:
            tensor = tfm(img).unsqueeze(0).to(DEVICE)
            prob   = F.softmax(model(tensor), dim=1).squeeze(0).cpu().numpy()
            probs.append(prob)
        all_probs.append(np.mean(probs, axis=0))
        all_labels.append(label)
    preds = np.argmax(all_probs, axis=1)
    acc   = np.mean(preds == np.array(all_labels))
    return preds, np.array(all_labels), acc

# ── Fit with logging ──────────────────────────────────────────────────────────
csv_rows = []

def fit(model, train_loader, val_loader, optimizer, criterion, scheduler,
        epochs, save_path, patience=5, stage_name='', use_mixup=False):
    best_val_acc  = 0.0
    best_weights  = copy.deepcopy(model.state_dict())
    patience_cnt  = 0
    best_val_loss = float('inf')
    history = {'train_acc': [], 'val_acc': [], 'train_loss': [], 'val_loss': [], 'lr': []}

    print(f'\n{"="*65}')
    print(f'  {stage_name}')
    print(f'{"="*65}')
    print(f'  {"Epoch":>5}  {"TrainAcc":>9}  {"ValAcc":>8}  {"Gap":>8}  '
          f'{"ValLoss":>9}  {"LR":>10}  {"Time":>6}')
    print(f'  {"-"*60}')

    for ep in range(1, epochs + 1):
        t0 = time.time()
        lr = optimizer.param_groups[0]['lr']
        tr_loss, tr_acc = train_one_epoch(model, train_loader, optimizer,
                                          criterion, use_mixup=use_mixup)
        vl_loss, vl_acc = evaluate(model, val_loader, criterion)
        scheduler.step()

        gap = tr_acc - vl_acc
        elapsed = time.time() - t0
        marker = ' ✓' if vl_acc > best_val_acc else ''

        print(f'  {ep:>5}  {tr_acc:>9.4f}  {vl_acc:>8.4f}  {gap:>+8.4f}  '
              f'{vl_loss:>9.4f}  {lr:>10.2e}  {elapsed:>5.0f}s{marker}')

        history['train_acc'].append(tr_acc)
        history['val_acc'].append(vl_acc)
        history['train_loss'].append(tr_loss)
        history['val_loss'].append(vl_loss)
        history['lr'].append(lr)
        csv_rows.append([stage_name, ep, f'{tr_acc:.4f}', f'{vl_acc:.4f}',
                         f'{gap:+.4f}', f'{vl_loss:.4f}', f'{lr:.2e}'])

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
                print(f'  EarlyStopping @ epoch {ep} (patience={patience})')
                break

    model.load_state_dict(best_weights)
    best_ep = int(np.argmax(history['val_acc']))
    ta, va = history['train_acc'][best_ep], history['val_acc'][best_ep]
    print(f'\n  Best: ep{best_ep+1}  train={ta:.4f}  val={va:.4f}  gap={ta-va:+.4f}')
    return history

# ── Stage 1 ───────────────────────────────────────────────────────────────────
model    = build_model().to(DEVICE)
criterion = nn.CrossEntropyLoss(label_smoothing=0.1)

optimizer1 = torch.optim.Adam(model.fc.parameters(), lr=1e-3, weight_decay=1e-4)
scheduler1 = CosineAnnealingLR(optimizer1, T_max=20, eta_min=1e-6)

history1 = fit(model, train_loader, val_loader, optimizer1, criterion, scheduler1,
               epochs=20, save_path=f'{SAVE_DIR}/v2_stage1.pth',
               patience=7, stage_name='STAGE 1 — head only (backbone frozen)',
               use_mixup=False)

# ── Stage 2 ───────────────────────────────────────────────────────────────────
model.load_state_dict(torch.load(f'{SAVE_DIR}/v2_stage1.pth'))
for p in model.layer4.parameters():
    p.requires_grad = True
print(f'\n  Trainable params: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}')

optimizer2 = torch.optim.Adam(
    filter(lambda p: p.requires_grad, model.parameters()), lr=1e-4, weight_decay=1e-4)
scheduler2 = CosineAnnealingLR(optimizer2, T_max=20, eta_min=1e-7)

history2 = fit(model, train_loader, val_loader, optimizer2, criterion, scheduler2,
               epochs=20, save_path=f'{SAVE_DIR}/v2_stage2.pth',
               patience=6, stage_name='STAGE 2 — fine-tune layer4 + Mixup',
               use_mixup=True)

# ── Stage 3 ───────────────────────────────────────────────────────────────────
model.load_state_dict(torch.load(f'{SAVE_DIR}/v2_stage2.pth'))
for p in model.layer3.parameters():
    p.requires_grad = True
print(f'\n  Trainable params: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}')

optimizer3 = torch.optim.Adam(
    filter(lambda p: p.requires_grad, model.parameters()), lr=1e-5, weight_decay=1e-4)
scheduler3 = CosineAnnealingLR(optimizer3, T_max=15, eta_min=1e-8)

history3 = fit(model, train_loader, val_loader, optimizer3, criterion, scheduler3,
               epochs=15, save_path=f'{SAVE_DIR}/v2_stage3.pth',
               patience=5, stage_name='STAGE 3 — fine-tune layer3+4 + Mixup',
               use_mixup=True)

# ── Save CSV log ──────────────────────────────────────────────────────────────
with open(LOG_CSV, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['stage', 'epoch', 'train_acc', 'val_acc', 'gap', 'val_loss', 'lr'])
    w.writerows(csv_rows)
print(f'\nLog saved: {LOG_CSV}')

# ── Overfitting summary ───────────────────────────────────────────────────────
print(f'\n{"="*65}')
print('  OVERFITTING ANALYSIS')
print(f'{"="*65}')
for name, h in [('Stage 1', history1), ('Stage 2', history2), ('Stage 3', history3)]:
    ta, va = h['train_acc'], h['val_acc']
    vl = h['val_loss']
    best_ep = int(np.argmax(va))
    print(f'\n  {name}:')
    print(f'    Best  ep{best_ep+1:02d}: train={ta[best_ep]:.4f}  val={va[best_ep]:.4f}  gap={ta[best_ep]-va[best_ep]:+.4f}')
    print(f'    Final ep{len(ta):02d}: train={ta[-1]:.4f}   val={va[-1]:.4f}  gap={ta[-1]-va[-1]:+.4f}')
    print(f'    Val loss: {vl[0]:.4f} → {vl[-1]:.4f}  ({"↑ diverging" if vl[-1]>vl[0] else "↓ improving"})')

# ── Evaluate: normal + TTA ────────────────────────────────────────────────────
print(f'\n{"="*65}')
print('  TEST SET EVALUATION')
print(f'{"="*65}')
model.load_state_dict(torch.load(f'{SAVE_DIR}/v2_stage3.pth'))

# Normal
model.eval()
all_preds, all_labels = [], []
with torch.no_grad():
    for imgs, labels in test_loader:
        preds = model(imgs.to(DEVICE)).argmax(1).cpu()
        all_preds.extend(preds.numpy())
        all_labels.extend(labels.numpy())
normal_acc = np.mean(np.array(all_preds) == np.array(all_labels))
print(f'\n  Normal inference accuracy: {normal_acc*100:.2f}%')

# TTA
print('  Running TTA (5 views)...')
tta_preds, tta_labels, tta_acc = predict_tta(model, test_ds)
print(f'  TTA accuracy            : {tta_acc*100:.2f}%')
print(f'\n  Classification report (TTA):')
print(classification_report(tta_labels, tta_preds, target_names=class_names))

# ── Plots — tách riêng từng file ─────────────────────────────────────────────
from sklearn.metrics import f1_score

def plot_stage(key, label, color, h):
    ep  = list(range(1, len(h['train_acc']) + 1))
    ta  = h['train_acc']; va = h['val_acc']
    vl  = h['val_loss'];  lr = h['lr']
    gap = [t - v for t, v in zip(ta, va)]

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle(label, fontsize=13, fontweight='bold')

    # Accuracy
    ax = axes[0][0]
    ax.plot(ep, ta, color=color, lw=2, marker='o', ms=4, label='Train')
    ax.plot(ep, va, color=color, lw=2, marker='s', ms=4, ls='--', label='Val')
    best_i = int(np.argmax(va))
    ax.axvline(ep[best_i], color='gray', ls=':', lw=1.2)
    ax.scatter([ep[best_i]], [va[best_i]], color='red', zorder=5, s=60,
               label=f'Best val={va[best_i]:.4f}')
    ax.set_title('Accuracy'); ax.set_xlabel('Epoch'); ax.set_ylabel('Accuracy')
    ax.legend(fontsize=9); ax.grid(alpha=0.3); ax.set_ylim(0, 1.05)

    # Val Loss
    ax = axes[0][1]
    ax.plot(ep, vl, color=color, lw=2, marker='s', ms=4)
    ax.fill_between(ep, min(vl) * 0.99, vl, alpha=0.15, color=color)
    ax.set_title('Validation Loss'); ax.set_xlabel('Epoch'); ax.set_ylabel('Loss')
    ax.grid(alpha=0.3)

    # Gap
    ax = axes[1][0]
    gap_arr = np.array(gap)
    ax.fill_between(ep, 0, gap_arr,
                    where=(gap_arr > 0),  alpha=0.35, color='#F44336', label='Overfitting zone')
    ax.fill_between(ep, gap_arr, 0,
                    where=(gap_arr <= 0), alpha=0.25, color='#4CAF50', label='Val > Train (healthy)')
    ax.plot(ep, gap_arr, color='#333333', lw=2, marker='o', ms=4, zorder=3)
    ax.axhline(0,    color='black',   lw=1.2)
    ax.axhline(0.08, color='#FF9800', lw=1.2, ls='--', label='8% threshold')
    ax.axhline(0.15, color='#F44336', lw=1.0, ls=':',  label='15% (old model)')
    best_gap_i = int(np.argmax(gap_arr)); worst_gap_i = int(np.argmin(gap_arr))
    ax.annotate(f'{gap_arr[best_gap_i]:+.3f}',
                xy=(ep[best_gap_i], gap_arr[best_gap_i]),
                xytext=(0, 8), textcoords='offset points', ha='center', fontsize=8, color='#F44336')
    ax.annotate(f'{gap_arr[worst_gap_i]:+.3f}',
                xy=(ep[worst_gap_i], gap_arr[worst_gap_i]),
                xytext=(0, -12), textcoords='offset points', ha='center', fontsize=8, color='#4CAF50')
    ax.set_title('Overfitting Gap (Train − Val Accuracy)')
    ax.set_xlabel('Epoch'); ax.set_ylabel('Gap')
    ax.legend(fontsize=8, loc='upper right'); ax.grid(alpha=0.3)

    # Learning Rate
    ax = axes[1][1]
    ax.plot(ep, lr, color='purple', lw=2, marker='^', ms=4)
    ax.fill_between(ep, 0, lr, alpha=0.15, color='purple')
    ax.set_title('Learning Rate Schedule (CosineAnnealing)')
    ax.set_xlabel('Epoch'); ax.set_ylabel('Learning Rate')
    ax.ticklabel_format(style='sci', axis='y', scilimits=(0, 0))
    ax.grid(alpha=0.3)

    plt.tight_layout()
    path = f'{SAVE_DIR}/chart_v2_{key}.png'
    plt.savefig(path, dpi=130, bbox_inches='tight')
    plt.close()
    print(f'  Chart saved: {path}')

def plot_stage_report(key, label, color, h):
    """2-panel report chart (Accuracy | Val Loss + Gap dual-axis) → report_stage_{key}.png"""
    ep      = list(range(1, len(h['train_acc']) + 1))
    ta      = np.array(h['train_acc'])
    va      = np.array(h['val_acc'])
    vl      = np.array(h['val_loss'])
    gap     = ta - va
    best_i  = int(np.argmax(va))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(label, fontsize=13, fontweight='bold')

    # ── Left: Accuracy over Epochs ────────────────────────────────────────────
    ax1.set_title('Accuracy over Epochs', fontsize=11)
    ax1.plot(ep, ta, color=color, lw=2, marker='o', ms=4, label='Train accuracy')
    ax1.plot(ep, va, color=color, lw=2, marker='s', ms=4, ls='--', label='Val accuracy')
    ax1.axvline(ep[best_i], color='gray', ls=':', lw=1.5)
    ax1.scatter([ep[best_i]], [va[best_i]], color='red', zorder=5, s=70,
                label=f'Best val = {va[best_i]:.4f}')
    ax1.set_xlabel('Epoch'); ax1.set_ylabel('Accuracy')
    ax1.set_ylim(0, 1.05)
    ax1.legend(fontsize=9); ax1.grid(alpha=0.3)

    # ── Right: Val Loss + Overfitting Gap (dual y-axis) ───────────────────────
    ax2.set_title('Val Loss & Overfitting Gap', fontsize=11)
    ax2.plot(ep, vl, color=color, lw=2, marker='s', ms=4, label='Val loss')
    ax2.set_xlabel('Epoch')
    ax2.set_ylabel('Val Loss', color=color)
    ax2.tick_params(axis='y', labelcolor=color)

    ax2b = ax2.twinx()
    ax2b.plot(ep, gap, color='#333333', lw=2, marker='o', ms=4, zorder=3)
    ax2b.axhline(0, color='black', lw=1)
    ax2b.fill_between(ep, 0,   gap, where=(gap > 0),  alpha=0.30,
                      color='#F44336', label='Overfitting')
    ax2b.fill_between(ep, gap, 0,   where=(gap <= 0), alpha=0.25,
                      color='#4CAF50', label='Val > Train')
    ax2b.set_ylabel('Gap (Train − Val)', color='#333333')
    ax2b.tick_params(axis='y', labelcolor='#333333')

    lines1, lbl1 = ax2.get_legend_handles_labels()
    lines2, lbl2 = ax2b.get_legend_handles_labels()
    ax2b.legend(lines1 + lines2, lbl1 + lbl2, fontsize=9, loc='upper right')
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    path = f'{SAVE_DIR}/report_stage_{key}.png'
    plt.savefig(path, dpi=130, bbox_inches='tight')
    plt.close()
    print(f'  Chart saved: {path}')


stage_configs = [
    ('stage1', 'Stage 1 — Head only (backbone frozen)',    '#2196F3', history1),
    ('stage2', 'Stage 2 — Fine-tune layer4 + Mixup',       '#FF9800', history2),
    ('stage3', 'Stage 3 — Fine-tune layer3+4 + Mixup',     '#4CAF50', history3),
]

print(f'\n{"="*65}\n  SAVING CHARTS\n{"="*65}')
for key, label, color, h in stage_configs:
    plot_stage(key, label, color, h)
    plot_stage_report(key, label, color, h)

# Per-class F1
f1_scores = f1_score(tta_labels, tta_preds, average=None)
sorted_idx = np.argsort(f1_scores)
fig, ax = plt.subplots(figsize=(10, 10))
bar_colors = ['#F44336' if f < 0.75 else ('#FF9800' if f < 0.85 else '#4CAF50')
              for f in f1_scores[sorted_idx]]
bars = ax.barh([class_names[i] for i in sorted_idx], f1_scores[sorted_idx],
               color=bar_colors, alpha=0.85)
ax.axvline(float(np.mean(f1_scores)), color='navy', lw=1.5, ls='--',
           label=f'Mean F1 = {np.mean(f1_scores):.3f}')
for bar, val in zip(bars, f1_scores[sorted_idx]):
    ax.text(val + 0.005, bar.get_y() + bar.get_height() / 2,
            f'{val:.2f}', va='center', fontsize=9)
ax.set_xlim(0, 1.08)
ax.set_title(f'Per-class F1 Score — TTA ({tta_acc*100:.2f}% test acc)\n'
             '■ green ≥0.85   ■ orange ≥0.75   ■ red <0.75', fontsize=12)
ax.set_xlabel('F1 Score')
ax.legend(); ax.grid(alpha=0.3, axis='x')
plt.tight_layout()
f1_path = f'{SAVE_DIR}/chart_v2_f1_perclass.png'
plt.savefig(f1_path, dpi=130, bbox_inches='tight')
plt.close()
print(f'  Chart saved: {f1_path}')

# ── chart_classification_report.png ──────────────────────────────────────────
from sklearn.metrics import precision_recall_fscore_support
import matplotlib.patches as mpatches

pr_arr, rc_arr, f1_arr, sup_arr = precision_recall_fscore_support(
    tta_labels, tta_preds, average=None)

fig_cr, ax_cr = plt.subplots(figsize=(11, 10))
n_cls = len(class_names)
ax_cr.set_xlim(0, 4); ax_cr.set_ylim(0, n_cls + 4); ax_cr.axis('off')

col_labels = ['Precision', 'Recall', 'F1-Score', 'Support']
col_x      = [1.0, 1.9, 2.8, 3.7]
row_h      = 0.90

def _cell_color(val, is_sup=False):
    if is_sup: return '#f5f5f5'
    if val >= 0.90: return '#c8e6c9'
    if val >= 0.80: return '#fff9c4'
    return '#ffcdd2'

header_y = n_cls + 3.3
ax_cr.text(0.05, header_y, 'Class', fontsize=9, fontweight='bold', va='center')
for lbl, cx in zip(col_labels, col_x):
    ax_cr.text(cx, header_y, lbl, fontsize=9, fontweight='bold', va='center', ha='center')
ax_cr.axhline(header_y - 0.45, color='#333', lw=1.2)

for i, cls in enumerate(class_names):
    y   = n_cls + 2.5 - i * row_h
    bg  = '#fafafa' if i % 2 == 0 else '#ffffff'
    ax_cr.barh(y, 4.15, height=row_h * 0.92, left=-0.1, color=bg, edgecolor='none', zorder=0)
    ax_cr.text(0.05, y, cls, fontsize=8.5, va='center')
    for val, cx, clr in zip(
            [pr_arr[i], rc_arr[i], f1_arr[i], sup_arr[i]], col_x,
            [_cell_color(pr_arr[i]), _cell_color(rc_arr[i]),
             _cell_color(f1_arr[i]), _cell_color(0, True)]):
        txt = f'{val:.2f}' if isinstance(val, float) else str(int(val))
        rect = plt.Rectangle((cx - 0.42, y - 0.38), 0.84, 0.76,
                              color=clr, zorder=1, linewidth=0)
        ax_cr.add_patch(rect)
        ax_cr.text(cx, y, txt, fontsize=8.5, va='center', ha='center', zorder=2)

div_y = 3 * row_h - 0.05
ax_cr.axhline(div_y, color='#888', lw=0.8, ls='--')

macro_p  = float(np.mean(pr_arr)); macro_r = float(np.mean(rc_arr))
macro_f1 = float(np.mean(f1_arr))
summary  = [
    ('accuracy',     '',         '',         f'{tta_acc:.2f}', len(tta_labels)),
    ('macro avg',    f'{macro_p:.2f}', f'{macro_r:.2f}', f'{macro_f1:.2f}', len(tta_labels)),
    ('weighted avg', f'{macro_p:.2f}', f'{macro_r:.2f}', f'{macro_f1:.2f}', len(tta_labels)),
]
for j, (label_s, p_, r_, f_, sup) in enumerate(summary):
    y = (2 - j) * row_h + row_h * 0.5
    ax_cr.text(0.05, y, label_s, fontsize=8.5, va='center', style='italic')
    for val, cx in zip([p_, r_, f_, str(sup)], col_x):
        ax_cr.text(cx, y, val, fontsize=8.5, va='center', ha='center')

ax_cr.set_title(f'Classification Report — ResNet50 V2 (TTA {tta_acc*100:.2f}% Test Accuracy)',
                fontsize=12, fontweight='bold', pad=14)
patches_legend = [
    mpatches.Patch(color='#c8e6c9', label='F1 ≥ 0.90  (good)'),
    mpatches.Patch(color='#fff9c4', label='0.80 ≤ F1 < 0.90'),
    mpatches.Patch(color='#ffcdd2', label='F1 < 0.80  (needs work)'),
]
ax_cr.legend(handles=patches_legend, loc='lower right', fontsize=8, framealpha=0.7)

cr_path = f'{SAVE_DIR}/chart_classification_report.png'
plt.savefig(cr_path, dpi=130, bbox_inches='tight')
plt.close()
print(f'  Chart saved: {cr_path}')

# ── chart_test_evaluation.png ─────────────────────────────────────────────────
from matplotlib.gridspec import GridSpec

sorted_rc_idx    = np.argsort(rc_arr)
sorted_rc_names  = [class_names[i] for i in sorted_rc_idx]
sorted_rc_vals   = rc_arr[sorted_rc_idx]
bar_colors_rc    = ['#F44336' if v < 0.75 else ('#FF9800' if v < 0.85 else '#4CAF50')
                    for v in sorted_rc_vals]

fig_te = plt.figure(figsize=(16, 10))
fig_te.suptitle(f'Test Set Evaluation — ResNet50 V2  (Test acc: {normal_acc*100:.2f}%)',
                fontsize=14, fontweight='bold')
gs = GridSpec(2, 2, width_ratios=[2.4, 1], hspace=0.45, wspace=0.35)
ax_left  = fig_te.add_subplot(gs[:, 0])
ax_top   = fig_te.add_subplot(gs[0, 1])
ax_bot   = fig_te.add_subplot(gs[1, 1])

# Per-class accuracy (recall proxy)
bars_rc = ax_left.barh(sorted_rc_names, sorted_rc_vals, color=bar_colors_rc,
                        alpha=0.85, edgecolor='white', linewidth=0.5)
ax_left.axvline(normal_acc, color='navy', ls='--', lw=1.5)
for bar, val in zip(bars_rc, sorted_rc_vals):
    ax_left.text(min(val + 0.007, 1.07), bar.get_y() + bar.get_height() / 2,
                 f'{val:.2f}', va='center', fontsize=8)
ax_left.set_xlim(0, 1.10)
ax_left.set_xlabel('Accuracy', fontsize=10)
ax_left.set_title('Per-class Accuracy (sorted ascending)', fontsize=11)
ax_left.grid(alpha=0.3, axis='x')
ax_left.tick_params(axis='y', labelsize=8.5)
leg_handles = [
    plt.Line2D([0], [0], color='navy', ls='--', lw=1.5,
               label=f'Overall = {normal_acc*100:.1f}%'),
    mpatches.Patch(color='#4CAF50', label='≥ 0.85'),
    mpatches.Patch(color='#FF9800', label='0.75 – 0.85'),
    mpatches.Patch(color='#F44336', label='< 0.75'),
]
ax_left.legend(handles=leg_handles, fontsize=8.5, loc='lower right')

# Normal vs TTA
width = 0.4
ax_top.bar([0], [normal_acc], width, color='#90CAF9', alpha=0.9,
           edgecolor='#1565C0', label='Normal')
ax_top.bar([1], [tta_acc],    width, color='#1565C0', alpha=0.9,
           edgecolor='#0D47A1', label='TTA (×5)')
ax_top.text(0, normal_acc + 0.0005, f'{normal_acc:.4f}',
            ha='center', va='bottom', fontsize=10, fontweight='bold')
ax_top.text(1, tta_acc    + 0.0005, f'{tta_acc:.4f}',
            ha='center', va='bottom', fontsize=10, fontweight='bold', color='#0D47A1')
ax_top.annotate(f'+{(tta_acc - normal_acc)*100:.2f}%',
                xy=(1, tta_acc), xytext=(1.32, (normal_acc + tta_acc) / 2),
                fontsize=9, color='green', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='green', lw=1.2))
ax_top.set_ylim(normal_acc - 0.02, tta_acc + 0.02)
ax_top.set_xticks([0, 1])
ax_top.set_xticklabels(['Normal\nInference', 'TTA\n(×5 views)'], fontsize=9)
ax_top.set_ylabel('Test Accuracy', fontsize=9)
ax_top.set_title('Normal vs TTA Accuracy', fontsize=10)
ax_top.legend(fontsize=8); ax_top.grid(alpha=0.3, axis='y')

# F1 distribution by group
n_good   = int(np.sum(f1_arr >= 0.85))
n_medium = int(np.sum((f1_arr >= 0.75) & (f1_arr < 0.85)))
n_weak   = int(np.sum(f1_arr < 0.75))
brs = ax_bot.bar(['Good\n(F1≥0.85)', 'Medium\n(0.75–0.85)', 'Weak\n(F1<0.75)'],
                  [n_good, n_medium, n_weak],
                  color=['#4CAF50', '#FF9800', '#F44336'], alpha=0.85, edgecolor='white')
for bar, cnt in zip(brs, [n_good, n_medium, n_weak]):
    ax_bot.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                str(cnt), ha='center', va='bottom', fontsize=11, fontweight='bold')
ax_bot.set_ylim(0, max(n_good, n_medium, n_weak) * 1.25)
ax_bot.set_ylabel('# Classes', fontsize=9)
ax_bot.set_title('F1-Score Distribution by Group', fontsize=10)
ax_bot.grid(alpha=0.3, axis='y')

te_path = f'{SAVE_DIR}/chart_test_evaluation.png'
plt.savefig(te_path, dpi=130, bbox_inches='tight')
plt.close()
print(f'  Chart saved: {te_path}')

# ── Final summary ─────────────────────────────────────────────────────────────
print(f'\n{"="*65}')
print('  FINAL SUMMARY — v1 vs v2')
print(f'{"="*65}')
print(f'  {"":30} {"v1 (ResNet50 V1)":>18} {"v2 (ResNet50 V2)":>18}')
print(f'  {"-"*66}')
print(f'  {"Backbone ImageNet acc":<30} {"76.1%":>18} {"80.9%":>18}')
print(f'  {"Stages":<30} {"2":>18} {"3":>18}')
print(f'  {"Mixup"::<30} {"No":>18} {"Yes (S2+S3)":>18}')
print(f'  {"CosineAnnealingLR":<30} {"No":>18} {"Yes":>18}')
print(f'  {"RandomErasing":<30} {"No":>18} {"Yes":>18}')
print(f'  {"Test acc (normal)":<30} {"84.41%":>18} {f"{normal_acc*100:.2f}%":>18}')
print(f'  {"Test acc (TTA)":<30} {"N/A":>18} {f"{tta_acc*100:.2f}%":>18}')
