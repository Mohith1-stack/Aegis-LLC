import numpy as np
import torch
from dataclasses import dataclass
from typing import Dict, Tuple

@dataclass
class WindowBuffer:
    capacity: int = 64
    feature_dim: int = 6
    ptr: int = 0
    is_full: bool = False

    def __post_init__(self):
        self.buffer = np.zeros((self.capacity, self.feature_dim), dtype=np.float32)

    def push(self, sample: np.ndarray):
        self.buffer[self.ptr] = sample
        self.ptr = (self.ptr + 1) % self.capacity
        if self.ptr == 0:
            self.is_full = True

    def get_ordered(self) -> np.ndarray:
        if not self.is_full:
            return self.buffer[:self.ptr]
        return np.roll(self.buffer, -self.ptr, axis=0)

class OnlineWelfordStandardizer:
    """
    Zero-overhead, continuous statistical standardization.
    Computes numerically stable online running mean and variance.
    """
    def __init__(self, feature_dim: int):
        self.count = 0
        self.mean = np.zeros(feature_dim, dtype=np.float64)
        self.M2 = np.zeros(feature_dim, dtype=np.float64)

    def update(self, x: np.ndarray):
        self.count += 1
        delta = x - self.mean
        self.mean += delta / self.count
        delta2 = x - self.mean
        self.M2 += delta * delta2

    def transform(self, x: np.ndarray) -> np.ndarray:
        if self.count < 2:
            return x
        variance = self.M2 / (self.count - 1)
        std = np.sqrt(variance) + 1e-6
        return ((x - self.mean) / std).astype(np.float32)

class TelemetryEngine:
    def __init__(self):
        self.buffers: Dict[int, WindowBuffer] = {}
        self.standardizers: Dict[int, OnlineWelfordStandardizer] = {}

    def process_raw_telemetry(self, raw_record: dict) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Transforms raw event stream into (x_spatial, x_seq, x_macro) tensors.
        """
        pid = raw_record["pid"]
        if pid not in self.buffers:
            self.buffers[pid] = WindowBuffer()
            self.standardizers[pid] = OnlineWelfordStandardizer(feature_dim=6)

        # 1. Temporal Feature Extraction
        # Raw sample: [instr, cycles, llc_miss, l1d_miss, br_miss, faults]
        raw_vec = np.array([
            raw_record["instructions"],
            raw_record["cycles"],
            raw_record["llc_misses"],
            raw_record["l1d_misses"],
            raw_record["branch_misses"],
            raw_record["page_faults"]
        ], dtype=np.float32)

        self.standardizers[pid].update(raw_vec)
        norm_vec = self.standardizers[pid].transform(raw_vec)
        self.buffers[pid].push(norm_vec)

        # 2. Sequential Window Matrix (B, 64, 6)
        seq_data = self.buffers[pid].get_ordered()
        if len(seq_data) < 64:
            # Pad early sequences
            padded = np.zeros((64, 6), dtype=np.float32)
            padded[-len(seq_data):] = seq_data
            seq_data = padded

        # 3. Attributed Spatial Tensor Generation (1, 64, 64)
        # We project physical/virtual address collision histograms into a 64x64 cache set matrix
        # reconstructed from page-fault addresses and LLC-miss telemetry
        spatial_matrix = np.zeros((1, 64, 64), dtype=np.float32)
        target_set = (raw_record.get("last_fault_addr", 0) >> 6) % 64
        way_proxy = int(np.clip(raw_record["llc_misses"] / (raw_record["instructions"] + 1) * 64, 0, 63))
        spatial_matrix[0, target_set, :way_proxy] = 1.0

        # 4. Macro Telemetry Feature Vector (8-dim)
        ipc = raw_record["instructions"] / (raw_record["cycles"] + 1e-5)
        llc_miss_rate = raw_record["llc_misses"] / (raw_record["instructions"] + 1e-5)
        br_miss_ratio = raw_record["branch_misses"] / (raw_record["instructions"] + 1e-5)

        macro_vector = np.array([
            ipc,
            llc_miss_rate,
            br_miss_ratio,
            raw_record["page_faults"],
            raw_record.get("cpu_temp_delta", 0.0),
            raw_record.get("context_switches", 0.0),
            raw_record.get("memory_bandwidth_mb", 0.0),
            float(raw_record["cpu"])
        ], dtype=np.float32)

        return (
            torch.from_numpy(spatial_matrix).unsqueeze(0),
            torch.from_numpy(seq_data).unsqueeze(0),
            torch.from_numpy(macro_vector).unsqueeze(0)
        )
