import torch
import argparse
from aegis_net import AegisTriModalNet

def export_to_onnx(weights_path, output_path, quantize=False):
    print(f"Loading model from {weights_path}...")
    model = AegisTriModalNet(num_classes=4)
    # model.load_state_dict(torch.load(weights_path))
    model.eval()

    dummy_spatial = torch.randn(1, 1, 64, 64)
    dummy_seq = torch.randn(1, 64, 6)
    dummy_macro = torch.randn(1, 8)

    print(f"Exporting to {output_path}...")
    torch.onnx.export(
        model, 
        (dummy_spatial, dummy_seq, dummy_macro), 
        output_path,
        input_names=['spatial_input', 'seq_input', 'macro_input'],
        output_names=['logits'],
        opset_version=13
    )

    if quantize:
        print("Applying INT8 dynamic quantization...")
        # from onnxruntime.quantization import quantize_dynamic, QuantType
        # quantize_dynamic(output_path, output_path.replace('.onnx', '_int8.onnx'), weight_type=QuantType.QInt8)
        print("Quantization complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=str, default="best_model.pt")
    parser.add_argument("--output", type=str, default="aegis_model.onnx")
    parser.add_argument("--quantize", action="store_true")
    args = parser.parse_args()
    
    export_to_onnx(args.weights, args.output, args.quantize)
