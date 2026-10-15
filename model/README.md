# model/ ディレクトリの運用ルール

モデル・データ構築フローを再構築中のため、旧 `model/baseline/` および旧 `HeteroData`
リファレンス（4ノード種・12エッジ種、`y`/`y_valid` 分離、`get_loaders()` 等）は破棄した。
旧内容は git 履歴（`git log -- model/README.md`）を参照。

新しいグラフデータの仕様は [`claude_output/graph_spec.md`](../claude_output/graph_spec.md) を参照
（`NeighborLoader` 側 `scripts/datap/graph/loader.py` は未実装）。
グラフ仕様が固まったら、ノード/エッジ/ラベルの扱いと既知の落とし穴をこのファイルに書き戻す。

## 現在 `model/` にあるもの

| パス | 内容 |
|---|---|
| `model/common/early_stopping.py` | 早期終了ユーティリティ |
| `model/common/visualize.py` | `write_model_structure_md()`（モデル階層を Mermaid で `model/<alias>/model_structure.md` に出力）、`plot_training_curves()`（学習曲線 PNG） |

## 運用ルール（モデル追加時に守る）

- モデルごとに `model/<alias>/` 以下へ `model.py` / `train.py` 等を置く（`__init__.py` は置かない namespace package）。
  共通の知見はこの README に集約し、各モデルのコードにはモデル固有の設計判断だけを書く。
- 起動は `uv run python -m model.<alias>.train [--options]`。
- 引数は2グループに分ける。
  - 共通引数（全モデルで名前・意味を揃える）: 学習対象データの指定、`--epochs`、TensorBoard 連携を入れるなら
    `--log-dir`（既定 `logs/tensorboard`）・`--run-name`・`--no-tensorboard`。
  - モデル固有引数: `--hidden-dim` / `--num-layers` / `--lr` / `--dropout` / `--batch-size` 等は自由。
- 学習ログは CLAUDE.md の「Log output location」に従い、`logs/model_result/<timestamp>_<alias>.log`（stdout のミラー）と
  `logs/tensorboard/`（TensorBoard）に出す。
- 保存物（`.pt` / サイドカー `<run_name>.json` / `<run_name>.png`）は `model/<alias>/models/` に置く。
  `.pt` は `state_dict` のみなので、再構築に要るハイパーパラメータを JSON で併せて保存し、
  評価専用の `eval.py`（共通引数 `--model-path`・`--split`）がそれを読む。
- 新しい `train.py` ではモデル生成直後に `write_model_structure_md(model, out_dir=Path(__file__).parent)` を呼ぶ。

学習曲線の監視: `uv run tensorboard --logdir logs/tensorboard`
