import h5py
import numpy as np
import os

class HDF5Builder:
    def __init__(self, output_path="dataset.h5"):
        self.output_path = output_path
        print(f"Initialized HDF5 Builder -> {self.output_path}")

    def create_dataset(self, samples):
        with h5py.File(self.output_path, 'w') as f:
            f.create_dataset('spatial', data=np.stack([s['spatial_matrix'] for s in samples]))
            f.create_dataset('temporal', data=np.stack([s['temporal_sequence'] for s in samples]))
            f.create_dataset('macro', data=np.stack([s['macro_vector'] for s in samples]))
            f.create_dataset('labels', data=np.array([s['label'] for s in samples], dtype=np.uint8))
        print(f"Dataset written to {self.output_path}")
