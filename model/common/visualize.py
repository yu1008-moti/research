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
