"""ベースライン GNN（model/baseline/model.py の BaselineHeteroGNN）の学習・評価スクリプト。

実行例:
    uv run python -m model.baseline.train --serial-id 9999 --epochs 20

前提: scripts/datap/graph/data_pipeline.get_loaders() が使う HeteroData
（scripts/datap/graph/DS/processed/data_{serial_id}_full.pt）が既に構築済みであること。

学習曲線のオンラインモニタリング:
    デフォルトで logs/tensorboard/<run-name>/ に TensorBoard ログを書き出す。
    学習と並行して別ターミナルで以下を実行するとブラウザでリアルタイムに確認できる。

        uv run tensorboard --logdir logs/tensorboard

    --run-name で実行ごとのログディレクトリ名を指定できる（省略時は serial-id とタイムスタンプ
    から自動生成）。--no-tensorboard を渡すとログ出力自体を無効化できる。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import torch
import torch.nn.functional as F
from torch.utils.tensorboard import SummaryWriter
from torch_geometric.data import HeteroData

from model.common.visualize import plot_training_curves, write_model_structure_md
from scripts.datap.graph.data_pipeline import (
    CATEGORICAL_COLUMNS,
    get_loaders,
    get_vocab_sizes,
)

if TYPE_CHECKING:
    # 実行時は main() 内で遅延 import する（理由はそちらのコメント参照）。
    # 型注釈のためだけに TYPE_CHECKING 下でここに置く（from __future__ import
    # annotations があるため実行時には評価されない）。
    from model.baseline.model import BaselineHeteroGNN

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


def run_epoch(model: BaselineHeteroGNN, loader, device, optimizer=None, writer=None, global_step=0):
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

            batch_correct = (logits.argmax(dim=-1) == labels).sum().item()
            total_loss += loss.item() * seed_n
            total_correct += batch_correct
            total_count += seed_n

            # バッチ単位のログはエポック単位より粒度が細かく、学習中にリアルタイムで
            # 誤差の遷移（1エポック内での挙動）を追えるようにするためのもの。
            if is_train and writer is not None:
                writer.add_scalar("batch/train_loss", loss.item(), global_step)
                writer.add_scalar("batch/train_acc", batch_correct / seed_n, global_step)
                global_step += 1

    return total_loss / total_count, total_correct / total_count, global_step


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial-id", type=int, default=9999)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument(
        "--sampler",
        type=str,
        choices=["neighbor", "hgt"],
        default="neighbor",
        help=(
            "近傍サンプリング方式。'neighbor'（既定, NeighborLoader）はエッジタイプ単位で"
            "一律の近傍数を使う。'hgt'（HGTLoader, HGT論文のHGSampling）はノードタイプ"
            "ごとに独立した予算・次数正規化サンプリングを行うため、option のようにノード数"
            "が突出して多いタイプが計算コストを支配するのを緩和できる可能性がある。"
        ),
    )
    parser.add_argument(
        "--num-neighbors-per-hop",
        type=int,
        default=10,
        help=(
            "1ホップあたりのサンプル数（'neighbor' では全エッジ種別、'hgt' では全ノード"
            "種別に一律適用）。ホップ数と合わせてサブグラフサイズ＝1バッチあたりの"
            "計算コストを左右する最重要パラメータ。小さくすると学習時間短縮が期待できる。"
        ),
    )
    parser.add_argument(
        "--num-hops",
        type=int,
        default=2,
        help="サンプリングのホップ数。1減らすとサブグラフサイズが大きく縮小し学習が速くなる。",
    )
    parser.add_argument("--log-dir", type=str, default="logs/tensorboard", help="TensorBoard ログの出力先ルート")
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="ログディレクトリ名（省略時は serial-id とタイムスタンプから自動生成）",
    )
    parser.add_argument("--no-tensorboard", action="store_true", help="TensorBoard へのログ出力を無効化する")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_loader, val_loader, test_loader = get_loaders(
        serial_id=args.serial_id,
        batch_size=args.batch_size,
        sampler=args.sampler,
        num_neighbors_per_hop=args.num_neighbors_per_hop,
        num_hops=args.num_hops,
    )
    data = train_loader.data  # 3つの loader は同一の HeteroData を共有している（マスクのみ異なる）

    assert isinstance(data, HeteroData)

    # torch_geometric.nn（GraphConv/HeteroConv）を使う BaselineHeteroGNN の import を
    # ここまで遅延させている。get_loaders() 呼び出しより前に import すると、上の
    # データパイプライン処理（pandas/duckdb/statsmodels を多用）と同一プロセス内で
    # 実行が重なるタイミングでネイティブクラッシュ（ACCESS_VIOLATION）することがある
    # ため（graphDataSet が一度キャッシュを作ってしまえば再現しなくなる不安定な事象）。
    # 事前に build_graph_cache_main.py でキャッシュを作っておくのが根本的な回避策。
    from model.baseline.model import BaselineHeteroGNN

    model = BaselineHeteroGNN(
        node_feat_dims=build_node_feat_dims(data, args.serial_id),
        edge_types=data.edge_types,
        hidden_dim=args.hidden_dim,
        num_layers=args.num_layers,
        dropout=args.dropout,
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    structure_path = write_model_structure_md(model, out_dir=Path(__file__).parent)
    print(f"[model structure] wrote {structure_path}")

    # tensorboard の有無によらず、学習済みモデルのファイル名にも使うため常に決めておく。
    run_name = args.run_name or f"serial{args.serial_id}_{datetime.now():%Y%m%d_%H%M%S}"

    writer = None
    if not args.no_tensorboard:
        run_dir = Path(args.log_dir) / run_name
        writer = SummaryWriter(log_dir=str(run_dir))
        writer.add_text(
            "hparams",
            f"hidden_dim={args.hidden_dim}, num_layers={args.num_layers}, lr={args.lr}, "
            f"dropout={args.dropout}, batch_size={args.batch_size}, epochs={args.epochs}",
        )
        print(f"[tensorboard] logging to {run_dir}")
        print(f"[tensorboard] monitor with: uv run tensorboard --logdir {args.log_dir}")

    global_step = 0
    best_val_acc = 0.0
    history = {"train_loss": [], "val_loss": [], "train_acc": [], "val_acc": []}
    try:
        for epoch in range(1, args.epochs + 1):
            train_loss, train_acc, global_step = run_epoch(
                model, train_loader, device, optimizer, writer=writer, global_step=global_step
            )
            val_loss, val_acc, _ = run_epoch(model, val_loader, device)
            best_val_acc = max(best_val_acc, val_acc)
            history["train_loss"].append(train_loss)
            history["val_loss"].append(val_loss)
            history["train_acc"].append(train_acc)
            history["val_acc"].append(val_acc)
            print(
                f"[epoch {epoch:03d}] train_loss={train_loss:.4f} train_acc={train_acc:.4f} "
                f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}"
            )

            if writer is not None:
                writer.add_scalars("epoch/loss", {"train": train_loss, "val": val_loss}, epoch)
                writer.add_scalars("epoch/acc", {"train": train_acc, "val": val_acc}, epoch)
                writer.flush()

        test_loss, test_acc, _ = run_epoch(model, test_loader, device)
        print(f"[test] loss={test_loss:.4f} acc={test_acc:.4f} (best_val_acc={best_val_acc:.4f})")
        if writer is not None:
            writer.add_text("test_result", f"loss={test_loss:.4f}, acc={test_acc:.4f}, best_val_acc={best_val_acc:.4f}")

        model_dir = Path(__file__).parent / "models"
        model_dir.mkdir(exist_ok=True)
        model_path = model_dir / f"{run_name}.pt"
        torch.save(model.state_dict(), model_path)
        print(f"[model] saved to {model_path}")

        # eval.py がチェックポイント単体からモデルを再構築できるよう、state_dict の
        # 復元に必要なハイパーパラメータ（アーキテクチャに関わるもの）をサイドカー
        # JSON として残す（.pt には state_dict しか入っておらず、これらの値は
        # どこにも永続化されないため）。
        config_path = model_dir / f"{run_name}.json"
        config_path.write_text(
            json.dumps(
                {
                    "serial_id": args.serial_id,
                    "hidden_dim": args.hidden_dim,
                    "num_layers": args.num_layers,
                    "dropout": args.dropout,
                    "batch_size": args.batch_size,
                    "sampler": args.sampler,
                    "num_neighbors_per_hop": args.num_neighbors_per_hop,
                    "num_hops": args.num_hops,
                    "epochs": args.epochs,
                    "lr": args.lr,
                    "best_val_acc": best_val_acc,
                    "test_loss": test_loss,
                    "test_acc": test_acc,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"[model] config saved to {config_path}")

        curves_path = model_dir / f"{run_name}.png"
        plot_training_curves(history, curves_path, title=run_name)
        print(f"[curves] saved to {curves_path}")
    finally:
        if writer is not None:
            writer.close()


if __name__ == "__main__":
    main()
