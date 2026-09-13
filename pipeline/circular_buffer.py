import numpy as np

class CircularBuffer:
    def __init__(self, capacity, feature_dim):
        self.capacity = capacity
        self.feature_dim = feature_dim
        self.buffer = np.zeros((capacity, feature_dim), dtype=np.float32)
        self.head = 0
        self.full = False

    def push(self, data):
        self.buffer[self.head] = data
        self.head = (self.head + 1) % self.capacity
        if self.head == 0:
            self.full = True

    def get_window(self):
        if not self.full:
            return self.buffer[:self.head]
        return np.concatenate((self.buffer[self.head:], self.buffer[:self.head]))
