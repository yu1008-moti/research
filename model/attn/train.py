"""Attention 版 GNN（model/attn/model.py の AttnHeteroGNN）の学習・評価スクリプト。

`model/baseline/train.py` とほぼ同一の構成（共通引数・ログ出力・チェックポイント保存規約
は model/README.md の運用ルールに準拠）。差分は AttnHeteroGNN 固有のハイパーパラメータ
（--attn-heads / --attn-head-channels）のみ。

実行例:
    uv run python -m model.attn.train --serial-id 9999 --epochs 20

前提: scripts/datap/graph/data_pipeline.get_loaders() が使う HeteroData
（scripts/datap/graph/DS/processed/data_{serial_id}_full.pt）が既に構築済みであること。

学習曲線のオンラインモニタリング:
    デフォルトで logs/tensorboard/<run-name>/ に TensorBoard ログを書き出す。
    学習と並行して別ターミナルで以下を実行するとブラウザでリアルタイムに確認できる。

        uv run tensorboard --logdir logs/tensorboard

    --run-name で実行ごとのログディレクトリ名を指定できる（省略時は serial-id とタイムスタンプ
    から自動生成）。--no-tensorboard を渡すとログ出力自体を無効化できる。

実行ログのファイル出力:
    標準出力に表示される内容（パラメータ一覧・エポックごとの loss/acc・保存先パスなど）は、
    logs/model_result/<timestamp>_<alias>.log（<alias> は model/<alias>/train.py の <alias>、
    例: model/attn/train.py なら attn）にもそのまま書き出される。
    --no-file-log を渡すとファイル出力のみ無効化できる（標準出力への表示は変わらない）。
"""

from __future__ import annotations

import argparse
import itertools
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import torch
from torch.profiler import profile, record_function, ProfilerActivity
import torch.nn.functional as F
from torch.utils.tensorboard import SummaryWriter
from torch_geometric.data import HeteroData

from model.baseline.train import build_node_feat_dims, stock_labels
from model.common.visualize import plot_training_curves, write_model_structure_md
from scripts.datap.graph.data_pipeline import get_loaders

if TYPE_CHECKING:
    # 実行時は main() 内で遅延 import する（理由はそちらのコメント参照）。
    from model.attn.model import AttnHeteroGNN

NODE_TYPES = ["stock", "statement", "option", "future"]


def run_epoch(
    model: AttnHeteroGNN,
    loader,
    device,
    optimizer=None,
    writer=None,
    global_step=0,
    use_profiler=False,
    profile_batches=20,
):
    is_train = optimizer is not None
    model.train(is_train)

    total_loss, total_correct, total_count = 0.0, 0, 0

    def step(batch):
        nonlocal total_loss, total_correct, total_count, global_step
        batch = batch.to(device)
        labels = stock_labels(batch)

        # NeighborLoader は起点（seed）ノードを各ノードタイプの配列の先頭に置く。
        # 損失・精度は起点ノード（＝このバッチで実際に予測したい stock ノード）のみで計算する。
        seed_n = batch["stock"].batch_size
        logits = model(batch)[:seed_n]
        labels = labels[:seed_n]

        loss = F.cross_entropy(logits, labels)

        if is_train and isinstance(optimizer, torch.optim.Optimizer):
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

    with torch.set_grad_enabled(is_train):
        loader_iter = iter(loader)

        if use_profiler:
            # torch.profiler はプロファイル区間中に発生した全イベントを保持し続けるため、
            # エポック全体を対象にすると（バッチ数×グラフサイズに比例して）ホストメモリ
            # 使用量が際限なく増え続ける。ここでは先頭 profile_batches 件だけを計測して
            # 即座に打ち切る（残りのバッチは処理しない）。
            with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA], record_shapes=True) as prof:
                for batch in itertools.islice(loader_iter, profile_batches):
                    step(batch)
            if device.type == "cuda":
                torch.cuda.synchronize()
            logging.info(prof.key_averages().table(sort_by="cuda_time", row_limit=40))
            prof.export_chrome_trace("./trace.json")
        else:
            for batch in loader_iter:
                step(batch)

    return total_loss / total_count, total_correct / total_count, global_step


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--serial-id", type=int, default=9999)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument(
        "--attn-heads",
        type=int,
        default=4,
        help="stock ノードのグローバル注意（PerformerAttention）のヘッド数。hidden_dim を割り切る必要がある。",
    )
    parser.add_argument(
        "--attn-head-channels",
        type=int,
        default=None,
        help="PerformerAttention の1ヘッドあたりの内部次元。省略時は hidden_dim // attn_heads。",
    )
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
    parser.add_argument(
        "--num-workers",
        type=int,
        default=2,
        help="NeighborLoader/HGTLoader のバックグラウンドワーカープロセス数（既定は2、詳細は model/baseline/train.py 参照）。",
    )
    parser.add_argument("--log-dir", type=str, default="logs/tensorboard", help="TensorBoard ログの出力先ルート")
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="ログディレクトリ名（省略時は serial-id とタイムスタンプから自動生成）",
    )
    parser.add_argument("--no-tensorboard", action="store_true", help="TensorBoard へのログ出力を無効化する")
    parser.add_argument(
        "--profile",
        action="store_true",
        help=(
            "torch.profiler による計測を有効化する（既定は無効）。エポック全体ではなく"
            "各学習エポックの先頭 --profile-batches バッチのみを計測し、結果を標準出力に表示する。"
        ),
    )
    parser.add_argument(
        "--profile-batches",
        type=int,
        default=20,
        help="--profile 有効時に計測対象とする先頭バッチ数",
    )
    parser.add_argument(
        "--no-file-log",
        action="store_true",
        help="logs/model_result/ への実行ログファイル出力を無効化する（標準出力には引き続き表示される）",
    )
    args = parser.parse_args()

    run_started = datetime.now()
    alias = Path(__file__).resolve().parent.name  # model/<alias>/train.py の <alias>

    handlers = [logging.StreamHandler(sys.stdout)]
    log_path = None
    if not args.no_file_log:
        log_dir = Path("logs/model_result")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{run_started:%Y%m%d_%H%M%S}_{alias}.log"
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=handlers, force=True)

    if log_path is not None:
        logging.info(f"[log] writing to {log_path}")
    logging.info(f"python -m model.{alias}.train {' '.join(sys.argv[1:])}")
    logging.info(f"[params] {json.dumps(vars(args), ensure_ascii=False, sort_keys=True)}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_loader, val_loader, test_loader = get_loaders(
        serial_id=args.serial_id,
        batch_size=args.batch_size,
        sampler=args.sampler,
        num_neighbors_per_hop=args.num_neighbors_per_hop,
        num_hops=args.num_hops,
        num_workers=args.num_workers,
    )
    data = train_loader.data  # 3つの loader は同一の HeteroData を共有している（マスクのみ異なる）

    assert isinstance(data, HeteroData)

    # model/baseline/train.py と同じ理由（データパイプライン処理と torch_geometric.nn の
    # import が同一プロセス内で重なるとネイティブクラッシュすることがある）で遅延 import する。
    from model.attn.model import AttnHeteroGNN

    model = AttnHeteroGNN(
        node_feat_dims=build_node_feat_dims(data, args.serial_id),
        edge_types=data.edge_types,
        hidden_dim=args.hidden_dim,
        num_layers=args.num_layers,
        dropout=args.dropout,
        attn_heads=args.attn_heads,
        attn_head_channels=args.attn_head_channels,
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    structure_path = write_model_structure_md(model, out_dir=Path(__file__).parent)
    logging.info(f"[model structure] wrote {structure_path}")

    # run_started はログファイル名にも使ったタイムスタンプと同一なので、
    # logs/model_result/<timestamp>_<alias>.log と logs/tensorboard/<run_name>/ を突き合わせやすい。
    run_name = args.run_name or f"serial{args.serial_id}_{run_started:%Y%m%d_%H%M%S}"

    writer = None
    if not args.no_tensorboard:
        run_dir = Path(args.log_dir) / run_name
        writer = SummaryWriter(log_dir=str(run_dir))
        writer.add_text(
            "hparams",
            f"hidden_dim={args.hidden_dim}, num_layers={args.num_layers}, lr={args.lr}, "
            f"dropout={args.dropout}, batch_size={args.batch_size}, epochs={args.epochs}, "
            f"attn_heads={args.attn_heads}, attn_head_channels={args.attn_head_channels}",
        )
        logging.info(f"[tensorboard] logging to {run_dir}")
        logging.info(f"[tensorboard] monitor with: uv run tensorboard --logdir {args.log_dir}")

    global_step = 0
    best_val_acc = 0.0
    history = {"train_loss": [], "val_loss": [], "train_acc": [], "val_acc": []}
    try:
        for epoch in range(1, args.epochs + 1):
            train_loss, train_acc, global_step = run_epoch(
                model,
                train_loader,
                device,
                optimizer,
                writer=writer,
                global_step=global_step,
                use_profiler=args.profile,
                profile_batches=args.profile_batches,
            )

            if args.profile:
                # --profile は性能診断用の単発計測が目的なので、先頭 profile_batches 件を
                # 計測し終えた時点で即座に打ち切る。
                logging.info(
                    f"[profile] profiled first {args.profile_batches} batches "
                    f"(train_loss={train_loss:.4f}, train_acc={train_acc:.4f}); exiting."
                )
                sys.exit(0)

            val_loss, val_acc, _ = run_epoch(model, val_loader, device)
            best_val_acc = max(best_val_acc, val_acc)
            history["train_loss"].append(train_loss)
            history["val_loss"].append(val_loss)
            history["train_acc"].append(train_acc)
            history["val_acc"].append(val_acc)
            logging.info(
                f"[epoch {epoch:03d}] train_loss={train_loss:.4f} train_acc={train_acc:.4f} "
                f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}"
            )

            if writer is not None:
                writer.add_scalars("epoch/loss", {"train": train_loss, "val": val_loss}, epoch)
                writer.add_scalars("epoch/acc", {"train": train_acc, "val": val_acc}, epoch)
                writer.flush()

        test_loss, test_acc, _ = run_epoch(model, test_loader, device)
        logging.info(f"[test] loss={test_loss:.4f} acc={test_acc:.4f} (best_val_acc={best_val_acc:.4f})")
        if writer is not None:
            writer.add_text("test_result", f"loss={test_loss:.4f}, acc={test_acc:.4f}, best_val_acc={best_val_acc:.4f}")

        model_dir = Path(__file__).parent / "models"
        model_dir.mkdir(exist_ok=True)
        model_path = model_dir / f"{run_name}.pt"
        torch.save(model.state_dict(), model_path)
        logging.info(f"[model] saved to {model_path}")

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
                    "attn_heads": args.attn_heads,
                    "attn_head_channels": args.attn_head_channels,
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
        logging.info(f"[model] config saved to {config_path}")

        curves_path = model_dir / f"{run_name}.png"
        plot_training_curves(history, curves_path, title=run_name)
        logging.info(f"[curves] saved to {curves_path}")
    finally:
        if writer is not None:
            writer.close()


if __name__ == "__main__":
    main()
