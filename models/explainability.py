import os
import sys
import torch
import torch.nn.functional as F
import numpy as np
import matplotlib.pyplot as plt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.aegis_net import AegisTriModalNet

class GradCAM:
    def __init__(self, model, target_layer):
        self.model = model
        self.target_layer = target_layer
        self.gradients = None
        self.activations = None
        
        # Hook into the target layer
        target_layer.register_forward_hook(self.save_activation)
        target_layer.register_backward_hook(self.save_gradient)

    def save_activation(self, module, input, output):
        self.activations = output

    def save_gradient(self, module, grad_input, grad_output):
        self.gradients = grad_output[0]

    def generate_heatmap(self, spatial, seq, macro):
        self.model.eval()
        
        # Forward pass
        attack_logits, _, _ = self.model(spatial, seq, macro)
        
        # Backward pass on the binary attack prediction
        self.model.zero_grad()
        attack_logits.backward()
        
        # Pool the gradients across the spatial dimensions
        pooled_gradients = torch.mean(self.gradients, dim=[0, 2, 3])
        
        # Weight the channels by the gradients
        activations = self.activations.detach()[0]
        for i in range(activations.size(0)):
            activations[i, :, :] *= pooled_gradients[i]
            
        # Average the channels to create the heatmap
        heatmap = torch.mean(activations, dim=0).cpu().numpy()
        
        # ReLU to keep only positive influence
        heatmap = np.maximum(heatmap, 0)
        
        # Normalize
        if np.max(heatmap) > 0:
            heatmap /= np.max(heatmap)
            
        return heatmap

def run_explainability_demo():
    model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "daemon", "best_model.pt")
    if not os.path.exists(model_path):
        print("Model weights not found. Please train the model first.")
        return

    model = AegisTriModalNet(num_classes=4)
    model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
    model.eval()

    # The last conv layer in the spatial extractor
    target_layer = model.spatial_extractor[4] # The second Conv2d layer

    cam = GradCAM(model, target_layer)

    # Generate dummy malicious data (e.g. intense cache probing on early sets)
    x_spatial = torch.zeros((1, 1, 64, 64))
    x_spatial[0, 0, 10:20, 10:20] = 1.0 # Probing cache sets 10-20
    x_seq = torch.randn((1, 64, 6))
    x_macro = torch.randn((1, 8))

    print("Generating Grad-CAM Heatmap...")
    heatmap = cam.generate_heatmap(x_spatial, x_seq, x_macro)

    # Plot
    plt.figure(figsize=(8, 8))
    plt.imshow(x_spatial[0,0].numpy(), cmap='gray', alpha=0.5, interpolation='nearest')
    plt.imshow(heatmap, cmap='jet', alpha=0.5, interpolation='bilinear')
    plt.title("Grad-CAM: CPU L3 Cache Vulnerability Hotspots")
    plt.colorbar(label="Importance Score")
    
    save_path = os.path.join(os.path.dirname(__file__), "gradcam_output.png")
    plt.savefig(save_path)
    print(f"Explainability heatmap saved to {save_path}")

if __name__ == "__main__":
    run_explainability_demo()
