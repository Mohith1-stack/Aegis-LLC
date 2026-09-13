import os
import sys
import time
import argparse
import torch
import numpy as np
from torch.utils.data import DataLoader, random_split

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dataset.train_on_archive import UniversalTelemetryDataset
from models.aegis_net import AegisTriModalNet

def evaluate(weights_path=None, csv_path=None, target_col=None, group_col=None):
    if weights_path is None:
        weights_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "daemon", "best_model.pt")
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), "archive", "Malware dataset.csv")

    print(f"Loading weights from: {weights_path}")
    print(f"Loading dataset from: {csv_path}")

    dataset = UniversalTelemetryDataset(csv_path, target_col=target_col, group_col=group_col)
    total_len = len(dataset)
    if total_len == 0:
        print("Error: Dataset yielded zero windows.")
        return

    # Deterministic 80/20 train/test split
    generator = torch.Generator().manual_seed(42)
    train_size = int(0.8 * total_len)
    test_size = total_len - train_size
    train_ds, test_ds = random_split(dataset, [train_size, test_size], generator=generator)

    model = AegisTriModalNet(num_classes=4)
    state_dict = torch.load(weights_path, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()

    def run_eval(loader, split_name):
        all_preds = []
        all_labels = []
        all_probs = []
        start_time = time.perf_counter()

        with torch.no_grad():
            for spatial, seq, macro, labels in loader:
                attack_logits, source_logits, severity = model(spatial, seq, macro)
                probs = torch.sigmoid(attack_logits).squeeze(-1).numpy()
                preds = (probs >= 0.5).astype(int)

                all_preds.extend(preds.tolist())
                all_labels.extend(labels.numpy().tolist())
                all_probs.extend(probs.tolist())

        elapsed = time.perf_counter() - start_time
        latency_per_sample_ms = (elapsed / len(all_preds)) * 1000.0

        all_preds = np.array(all_preds)
        all_labels = np.array(all_labels)
        binary_labels = (all_labels > 0).astype(int)

        accuracy = np.mean(all_preds == binary_labels) * 100.0
        tp = int(np.sum((all_preds == 1) & (binary_labels == 1)))
        fp = int(np.sum((all_preds == 1) & (binary_labels == 0)))
        tn = int(np.sum((all_preds == 0) & (binary_labels == 0)))
        fn = int(np.sum((all_preds == 0) & (binary_labels == 1)))

        precision = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 0.0
        recall = (tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        specificity = (tn / (tn + fp) * 100.0) if (tn + fp) > 0 else 0.0

        print(f"\n==================================================")
        print(f"  EVALUATION REPORT: {split_name}")
        print(f"==================================================")
        print(f"Total Samples Evaluated : {len(binary_labels)}")
        print(f"Class Breakdown         : Benign = {tn + fp} | Attack/Malware = {tp + fn}")
        print(f"--------------------------------------------------")
        print(f"Accuracy                : {accuracy:.2f}%")
        print(f"Precision               : {precision:.2f}%")
        print(f"Recall (Sensitivity)    : {recall:.2f}%")
        print(f"Specificity             : {specificity:.2f}%")
        print(f"F1 Score                : {f1:.2f}%")
        print(f"Average Inference Latency: {latency_per_sample_ms:.2f} ms/sample")
        print(f"--------------------------------------------------")
        print(f"Confusion Matrix:")
        print(f"  True Positives  (TP) : {tp}")
        print(f"  True Negatives  (TN) : {tn}")
        print(f"  False Positives (FP) : {fp}")
        print(f"  False Negatives (FN) : {fn}")
        print(f"==================================================\n")

        return {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "specificity": specificity,
            "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn}
        }

    test_metrics = run_eval(DataLoader(test_ds, batch_size=64, shuffle=False), "Test Set (20% Holdout)")
    full_metrics = run_eval(DataLoader(dataset, batch_size=64, shuffle=False), "Entire Dataset")

    return test_metrics, full_metrics

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AEGIS Universal Model Evaluation Benchmark")
    parser.add_argument("--csv", type=str, default=None, help="Path to input CSV dataset to evaluate")
    parser.add_argument("--weights", type=str, default=None, help="Path to trained model weights (.pt)")
    parser.add_argument("--target-col", type=str, default=None, help="Name of the label/target column")
    parser.add_argument("--group-col", type=str, default=None, help="Name of the process/grouping column")
    args = parser.parse_args()

    evaluate(
        weights_path=args.weights,
        csv_path=args.csv,
        target_col=args.target_col,
        group_col=args.group_col
    )
