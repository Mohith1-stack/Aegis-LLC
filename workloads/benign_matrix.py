import numpy as np
import time

def run_matrix_multiplication():
    print("Starting benign matrix multiplication workload (High IPC, high cache hits)...")
    while True:
        # 2048 x 2048 float64 matrices
        A = np.random.rand(2048, 2048)
        B = np.random.rand(2048, 2048)
        C = np.dot(A, B)
        # Small sleep to prevent total CPU lockup
        time.sleep(0.01)

if __name__ == "__main__":
    run_matrix_multiplication()
