import torch
from typing import Tuple
import matplotlib.pyplot as plt 
from datetime import datetime as dt
from torch_geometric.loader import DataLoader

import scripts.datap.graph.const as c
from scripts.datap.graph.dataset import MarketDataset


class EarlyStopping:
    def __init__(self, patience: int = 10, min_delta: float = 0.0):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss = float('inf')
        self.early_stop = False
        self.save_path = f"best_model_{dt.now().strftime('%Y%m%d_%H%M%S')}.pt"

    def __call__(self, val_loss: float, model: torch.nn.Module):
        if val_loss < self.best_loss:
            delta = self.best_loss - val_loss
            self.best_loss = val_loss
            self.counter = 0
            self.checkpoint(model, path=self.save_path)
            if delta < self.min_delta: # case(1): using min_delta
                self.early_stop = True
                print(f"Early stopping triggered by delta [(min_delta): {delta:.6f}]")
        else:
            self.counter += 1
            if self.counter >= self.patience: # case(2): using patience
                self.early_stop = True
                print(f"Early stopping triggered by patience")

    def checkpoint(self, model: torch.nn.Module, path: str):
        if self.best_loss < float('inf'):
            torch.save(model.state_dict(), path)
            print(f"Model checkpoint saved with validation loss: {self.best_loss}")


class RealTimePlot:
    def __init__(self):
        self.train_losses = []
        self.valid_losses = []
        plt.ion()  # Turn on interactive mode
        self.fig, self.ax = plt.subplots()

    def update(self, train_loss: float, valid_loss: float):
        self.train_losses.append(train_loss)
        self.valid_losses.append(valid_loss)
        self.ax.clear()
        self.ax.plot(range(1, len(self.train_losses) + 1), self.train_losses, label='Train Loss')
        self.ax.plot(range(1, len(self.valid_losses) + 1), self.valid_losses, label='Valid Loss')
        self.ax.set_xlabel('Epoch')
        self.ax.set_ylabel('Loss')
        self.ax.set_title('Training and Validation Loss')
        self.ax.legend()
        plt.draw()
        plt.pause(0.001)  # Pause to allow the plot to update

    def close(self):
        plt.savefig(f"loss_plot_{dt.now().strftime('%Y%m%d_%H%M%S')}.png")
        plt.ioff()  # Turn off interactive mode
        plt.show()


def get_loader(dataset:MarketDataset, batch_size:int) -> Tuple[DataLoader, DataLoader]:
    train_idx = list(range(0, c.TRAIN_RANGE_TID[1] + 1 - c.TRAIN_RANGE_TID[0]))
    valid_idx = list(range(0, c.VALID_RANGE_TID[1] + 1 - c.VALID_RANGE_TID[0]))
    train_loader = DataLoader(dataset.index_select(train_idx), batch_size=batch_size, shuffle=True)
    valid_loader = DataLoader(dataset.index_select(valid_idx), batch_size=batch_size, shuffle=False)
    return train_loader, valid_loader