import os
import sys
import argparse
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm

# Add parent to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.aegis_net import AegisTriModalNet
from models.focal_loss import MultiClassFocalLoss

class UniversalTelemetryDataset(Dataset):
    """
    Adaptive, zero-hardcoding dataset loader for any hardware, OS, or telemetry dataset.
    Automatically detects:
      - Binary or multi-class target labels
      - Process/grouping and time-ordering columns
      - Informative temporal features (6) and macro-architectural statistics (8)
      - Dynamic spatial matrix mapping (64x64)
    """
    def __init__(self, csv_path, seq_len=64, target_col=None, group_col=None, seq_cols=None, macro_cols=None):
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Dataset not found at path: {csv_path}")

        print(f"Loading dataset from: {csv_path}")
        df = pd.read_csv(csv_path)

        # 1. Automatic Target Column Resolution
        if target_col is None:
            candidates = ['label', 'classification', 'target', 'attack', 'class', 'malware', 'is_malware', 'is_attack']
            for c in candidates:
                if c in df.columns:
                    target_col = c
                    break
            if target_col is None:
                # Fallback: scan for any column with 2 unique values
                for c in df.columns:
                    if df[c].nunique() == 2:
                        target_col = c
                        break

        if target_col is None:
            raise ValueError(f"Could not automatically detect target column in {list(df.columns)}. Specify with --target-col")

        print(f"-> Target Column: '{target_col}'")

        def map_binary(val):
            if isinstance(val, (int, float, np.integer, np.floating)):
                return int(val > 0)
            s = str(val).strip().lower()
            if s in ['1', 'true', 'malware', 'attack', 'anomaly', 'abnormal', 'yes', 'pos', 'positive']:
                return 1
            return 0

        df['__target__'] = df[target_col].apply(map_binary)

        # 2. Automatic Grouping & Time Ordering Column Resolution
        if group_col is None:
            group_candidates = ['hash', 'pid', 'process_id', 'process', 'comm', 'id', 'session_id', 'thread_id']
            for c in group_candidates:
                if c in df.columns:
                    group_col = c
                    break

        sort_col = None
        sort_candidates = ['millisecond', 'timestamp', 'time', 'step', 'ms', 'datetime']
        for c in sort_candidates:
            if c in df.columns:
                sort_col = c
                break

        if group_col:
            print(f"-> Process/Group Column: '{group_col}'")
        if sort_col:
            print(f"-> Time-Sequence Column: '{sort_col}'")

        # 3. Automatic Feature Selection (6 Temporal + 8 Macro)
        default_seq = ['utime', 'total_vm', 'map_count', 'nvcsw', 'nivcsw', 'maj_flt']
        pmu_candidates = ['instructions', 'cycles', 'llc_misses', 'l1d_misses', 'branch_misses', 'page_faults']
        num_cols = [c for c in df.select_dtypes(include=['number']).columns if c not in [target_col, '__target__', group_col, sort_col]]
        valid_num_cols = [c for c in num_cols if df[c].std() > 1e-7]

        if seq_cols is None:
            if all(c in df.columns for c in default_seq):
                seq_cols = default_seq
            elif all(c in df.columns for c in pmu_candidates):
                seq_cols = pmu_candidates
            else:
                corrs = df[valid_num_cols].corrwith(df['__target__']).abs().sort_values(ascending=False)
                ranked_cols = corrs.dropna().index.tolist()
                seq_cols = ranked_cols[:6]
                if len(seq_cols) < 6:
                    seq_cols += [c for c in valid_num_cols if c not in seq_cols][:6 - len(seq_cols)]

        default_macro = ['map_count', 'total_vm', 'exec_vm', 'static_prio', 'nvcsw', 'nivcsw', 'utime', 'vm_truncate_count']
        if macro_cols is None:
            if all(c in df.columns for c in default_macro):
                macro_cols = default_macro
            else:
                corrs = df[valid_num_cols].corrwith(df['__target__']).abs().sort_values(ascending=False)
                macro_cols = corrs.dropna().index[:8].tolist()
                if len(macro_cols) < 8:
                    macro_cols += [c for c in valid_num_cols if c not in macro_cols][:8 - len(macro_cols)]

        # Ensure we always have 6 temporal and 8 macro features
        while len(seq_cols) < 6:
            seq_cols.append(seq_cols[-1])
        while len(macro_cols) < 8:
            macro_cols.append(macro_cols[-1])

        self.seq_cols = seq_cols[:6]
        self.macro_cols = macro_cols[:8]

        print(f"-> 6 Temporal Features : {self.seq_cols}")
        print(f"-> 8 Macro Features    : {self.macro_cols}")

        # Z-score normalization parameters
        means = df[self.seq_cols].mean()
        stds = df[self.seq_cols].std().replace(0, 1.0)
        m_means = df[self.macro_cols].mean()
        m_stds = df[self.macro_cols].std().replace(0, 1.0)

        # 4. Sequential Window Extraction
        self.samples = []
        if group_col and group_col in df.columns:
            grouped = df.groupby(group_col)
            groups = [g for _, g in grouped]
        else:
            groups = [df]

        print("Building sequential multi-modal windows...")
        for group in tqdm(groups, desc="Processing series"):
            if sort_col and sort_col in group.columns:
                group = group.sort_values(sort_col)

            f_arr = ((group[self.seq_cols] - means) / stds).values.astype(np.float32)
            m_arr = ((group[self.macro_cols] - m_means) / m_stds).values.astype(np.float32)
            labels = group['__target__'].values

            stride = max(1, seq_len // 2)
            if len(f_arr) < seq_len:
                pad_len = seq_len - len(f_arr)
                f_pad = np.pad(f_arr, ((0, pad_len), (0, 0)), mode='edge')
                m_pad = m_arr.mean(axis=0)
                spatial = np.zeros((1, 64, 64), dtype=np.float32)
                idx1 = int(np.clip(abs(m_pad[0]) * 10, 0, 63))
                idx2 = int(np.clip(abs(m_pad[1 % len(m_pad)]) * 10, 0, 63))
                spatial[0, :idx1, :idx2] = 1.0
                self.samples.append({
                    'spatial': spatial,
                    'temporal': f_pad,
                    'macro': m_pad,
                    'label': int(labels[0])
                })
            else:
                for i in range(0, len(f_arr) - seq_len + 1, stride):
                    window = f_arr[i:i+seq_len]
                    macro = m_arr[i:i+seq_len].mean(axis=0)
                    spatial = np.zeros((1, 64, 64), dtype=np.float32)
                    idx1 = int(np.clip(abs(macro[0]) * 10, 0, 63))
                    idx2 = int(np.clip(abs(macro[1 % len(macro)]) * 10, 0, 63))
                    spatial[0, :idx1, :idx2] = 1.0
                    self.samples.append({
                        'spatial': spatial,
                        'temporal': window,
                        'macro': macro,
                        'label': int(labels[i])
                    })

        print(f"Generated {len(self.samples)} sequence windows.")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        s = self.samples[idx]
        return (
            torch.from_numpy(s['spatial']),
            torch.from_numpy(s['temporal']),
            torch.from_numpy(s['macro']),
            torch.tensor(s['label'], dtype=torch.long)
        )

# Backward compatibility alias
MalwareArchiveDataset = UniversalTelemetryDataset

def train(csv_path=None, target_col=None, group_col=None, epochs=8, batch_size=32, lr=1e-3, save_path=None):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using compute device: {device}")

    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), "archive", "Malware dataset.csv")
    if save_path is None:
        save_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "daemon", "best_model.pt")

    dataset = UniversalTelemetryDataset(csv_path, target_col=target_col, group_col=group_col)

    if len(dataset) == 0:
        print("Error: Dataset yielded zero sequential windows.")
        return

    # Deterministic split
    generator = torch.Generator().manual_seed(42)
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_ds, val_ds = torch.utils.data.random_split(dataset, [train_size, val_size], generator=generator)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=64, shuffle=False)

    model = AegisTriModalNet(num_classes=4).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = MultiClassFocalLoss()
    bce_loss_fn = nn.BCEWithLogitsLoss()
    mse_loss_fn = nn.MSELoss()

    best_val_acc = 0.0

    for epoch in range(epochs):
        model.train()
        total_loss = 0
        correct = 0
        total = 0

        for spatial, seq, macro, labels in train_loader:
            spatial, seq, macro, labels = spatial.to(device), seq.to(device), macro.to(device), labels.to(device)

            optimizer.zero_grad()
            attack_logits, source_logits, severity = model(spatial, seq, macro)

            binary_labels = (labels > 0).float().unsqueeze(1)
            severity_labels = binary_labels.clone()

            bce_loss = bce_loss_fn(attack_logits, binary_labels)
            source_loss = criterion(source_logits, labels)
            mse_loss = mse_loss_fn(severity, severity_labels)

            loss = bce_loss + 0.5 * source_loss + 0.5 * mse_loss
            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            preds = (torch.sigmoid(attack_logits) >= 0.5).long()
            correct += (preds == binary_labels.long()).sum().item()
            total += labels.size(0)

        scheduler.step()
        train_acc = correct / total * 100.0

        # Validation pass
        model.eval()
        val_correct = 0
        val_total = 0
        with torch.no_grad():
            for spatial, seq, macro, labels in val_loader:
                spatial, seq, macro, labels = spatial.to(device), seq.to(device), macro.to(device), labels.to(device)
                attack_logits, _, _ = model(spatial, seq, macro)
                binary_labels = (labels > 0).float().unsqueeze(1)
                preds = (torch.sigmoid(attack_logits) >= 0.5).long()
                val_correct += (preds == binary_labels.long()).sum().item()
                val_total += labels.size(0)

        val_acc = val_correct / val_total * 100.0
        print(f"Epoch {epoch+1}/{epochs} | Train Loss: {total_loss/len(train_loader):.4f} | Train Acc: {train_acc:.2f}% | Val Acc: {val_acc:.2f}%")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), save_path)
            print(f"  -> Best model saved to {save_path} (Val Acc: {val_acc:.2f}%)")

    print(f"\nTraining complete. Peak Validation Accuracy: {best_val_acc:.2f}%")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AEGIS Universal Multi-Modal Training Pipeline")
    parser.add_argument("--csv", type=str, default=None, help="Path to input CSV dataset")
    parser.add_argument("--target-col", type=str, default=None, help="Name of the label/target column")
    parser.add_argument("--group-col", type=str, default=None, help="Name of the process/grouping column")
    parser.add_argument("--epochs", type=int, default=8, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--save-path", type=str, default=None, help="Path to save trained weights")
    args = parser.parse_args()

    train(
        csv_path=args.csv,
        target_col=args.target_col,
        group_col=args.group_col,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        save_path=args.save_path
    )
