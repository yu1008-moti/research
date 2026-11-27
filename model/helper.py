import os
import torch
from typing import Tuple, List, Optional
import matplotlib.pyplot as plt 
from torch_geometric.loader import DataLoader
from schedulefree import RAdamScheduleFree
import random
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


    def __call__(self, val_loss: float, model: torch.nn.Module, optimizer: RAdamScheduleFree) -> None:
        if val_loss < self.best_loss:
            self.best_loss = val_loss
            self.counter = 0
            self.checkpoint(model, optimizer=optimizer, path=self.save_path)
        else:
            self.counter += 1
            if self.counter >= self.patience: # case(2): using patience
                self.early_stop = True
                print(f"Early stopping triggered by patience")


    def checkpoint(self, model: torch.nn.Module, optimizer: RAdamScheduleFree, path: str):
        if self.best_loss < float('inf'):
            torch.save({"model": model.state_dict(), "optimizer": optimizer.state_dict()}, path)
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


    @staticmethod
    def compute_scaler(dl: DataLoader) -> dict[str, Tuple[torch.Tensor, torch.Tensor]]:
        """学習データ全体から, ノード型ごと・特徴量ごとの mean / std を求める (padding 部分は除外).

        DataLoader が返すバッチは毎回ディスクから読み直されるため, バッチを書き換えても正規化は残らない.
        そこで統計量だけをここで求め, 正規化はモデル側 (MarketHGTModel.forward) で毎回行う.
        """
        acc = {nt: [0.0, 0.0, 0.0] for nt in c.HETERO_NODE_TYPES}  # [件数, 和, 二乗和]
        for d in dl:
            for nt in c.HETERO_NODE_TYPES:
                x = d[nt].x.double()                                                 # [N, L, F]
                valid = torch.arange(x.size(1))[None, :] < d[nt].seq_len[:, None]    # [N, L] padding 以外
                v = x[valid]                                                         # [n, F]
                acc[nt][0] += v.size(0)
                acc[nt][1] = acc[nt][1] + v.sum(dim=0)
                acc[nt][2] = acc[nt][2] + (v ** 2).sum(dim=0)
        scaler = {}
        for nt, (n, s, ss) in acc.items():
            mean = s / max(n, 1)
            std = (ss / max(n, 1) - mean ** 2).clamp(min=0).sqrt().clamp(min=1e-6)
            scaler[nt] = (mean.float(), std.float())
        print(f"{GREEN}[train] z-score scaler computed from training data{END}")
        return scaler

    def get_loader(self) -> Tuple[DataLoader, DataLoader, dict[str, Tuple[torch.Tensor, torch.Tensor]]]:
        train_dataset = self.dataset.index_select(self.train_range)
        valid_dataset = self.dataset.index_select(self.valid_range)
        train_loader = DataLoader(train_dataset, batch_size=self.batch_size, shuffle=True , pin_memory=True, num_workers=4)
        valid_loader = DataLoader(valid_dataset, batch_size=self.batch_size, shuffle=False, pin_memory=True, num_workers=4)
        scaler = self.compute_scaler(train_loader)
        return train_loader, valid_loader, scaler


class Evaluation:
    """評価期間 (eval_split) に対するモデル評価.

    - 分類指標: CrossEntropy loss / accuracy / precision・recall・f1-score (クラス別, macro, weighted)
    - 売買シミュレーション: 各日 P(pos)-P(neg) の上位 top_k 銘柄を等ウェイトでロング,
      下位 top_k 銘柄をショートした日次リターン, およびリスクフリーレートを用いた Sharpe ratio

    前提: データセット index = tID - c._BASE, 返り値 NxRi は日次の小数リターン.
          tool.risk_free.r_f (年率 %) は _get_risk_free_rate() で日次の小数リターンに換算して使う.
    """

    CLASS_NAMES = tuple(c.CLASS_LABELS)  # labels: [neg, pos] (2値) / [neg, neu, pos] (3値)
    CLASS_POS = CLASS_NAMES.index('pos')
    CLASS_NEG = CLASS_NAMES.index('neg')

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
        self.confusion: Optional[torch.Tensor] = None  # [真値, 予測] の件数行列


    def _get_risk_free_rate(self) -> pd.DataFrame:
        conn = db.connect(database=":memory:", read_only=False)
        conn.execute(f"attach '{c.ACT_DB_PATH}' as act;")
        conn.execute(f"attach '{c.DEV_DB_PATH}' as dev;")
        df = conn.execute("SELECT * from dev.tool.risk_free;").df()[['tID', 'r_f']]
        conn.close()
        # tool.risk_free.r_f は年率 % (例: 0.5 = 年0.5%) -> 日次の小数リターンへ変換 (252営業日で複利換算)
        df['r_f'] = (1 + df['r_f'] / 100) ** (1 / 252) - 1
        return df


    def simulate(self) -> pd.DataFrame:
        """評価期間を1日ずつ推論し, 日次の損失・正解数・ポートフォリオリターンを返す."""
        rf = self._get_risk_free_rate().set_index('tID')['r_f']
        rows = []
        n_cls = len(self.CLASS_NAMES)
        confusion = torch.zeros(n_cls * n_cls, dtype=torch.long)

        self.model.eval()
        with torch.no_grad():
            for idx in range(self.eval_split[0], self.eval_split[1] + 1):
                data = self.dataset.get(idx)
                if data["stock"].labels.size(0) == 0:  # 予測対象 0 件の日は loss が NaN になるためスキップ
                    continue
                labels  =torch.argmax(data["stock"].labels.long(), dim=1).to(c.DEVICE)
                returns = data["stock"].returns.reshape(-1).to(c.DEVICE)
                output  = self.model(data)

                loss = self.criterion(output, labels)
                pred = output.argmax(dim=1)
                correct = (pred == labels).sum().item()
                confusion += torch.bincount((labels * n_cls + pred).cpu(), minlength=n_cls * n_cls)

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

        self.confusion = confusion.reshape(n_cls, n_cls)
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
        self.result = { # baseline-sharpe-ratio : 0.5175093301598428
            'loss'          : float(df['loss'].mean()),
            'accuracy'      : float(df['correct'].sum() / n_total) if n_total > 0 else 0.0,
            'long_mean'     : float(df['r_long'].mean()),
            'long_sharpe'   : self._sharpe(df['r_long'] - df['r_f']),
            # short 単独: 売却代金を r_f で運用する自己資金ゼロのポジション -> 超過リターン = r_f - r_short
            'short_mean'    : float((-df['r_short']).mean()),
            'short_sharpe'  : self._sharpe(df['r_f'] - df['r_short']),
            'ls_mean'       : float(df['r_long_short'].mean()),
            'ls_sharpe'     : self._sharpe(df['r_long_short']),
            'long_cum'      : float((1 + df['r_long']).prod() - 1), # type: ignore
            'short_cum'     : float((1 - df['r_short']).prod() - 1), # type: ignore
            'ls_cum'        : float((1 + df['r_long_short']).prod() - 1), # type: ignore
        }
        report = self.classification_report()
        for avg in ('macro', 'weighted'):
            for m in ('precision', 'recall', 'f1'):
                self.result[f'{avg}_{m}'] = float(report.loc[f'{avg} avg', m])

        print(f"{CYAN}[Evaluation] tID idx {self.eval_split[0]}-{self.eval_split[1]} ({len(df)} days), top_k={self.top_k}{END}")
        for k, v in self.result.items():
            print(f"  {k:15s}: {v:.4f}")
        self.print_classification_report(report)
        self.plot_confusion_matrix()
        return self.result


    def classification_report(self) -> pd.DataFrame:
        """混同行列からクラス別 / macro / weighted の precision・recall・f1-score を算出する.

        分母が 0 のクラス (予測 0 件 or 真値 0 件) の指標は 0 とする (sklearn の zero_division=0 と同じ).
        """
        assert self.confusion is not None, "Call simulate() first."
        cm = self.confusion.double()
        tp = cm.diag()
        pred_cnt = cm.sum(dim=0)  # 列和 = 予測件数
        true_cnt = cm.sum(dim=1)  # 行和 = 真値件数 (support)

        precision = torch.where(pred_cnt > 0, tp / pred_cnt.clamp(min=1), torch.zeros_like(tp))
        recall    = torch.where(true_cnt > 0, tp / true_cnt.clamp(min=1), torch.zeros_like(tp))
        denom     = precision + recall
        f1        = torch.where(denom > 0, 2 * precision * recall / denom.clamp(min=1e-12), torch.zeros_like(tp))

        report = pd.DataFrame({
            'precision': precision.numpy(), 'recall': recall.numpy(),
            'f1': f1.numpy(), 'support': true_cnt.long().numpy(),
        }, index=list(self.CLASS_NAMES))

        total = int(true_cnt.sum().item())
        weights = (true_cnt / total).numpy() if total > 0 else None
        metrics = ['precision', 'recall', 'f1']
        report.loc['macro avg', metrics] = report.loc[list(self.CLASS_NAMES), metrics].mean().values
        report.loc['weighted avg', metrics] = (
            (report.loc[list(self.CLASS_NAMES), metrics].values * weights[:, None]).sum(axis=0)
            if weights is not None else 0.0
        )
        report.loc[['macro avg', 'weighted avg'], 'support'] = total
        report['support'] = report['support'].astype(int)
        return report


    def print_classification_report(self, report: Optional[pd.DataFrame] = None) -> None:
        report = self.classification_report() if report is None else report
        print(f"{CYAN}[Classification Report]{END}")
        print(f"  {'':>12s}{'precision':>11s}{'recall':>11s}{'f1-score':>11s}{'support':>11s}")
        for name, row in report.iterrows():
            if name == 'macro avg':
                print()
            print(f"  {name:>12s}{row['precision']:>11.4f}{row['recall']:>11.4f}{row['f1']:>11.4f}{int(row['support']):>11d}")


    def plot_confusion_matrix(self, path: Optional[str] = None, show: bool = True) -> str:
        """混同行列 (行=真値, 列=予測) を表示し, PNG で保存する. 保存先パスを返す."""
        assert self.confusion is not None, "Call simulate() first."
        cm = self.confusion.numpy()
        names = self.CLASS_NAMES

        # コンソール出力
        print(f"{CYAN}[Confusion Matrix] rows=true, cols=pred{END}")
        print("  " + " " * 6 + "".join(f"{n:>10s}" for n in names))
        for name, row in zip(names, cm):
            print(f"  {name:>6s}" + "".join(f"{v:>10d}" for v in row))

        # 図 (セル内に件数と行方向の割合 = recall を表示)
        row_sum = cm.sum(axis=1, keepdims=True)
        ratio = cm / row_sum.clip(min=1)
        fig, ax = plt.subplots(figsize=(5, 4.5))
        im = ax.imshow(ratio, cmap='Blues', vmin=0.0, vmax=1.0)
        fig.colorbar(im, ax=ax, label='ratio (row-normalized)')
        ax.set_xticks(range(len(names)), labels=names)
        ax.set_yticks(range(len(names)), labels=names)
        ax.set_xlabel('Predicted')
        ax.set_ylabel('True')
        ax.set_title(f'Confusion Matrix (idx {self.eval_split[0]}-{self.eval_split[1]})')
        for i in range(len(names)):
            for j in range(len(names)):
                ax.text(j, i, f"{cm[i, j]}\n({ratio[i, j]:.1%})", ha='center', va='center',
                        color='white' if ratio[i, j] > 0.5 else 'black')
        fig.tight_layout()

        # 保存してから表示 (show はウィンドウを閉じるまでブロックするため, 先に保存しておく)
        path = path or os.path.join(self.model_dir, "confusion_matrix.png")
        fig.savefig(path, dpi=150)
        print(f"Saved confusion matrix: {path}")
        if show:
            plt.show()
        plt.close(fig)
        return path


    def save(self, path: Optional[str] = None) -> str:
        """日次結果を CSV に保存する."""
        assert self.daily is not None, "Call evaluate() first."
        path = path or os.path.join(self.model_dir, "eval_daily.csv")
        self.daily.to_csv(path, index=False)
        if self.confusion is not None:
            self.classification_report().to_csv(
                os.path.join(os.path.dirname(path) or ".", "classification_report.csv"))
        return path
