import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple

class CrossModalAttention(nn.Module):
    """
    Fuses Spatial and Temporal representations using scaled dot-product cross-attention.
    Prevents one modality from dominating during non-standard attack variants.
    """
    def __init__(self, dim_spatial: int, dim_temporal: int, embed_dim: int):
        super(CrossModalAttention, self).__init__()
        self.q_proj = nn.Linear(dim_spatial, embed_dim)
        self.k_proj = nn.Linear(dim_temporal, embed_dim)
        self.v_proj = nn.Linear(dim_temporal, embed_dim)
        self.scale = 1.0 / (embed_dim ** 0.5)

    def forward(self, spatial_feat: torch.Tensor, temporal_feat: torch.Tensor) -> torch.Tensor:
        # spatial_feat: (B, dim_spatial) -> (B, 1, embed_dim)
        Q = self.q_proj(spatial_feat).unsqueeze(1)
        # temporal_feat: (B, dim_temporal) -> (B, 1, embed_dim)
        K = self.k_proj(temporal_feat).unsqueeze(1)
        V = self.v_proj(temporal_feat).unsqueeze(1)

        attn_weights = F.softmax(torch.bmm(Q, K.transpose(1, 2)) * self.scale, dim=-1)
        attn_applied = torch.bmm(attn_weights, V).squeeze(1)
        return attn_applied

class AegisTriModalNet(nn.Module):
    def __init__(self, num_classes: int = 4, embed_dim: int = 64):
        super(AegisTriModalNet, self).__init__()

        # =====================================================================
        # 1. SPATIAL CNN: Cache Set & Way Matrix (B, 1, 64, 64)
        # =====================================================================
        self.spatial_extractor = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(32),
            nn.LeakyReLU(negative_slope=0.01),
            nn.MaxPool2d(kernel_size=2, stride=2),  # (B, 32, 32, 32)

            nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(64),
            nn.LeakyReLU(negative_slope=0.01),
            nn.MaxPool2d(kernel_size=2, stride=2),  # (B, 64, 16, 16)

            nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(128),
            nn.LeakyReLU(negative_slope=0.01),
            nn.AdaptiveAvgPool2d((4, 4))            # (B, 128, 4, 4)
        )
        self.spatial_fc = nn.Sequential(
            nn.Linear(128 * 4 * 4, embed_dim),
            nn.LayerNorm(embed_dim),
            nn.ReLU()
        )

        # =====================================================================
        # 2. TEMPORAL Bi-LSTM: Sequential Telemetry (B, 64, 6)
        # =====================================================================
        self.temporal_lstm = nn.LSTM(
            input_size=6,
            hidden_size=embed_dim // 2,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
            dropout=0.1
        )
        self.temporal_fc = nn.Sequential(
            nn.Linear(embed_dim, embed_dim),
            nn.LayerNorm(embed_dim),
            nn.ReLU()
        )

        # =====================================================================
        # 3. MACRO TELEMETRY BRANCH: Static Window Metrics (B, 8)
        # =====================================================================
        self.macro_fc = nn.Sequential(
            nn.Linear(8, 32),
            nn.LayerNorm(32),
            nn.ReLU(),
            nn.Linear(32, 32),
            nn.ReLU()
        )

        # =====================================================================
        # 4. CROSS-ATTENTION FUSION AND CLASSIFIER
        # =====================================================================
        self.cross_attn = CrossModalAttention(dim_spatial=embed_dim, dim_temporal=embed_dim, embed_dim=embed_dim)

        fusion_dim = embed_dim + embed_dim + embed_dim + 32  # Spatial + Temporal + Attn + Macro
        
        self.fusion = nn.Sequential(
            nn.Linear(fusion_dim, 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Dropout(p=0.25),
            nn.Linear(256, 128),
            nn.LayerNorm(128)
        )
        
        self.attack_head = nn.Sequential(
            nn.Linear(128, 1) # Binary Logits
        )
        
        self.source_head = nn.Sequential(
            nn.Linear(128, num_classes) # Multi-class
        )
        
        self.severity_head = nn.Sequential(
            nn.Linear(128, 1),
            nn.Sigmoid() # 0.0 to 1.0
        )

        # Legacy / Pretrained Classifier Head (present in production checkpoint best_model.pt)
        self.classifier = nn.Sequential(
            nn.Linear(fusion_dim, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(p=0.2),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(p=0.2),
            nn.Linear(64, num_classes)
        )
        self.use_legacy_classifier = False

    def load_state_dict(self, state_dict, strict=True, assign=False):
        if any(k.startswith("classifier.") for k in state_dict.keys()) and not any(k.startswith("fusion.") for k in state_dict.keys()):
            self.use_legacy_classifier = True
            return super().load_state_dict(state_dict, strict=False, assign=assign)
        self.use_legacy_classifier = False
        return super().load_state_dict(state_dict, strict=strict, assign=assign)

    def forward(self, x_spatial: torch.Tensor, x_seq: torch.Tensor, x_macro: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        # 1. Spatial Embeddings
        x_sp = self.spatial_extractor(x_spatial)
        x_sp = torch.flatten(x_sp, start_dim=1)
        z_spatial = self.spatial_fc(x_sp)

        # 2. Temporal Embeddings
        lstm_out, _ = self.temporal_lstm(x_seq)
        # Max-pool over the time dimension to extract dominant periodic phases
        z_temporal = torch.max(lstm_out, dim=1)[0]
        z_temporal = self.temporal_fc(z_temporal)

        # 3. Cross-Modal Feature Interrogation
        z_attn = self.cross_attn(z_spatial, z_temporal)

        # 4. Macro Embeddings
        z_macro = self.macro_fc(x_macro)

        # 5. Fusion
        fused = torch.cat([z_spatial, z_temporal, z_attn, z_macro], dim=1)

        if self.use_legacy_classifier:
            source_logits = self.classifier(fused)
            # Binary attack contrast: non-benign (1..N) vs benign (0)
            attack_logits = source_logits[:, 1:].max(dim=1, keepdim=True)[0] - source_logits[:, 0:1]
            severity = torch.sigmoid(attack_logits)
            return attack_logits, source_logits, severity

        z = self.fusion(fused)
        
        attack_logits = self.attack_head(z)
        source_logits = self.source_head(z)
        severity = self.severity_head(z)
        
        return attack_logits, source_logits, severity
