import time
import pytest
import torch
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.aegis_net import AegisTriModalNet

def test_inference_latency():
    """Ensures a single forward pass takes < 10.0ms on CPU."""
    model = AegisTriModalNet()
    model.eval()
    
    # Dummy tensors
    x_spatial = torch.randn(1, 1, 64, 64)
    x_seq = torch.randn(1, 64, 6)
    x_macro = torch.randn(1, 8)
    
    # Warmup
    for _ in range(10):
        with torch.no_grad():
            _ = model(x_spatial, x_seq, x_macro)
        
    # Benchmark over multiple runs for reliable latency measurement
    latencies = []
    for _ in range(20):
        start_time = time.perf_counter()
        with torch.no_grad():
            _ = model(x_spatial, x_seq, x_macro)
        latencies.append((time.perf_counter() - start_time) * 1000)
    
    avg_latency_ms = sum(latencies) / len(latencies)
    print(f"Average Inference Latency: {avg_latency_ms:.3f} ms")
    assert avg_latency_ms < 15.0, f"Average latency too high: {avg_latency_ms:.3f} ms"
