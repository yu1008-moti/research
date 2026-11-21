import os
import torch
from typing import Tuple, List, Optional
import matplotlib.pyplot as plt 
from datetime import datetime as dt
from torch_geometric.loader import DataLoader
from torch_geometric.data import Dataset, Batch, HeteroData
import random
from collections import defaultdict
import duckdb as db
import pandas as pd

import scripts.datap.graph.const as c
from scripts.datap.graph.dataset import MarketDataset

GREEN = '\033[92m'
MAGENTA = '\033[95m'
CYAN = '\033[96m'
END = '\033[0m'

MyScaler = dict[str, dict[Tuple[int, str], dict[str, float]]]

SAVE_MODELS_DIR = "save_models"


def get_model_dir(model_id: str) -> str:
    """save_models/<model_id>/ を作成して返す. モデルに関する全出力の保存先."""
    path = os.path.join(SAVE_MODELS_DIR, str(model_id))
    os.makedirs(path, exist_ok=True)
    return path


class EarlyStopping:

    def __init__(self, model_dir: str, patience: int = 10, min_delta: float = 0.0):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss = float('inf')
        self.early_stop = False
        self.save_path = os.path.join(model_dir, "best_model.pt")


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

    def __init__(self, model_dir: str):
        self.model_dir = model_dir
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
        plt.savefig(os.path.join(self.model_dir, "loss_plot.png"))
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


class Evaluation:
    """評価期間 (eval_split) に対するモデル評価.

    - 分類指標: CrossEntropy loss / accuracy
    - 売買シミュレーション: 各日 P(pos)-P(neg) の上位 top_k 銘柄を等ウェイトでロング,
      下位 top_k 銘柄をショートした日次リターン, およびリスクフリーレートを用いた Sharpe ratio

    前提: データセット index = tID - c._BASE, 返り値 NxRi と r_f は同一単位 (日次).
    """

    CLASS_POS = 2  # labels: [neg, neu, pos]
    CLASS_NEG = 0

    def __init__(self, model: torch.nn.Module, dataset: MarketDataset, criterion: torch.nn.Module,
                 eval_split: Tuple[int, int], model_dir: str, top_k: int = 20):
        if isinstance(eval_split[0], (tuple, list)):
            eval_split = eval_split
        self.model_dir = model_dir
        self.model = model
        self.dataset = dataset
        self.criterion = criterion
        self.eval_split = (int(eval_split[0]), int(eval_split[1]))
        self.top_k = top_k
        self.result: dict[str, float] = {}
        self.daily: Optional[pd.DataFrame] = None


    def _get_risk_free_rate(self) -> pd.DataFrame:
        conn = db.connect(database=":memory:", read_only=False)
        conn.execute(f"attach '{c.ACT_DB_PATH}' as act;")
        conn.execute(f"attach '{c.DEV_DB_PATH}' as dev;")
        df = conn.execute("SELECT * from dev.tool.risk_free;").df()[['tID', 'r_f']]
        conn.close()
        return df


    def simulate(self) -> pd.DataFrame:
        """評価期間を1日ずつ推論し, 日次の損失・正解数・ポートフォリオリターンを返す."""
        rf = self._get_risk_free_rate().set_index('tID')['r_f']
        rows = []

        self.model.eval()
        with torch.no_grad():
            for idx in range(self.eval_split[0], self.eval_split[1] + 1):
                data = self.dataset.get(idx)
                labels  = torch.argmax(data["stock"].labels.long(), dim=1).to(c.DEVICE)
                returns = data["stock"].returns.reshape(-1).to(c.DEVICE)
                output  = self.model(data)

                loss = self.criterion(output, labels)
                correct = (output.argmax(dim=1) == labels).sum().item()

                # スコア = P(pos) - P(neg) の順位で long / short
                prob  = torch.softmax(output, dim=1)
                score = prob[:, self.CLASS_POS] - prob[:, self.CLASS_NEG]
                k = min(self.top_k, score.numel() // 2) or 1
                order = torch.argsort(score, descending=True)
                r_long  = returns[order[:k]].mean().item()
                r_short = returns[order[-k:]].mean().item()

                tID = idx + c._BASE
                rows.append({
                    'tID': tID, 'loss': float(loss.item()), 'correct': correct,
                    'n': labels.size(0), 'r_long': r_long, 'r_short': r_short,
                    'r_f': float(rf.get(tID, 0.0)),
                })

        self.daily = pd.DataFrame(rows)
        self.daily['r_long_short'] = self.daily['r_long'] - self.daily['r_short']
        return self.daily


    @staticmethod
    def _sharpe(excess: pd.Series, periods: int = 252) -> float:
        sd = excess.std()
        return float(excess.mean() / sd * (periods ** 0.5)) if sd and sd > 0 else 0.0


    def evaluate(self) -> dict[str, float]:
        """simulate() を実行して集計し, 結果を表示して dict で返す."""
        df = self.simulate() if self.daily is None else self.daily
        n_total = int(df['n'].sum())
        self.result = {
            'loss'          : float(df['loss'].mean()),
            'accuracy'      : float(df['correct'].sum() / n_total) if n_total > 0 else 0.0,
            'long_mean'     : float(df['r_long'].mean()),
            'long_sharpe'   : self._sharpe(df['r_long'] - df['r_f']),
            'ls_mean'       : float(df['r_long_short'].mean()),
            'ls_sharpe'     : self._sharpe(df['r_long_short']),
            'long_cum'      : float((1 + df['r_long']).prod() - 1), # type: ignore
            'ls_cum'        : float((1 + df['r_long_short']).prod() - 1), # type: ignore
        }
        print(f"{CYAN}[Evaluation] tID idx {self.eval_split[0]}-{self.eval_split[1]} ({len(df)} days), top_k={self.top_k}{END}")
        for k, v in self.result.items():
            print(f"  {k:12s}: {v:.4f}")
        return self.result


    def save(self, path: Optional[str] = None) -> str:
        """日次結果を CSV に保存する."""
        assert self.daily is not None, "Call evaluate() first."
        path = path or os.path.join(self.model_dir, "eval_daily.csv")
        self.daily.to_csv(path, index=False)
        return path
