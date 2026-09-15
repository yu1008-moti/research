"""ベースライン GNN（model/baseline/model.py の BaselineHeteroGNN）の学習・評価スクリプト。

実行例:
    uv run python -m model.baseline.train --serial-id 9999 --epochs 20

前提: scripts/datap/graph/data_pipeline.get_loaders() が使う HeteroData
（scripts/datap/graph/DS/processed/data_{serial_id}_full.pt）が既に構築済みであること。
"""

from __future__ import annotations

import argparse

import torch
import torch.nn.functional as F
from torch_geometric.data import HeteroData

from model.baseline.model import BaselineHeteroGNN
from scripts.datap.graph.data_pipeline import CATEGORICAL_COLUMNS, get_loaders, get_vocab_sizes

NODE_TYPES = ["stock", "statement", "option", "future"]


def build_node_feat_dims(data: HeteroData, serial_id: int) -> dict:
    dims = {}
    for node_type in NODE_TYPES:
        cont_dim = data[node_type].x.shape[1]
        vocab_sizes = get_vocab_sizes(serial_id, node_type)
        dims[node_type] = {
            "cont": cont_dim,
            "cat": [vocab_sizes[c] for c in CATEGORICAL_COLUMNS.get(node_type, [])],
            "date": data[node_type].date_x.shape[1],
        }
    return dims


def stock_labels(batch: HeteroData) -> torch.Tensor:
    """batch['stock'].y（data_pipeline.py が x とは別テンソルとして持たせているラベル）を返す。

    get_loaders() が train/val/test マスクの時点で y_valid=False（系列末尾でラベル未定義）の
    ノードを input_nodes から除外しているため、ここで取り出す seed ノード分のラベルは
    常に有効なものだけになっている。
    """
    return batch["stock"].y.long()


def run_epoch(model: BaselineHeteroGNN, loader, device, optimizer=None):
    is_train = optimizer is not None
    model.train(is_train)

    total_loss, total_correct, total_count = 0.0, 0, 0
    with torch.set_grad_enabled(is_train):
        for batch in loader:
            batch = batch.to(device)
            labels = stock_labels(batch)

            # NeighborLoader は起点（seed）ノードを各ノードタイプの配列の先頭に置く。
            # 損失・精度は起点ノード（＝このバッチで実際に予測したい stock ノード）のみで計算する。
            seed_n = batch["stock"].batch_size
            logits = model(batch)[:seed_n]
            labels = labels[:seed_n]

            loss = F.cross_entropy(logits, labels)

            if is_train:
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

            total_loss += loss.item() * seed_n
            total_correct += (logits.argmax(dim=-1) == labels).sum().item()
            total_count += seed_n

    return total_loss / total_count, total_correct / total_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial-id", type=int, default=9999)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_loader, val_loader, test_loader = get_loaders(serial_id=args.serial_id, batch_size=args.batch_size)
    data = train_loader.data  # 3つの loader は同一の HeteroData を共有している（マスクのみ異なる）

    model = BaselineHeteroGNN(
        node_feat_dims=build_node_feat_dims(data, args.serial_id),
        edge_types=data.edge_types,
        hidden_dim=args.hidden_dim,
        num_layers=args.num_layers,
        dropout=args.dropout,
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    best_val_acc = 0.0
    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc = run_epoch(model, train_loader, device, optimizer)
        val_loss, val_acc = run_epoch(model, val_loader, device)
        best_val_acc = max(best_val_acc, val_acc)
        print(
            f"[epoch {epoch:03d}] train_loss={train_loss:.4f} train_acc={train_acc:.4f} "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}"
        )

    test_loss, test_acc = run_epoch(model, test_loader, device)
    print(f"[test] loss={test_loss:.4f} acc={test_acc:.4f} (best_val_acc={best_val_acc:.4f})")


if __name__ == "__main__":
    main()
