import os
import sys
import torch
import pytest
from torch.utils.data import DataLoader, random_split

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dataset.train_on_archive import MalwareArchiveDataset
from models.aegis_net import AegisTriModalNet

def test_model_accuracy_above_95():
    """Validates that AegisTriModalNet achieves > 95% accuracy on holdout test set."""
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dataset", "archive", "Malware dataset.csv")
    weights_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "daemon", "best_model.pt")

    if not os.path.exists(csv_path) or not os.path.exists(weights_path):
        pytest.skip("Dataset or model weights not present.")

    dataset = MalwareArchiveDataset(csv_path)
    generator = torch.Generator().manual_seed(42)
    train_size = int(0.8 * len(dataset))
    _, test_ds = random_split(dataset, [train_size, len(dataset) - train_size], generator=generator)

    model = AegisTriModalNet(num_classes=4)
    state_dict = torch.load(weights_path, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()

    correct = 0
    total = 0
    loader = DataLoader(test_ds, batch_size=64, shuffle=False)

    with torch.no_grad():
        for spatial, seq, macro, labels in loader:
            attack_logits, _, _ = model(spatial, seq, macro)
            preds = (torch.sigmoid(attack_logits) >= 0.5).long().squeeze()
            binary_labels = (labels > 0).long()
            correct += (preds == binary_labels).sum().item()
            total += labels.size(0)

    accuracy = correct / total * 100.0
    print(f"\nHoldout Test Accuracy: {accuracy:.2f}%")
    assert accuracy >= 95.0, f"Accuracy dropped below 95%: {accuracy:.2f}%"
