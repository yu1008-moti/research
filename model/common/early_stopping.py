"""各 model/<alias>/train.py 共通の early stopping。

検証損失（val_loss）を監視し、`patience` エポック連続で `min_delta` 以上の改善が
なければ学習を打ち切る。ベストエポック時点の重みを保持しており、`restore()` で
モデルに書き戻せる（テスト評価・保存をベスト重みで行うため）。
"""

from __future__ import annotations

import copy

import torch


class EarlyStopping:
    def __init__(self, patience: int, min_delta: float = 0.0) -> None:
        # patience <= 0 は無効（従来どおり全エポック回す）。ただしベスト重みの追跡は行う。
        self.patience = patience
        self.min_delta = min_delta
        self.best_loss = float("inf")
        self.best_epoch = 0
        self.best_state: dict | None = None
        self.num_bad_epochs = 0

    @property
    def enabled(self) -> bool:
        return self.patience > 0

    def step(self, val_loss: float, model: torch.nn.Module, epoch: int) -> bool:
        """1エポック終了ごとに呼ぶ。打ち切るべきなら True を返す。"""
        if val_loss < self.best_loss - self.min_delta:
            self.best_loss = val_loss
            self.best_epoch = epoch
            self.best_state = copy.deepcopy({k: v.detach().cpu() for k, v in model.state_dict().items()})
            self.num_bad_epochs = 0
            return False
        self.num_bad_epochs += 1
        return self.enabled and self.num_bad_epochs >= self.patience

    def restore(self, model: torch.nn.Module) -> None:
        if self.best_state is not None:
            model.load_state_dict(self.best_state)
