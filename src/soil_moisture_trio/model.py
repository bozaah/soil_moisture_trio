import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset

# Custom Dataset
class SoilData(Dataset):
    def __init__(self, X: np.ndarray, y: np.ndarray):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.float32).unsqueeze(1)
    
    def __len__(self) -> int:
        return len(self.X)
    
    def __getitem__(self, idx: int):
        return self.X[idx], self.y[idx]

# PyTorch Model (now 5 inputs)
class DryWetClassifier(nn.Module):
    def __init__(self, input_size: int = 5):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(input_size, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(x)