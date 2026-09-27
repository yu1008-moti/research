"""学習済みベースライン GNN（model/baseline/models/*.pt）を評価だけするスクリプト。

train.py が保存するサイドカー設定ファイル（<run_name>.json、state_dict の復元に
必要なアーキテクチャ関連ハイパーパラメータ一式）があれば自動的に読み込んで
モデルを再構築する。サイドカーが無いチェックポイント（本スクリプト実装以前に
保存されたもの）を評価する場合は、学習時に使った値を --serial-id 等で
明示的に指定すること。

実行例:
    # サイドカー JSON がある場合（--serial-id 等は省略可）
    uv run python -m model.baseline.eval --model-path model/baseline/models/serial9999_20260916_120000.pt

    # サイドカー JSON が無い場合（学習時の値を手で指定する）
    uv run python -m model.baseline.eval \
        --model-path model/baseline/models/serial9999_20260915_231011.pt \
        --serial-id 9999 --hidden-dim 64 --num-layers 2 --dropout 0.2

    # train/val/test すべてを評価
    uv run python -m model.baseline.eval --model-path ... --split all
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import TYPE_CHECKING

import torch
import torch.nn.functional as F
from torch_geometric.data import HeteroData

from model.baseline.train import build_node_feat_dims, stock_labels
from scripts.datap.graph.data_pipeline import get_loaders

if TYPE_CHECKING:
    from model.baseline.model import BaselineHeteroGNN


def load_sidecar_config(model_path: Path) -> dict:
    config_path = model_path.with_suffix(".json")
    if not config_path.exists():
        return {}
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def evaluate(model: BaselineHeteroGNN, loader, device) -> dict:
    """1エポック分（train.py の run_epoch の推論専用版）を回し、2値分類の各種指標を返す。

    train.py の run_epoch と同じ `torch.set_grad_enabled(False)` を使う
    （`@torch.no_grad()` デコレータだと、torch_geometric の動的コンパイル済み
    propagate/aggregate 内で "GIL held" のネイティブクラッシュを起こすことを確認した）。
    """
    model.eval()
    total_loss, total_count = 0.0, 0
    tp = fp = tn = fn = 0

    with torch.set_grad_enabled(False):
        for batch in loader:
            batch = batch.to(device)
            labels = stock_labels(batch)

            seed_n = batch["stock"].batch_size
            logits = model(batch)[:seed_n]
            labels = labels[:seed_n]

            loss = F.cross_entropy(logits, labels)
            preds = logits.argmax(dim=-1)

            total_loss += loss.item() * seed_n
            total_count += seed_n
            tp += int(((preds == 1) & (labels == 1)).sum())
            fp += int(((preds == 1) & (labels == 0)).sum())
            tn += int(((preds == 0) & (labels == 0)).sum())
            fn += int(((preds == 0) & (labels == 1)).sum())

    precision = tp / (tp + fp) if (tp + fp) > 0 else math.nan
    recall = tp / (tp + fn) if (tp + fn) > 0 else math.nan
    f1 = (
        2 * precision * recall / (precision + recall)
        if not (math.isnan(precision) or math.isnan(recall)) and (precision + recall) > 0
        else math.nan
    )
    return {
        "n": total_count,
        "loss": total_loss / total_count,
        "accuracy": (tp + tn) / total_count,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
    }


def print_metrics(split_name: str, metrics: dict) -> None:
    cm = metrics["confusion_matrix"]
    print(
        f"[{split_name}] n={metrics['n']} loss={metrics['loss']:.4f} acc={metrics['accuracy']:.4f} "
        f"precision={metrics['precision']:.4f} recall={metrics['recall']:.4f} f1={metrics['f1']:.4f}"
    )
    print(f"[{split_name}] confusion_matrix: tp={cm['tp']} fp={cm['fp']} tn={cm['tn']} fn={cm['fn']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model-path", type=str, required=True, help="評価する .pt チェックポイントのパス")
    parser.add_argument(
        "--split",
        type=str,
        choices=["train", "val", "test", "all"],
        default="test",
        help="評価する分割（既定: test）。'all' で train/val/test 全てを評価する。",
    )
    # 以下はすべてサイドカー JSON（<model-path>.json）があればそちらを既定値として使う。
    # CLI で明示的に渡した値は常にサイドカーより優先される。
    parser.add_argument("--serial-id", type=int, default=None)
    parser.add_argument("--hidden-dim", type=int, default=None)
    parser.add_argument("--num-layers", type=int, default=None)
    parser.add_argument("--dropout", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--sampler", type=str, choices=["neighbor", "hgt"], default=None)
    parser.add_argument("--num-neighbors-per-hop", type=int, default=None)
    parser.add_argument("--num-hops", type=int, default=None)
    args = parser.parse_args()

    model_path = Path(args.model_path)
    if not model_path.exists():
        raise FileNotFoundError(model_path)
    sidecar = load_sidecar_config(model_path)

    def resolve(key: str, cli_value, default):
        if cli_value is not None:
            return cli_value
        return sidecar.get(key, default)

    serial_id = resolve("serial_id", args.serial_id, None)
    if serial_id is None:
        raise ValueError(
            f"serial-id を特定できません。{model_path.with_suffix('.json')} が見つからないチェックポイントは "
            "--serial-id を明示的に指定してください。"
        )
    hidden_dim = resolve("hidden_dim", args.hidden_dim, 64)
    num_layers = resolve("num_layers", args.num_layers, 2)
    dropout = resolve("dropout", args.dropout, 0.2)
    batch_size = resolve("batch_size", args.batch_size, 32)
    sampler = resolve("sampler", args.sampler, "neighbor")
    num_neighbors_per_hop = resolve("num_neighbors_per_hop", args.num_neighbors_per_hop, 10)
    num_hops = resolve("num_hops", args.num_hops, 2)
    if sidecar:
        print(f"[config] loaded {model_path.with_suffix('.json')}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_loader, val_loader, test_loader = get_loaders(
        serial_id=serial_id,
        batch_size=batch_size,
        sampler=sampler,
        num_neighbors_per_hop=num_neighbors_per_hop,
        num_hops=num_hops,
    )
    data = train_loader.data
    assert isinstance(data, HeteroData)

    # train.py と同じ理由（データパイプライン処理と torch_geometric.nn の import が
    # 同一プロセス内で重なるとネイティブクラッシュすることがある）で遅延 import する。
    from model.baseline.model import BaselineHeteroGNN

    model = BaselineHeteroGNN(
        node_feat_dims=build_node_feat_dims(data, serial_id),
        edge_types=data.edge_types,
        hidden_dim=hidden_dim,
        num_layers=num_layers,
        dropout=dropout,
    ).to(device)
    model.load_state_dict(torch.load(model_path, map_location=device))
    print(f"[model] loaded {model_path}")

    loaders = {"train": train_loader, "val": val_loader, "test": test_loader}
    targets = loaders.items() if args.split == "all" else [(args.split, loaders[args.split])]
    for split_name, loader in targets:
        metrics = evaluate(model, loader, device)
        print_metrics(split_name, metrics)


if __name__ == "__main__":
    main()
