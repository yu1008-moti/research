import torch
from typing import Tuple, List, Optional
import matplotlib.pyplot as plt 
from datetime import datetime as dt
from torch_geometric.loader import DataLoader
from torch_geometric.data import Dataset, Batch, HeteroData
import random
from collections import defaultdict

import scripts.datap.graph.const as c
from scripts.datap.graph.dataset import MarketDataset

GREEN = '\033[92m'
MAGENTA = '\033[95m'
CYAN = '\033[96m'
END = '\033[0m'

MyScaler = dict[str, dict[Tuple[int, str], dict[str, float]]]

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
            self.best_loss = val_loss
            self.counter = 0
            self.checkpoint(model, path=self.save_path)
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
        plt.show(block=False)  # ウィンドウを学習開始時点で表示する
        plt.pause(0.1)


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
        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()
        plt.pause(0.1)  # GUIイベントを処理して再描画させる


    def close(self):
        plt.savefig(f"loss_plot_{dt.now().strftime('%Y%m%d_%H%M%S')}.png")
        plt.ioff()  # Turn off interactive mode
        plt.show()


class SampledMarketDataLoader:

    def __init__(self, dataset: MarketDataset, batch_size: int, train_ds_range: Tuple[int, int], valid_ds_range: Tuple[int, int], k: int = 100):
        self.dataset = dataset
        self.batch_size = batch_size
        self.train_range = list(range(train_ds_range[0], train_ds_range[1]))
        self.valid_range = list(range(valid_ds_range[0], valid_ds_range[1]))
        self.k = k


    def _get_train_indices(self) -> List[int]: # not used
        train_indices = random.sample(self.train_range, self.k)
        return train_indices



    def _data_transform(self, dl: DataLoader, scaler: Optional[MyScaler]=None) -> None|MyScaler:
        res = None
        if scaler is None:
            stack  = defaultdict( lambda: defaultdict( lambda: torch.tensor([])))
            scaler = defaultdict( lambda: defaultdict( lambda: defaultdict( lambda: []))) # type: ignore
            funcList  = [torch.min, torch.max, torch.median, torch.mean, torch.std]
            funcAlias = ['min', 'max', 'median', 'mean', 'std']

            assert scaler is not None, "Scaler should be initialized before data transformation."

            for d in dl:
                for nt in ["stock", "statement", "mktidx", "future"]:
                    for ft, i in c.ND[nt].items():
                        stack[nt][ft] = torch.cat((stack[nt][ft], d[nt].x[:, :, i].reshape(-1)), dim=0)
            
            for nt in ["stock", "statement", "mktidx", "future"]:
                for ft, i in c.ND[nt].items():
                    for f, alias in zip(funcList, funcAlias):
                        scaler[nt][i, ft][alias] = f(stack[nt][ft]) # type: ignore
            res = scaler

        for d in dl:
            for nt in ["stock", "statement", "mktidx", "future"]:
                for ft, i in c.ND[nt].items():
                    mean, std = scaler[nt][i, ft]['mean'], scaler[nt][i, ft]['std']
                    d[nt].x[:, :, i] = (d[nt].x[:, :, i] - mean) / std
        
        print(f"{GREEN}[{'train' if scaler is not None else 'valid'}]Data transformation completed: asinh and z-score normalization applied{END}")
        return res

    def get_loader(self) -> Tuple[DataLoader, DataLoader]:
        train_dataset = self.dataset.index_select(self.train_range)
        valid_dataset = self.dataset.index_select(self.valid_range)
        train_loader = DataLoader(train_dataset, batch_size=self.batch_size, shuffle=True , pin_memory=True, num_workers=4)
        valid_loader = DataLoader(valid_dataset, batch_size=self.batch_size, shuffle=False, pin_memory=True, num_workers=4)
        scaler = self._data_transform(train_loader)
        self._data_transform(valid_loader, scaler=scaler)
        return train_loader, valid_loader