"""nn.Module のモジュール階層を Mermaid のフローチャートとして可視化するユーティリティ。

`model/<alias>/` を新しく作るたびに、構築したモデルインスタンスのモジュール構造を
`model/<alias>/model_structure.md` として書き出すために使う（実際の forward
計算グラフではなく、`named_children()` で辿れる静的なモジュール階層を可視化する。
`model.py` を書き換えれば自動的に追従する）。

使い方（`model/<alias>/train.py` 側）:

    from pathlib import Path
    from model.common.visualize import write_model_structure_md

    model = SomeModel(...).to(device)
    write_model_structure_md(model, out_dir=Path(__file__).parent)
"""

from __future__ import annotations

import itertools
from datetime import datetime
from pathlib import Path

import torch.nn as nn


def _sanitize_label(label: str) -> str:
    # Mermaid のノードラベルは `["..."]` で囲むため、引用符と改行だけ潰せば安全。
    return label.replace('"', "'").replace("\n", " ").strip()


def module_to_mermaid(model: nn.Module, max_depth: int | None = None) -> str:
    """`model` のモジュール階層を Mermaid `graph TD` のソース文字列として返す。

    `max_depth` を指定すると、その深さより下の子モジュールは省略する
    （省略時（None）はリーフモジュールまで全て展開する）。
    """
    lines = ["graph TD"]
    counter = itertools.count()

    def visit(name: str, module: nn.Module, parent_id: str | None, depth: int) -> None:
        node_id = f"n{next(counter)}"
        cls_name = type(module).__name__
        label = f"{name}: {cls_name}" if name else cls_name
        extra = module.extra_repr()
        if extra:
            label += f"({extra})"
        lines.append(f'    {node_id}["{_sanitize_label(label)}"]')
        if parent_id is not None:
            lines.append(f"    {parent_id} --> {node_id}")

        if max_depth is None or depth < max_depth:
            for child_name, child_module in module.named_children():
                visit(child_name, child_module, node_id, depth + 1)

    visit("", model, None, 0)
    return "\n".join(lines)


def write_model_structure_md(
    model: nn.Module,
    out_dir: str | Path,
    filename: str = "model_structure.md",
    max_depth: int | None = None,
) -> Path:
    """`module_to_mermaid()` の結果をパラメータ数などと合わせて `out_dir/filename` に書き出す。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename

    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    mermaid = module_to_mermaid(model, max_depth=max_depth)

    content = (
        f"# {type(model).__name__} モデル構造\n\n"
        f"自動生成: {datetime.now():%Y-%m-%d %H:%M:%S}（train.py 実行時に上書きされる）\n\n"
        f"- 総パラメータ数: {total_params:,}\n"
        f"- 学習対象パラメータ数: {trainable_params:,}\n\n"
        "```mermaid\n"
        f"{mermaid}\n"
        "```\n"
    )
    out_path.write_text(content, encoding="utf-8")
    return out_path


def plot_training_curves(
    history: dict[str, list[float]],
    out_path: str | Path,
    title: str | None = None,
) -> Path:
    """train/val の loss・accuracy 曲線を1枚の PNG として書き出す。

    `history` は `{"train_loss": [...], "val_loss": [...], "train_acc": [...], "val_acc": [...]}`
    のようにエポック順の値を持つ dict（`train.py` のエポックループで蓄積したもの）を想定する。
    表示環境が無い CLI 実行（`uv run python -m model.<alias>.train`）でも保存だけできるよう、
    Agg バックエンドを明示的に使う。
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    epochs = range(1, len(history["train_loss"]) + 1)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    axes[0].plot(epochs, history["train_loss"], label="train")
    axes[0].plot(epochs, history["val_loss"], label="val")
    axes[0].set_xlabel("epoch")
    axes[0].set_ylabel("loss")
    axes[0].set_title("loss")
    axes[0].legend()

    axes[1].plot(epochs, history["train_acc"], label="train")
    axes[1].plot(epochs, history["val_acc"], label="val")
    axes[1].set_xlabel("epoch")
    axes[1].set_ylabel("accuracy")
    axes[1].set_title("accuracy")
    axes[1].legend()

    if title:
        fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
