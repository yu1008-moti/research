# Managing Experiments with GraphGym

- [Managing Experiments with GraphGym](#managing-experiments-with-graphgym)
  - [Highlights](#highlights)
  - [Why GraphGym?](#why-graphgym)
  - [Basic Usage](#basic-usage)
  - [In-Depth Usage](#in-depth-usage)
  - [Customizing GraphGym](#customizing-graphgym)

---

GraphGym は，[“Design Space for Graph Neural Networks”](https://arxiv.org/abs/2011.08843) 論文で最初に提案された，**Graph Neural Network（GNN）の設計と評価のためのプラットフォーム**である．
現在，GraphGym は PyG（PyTorch Geometric）の一部として公式にサポートされている．

> **Warning**
>
> GraphGym の API は，PyG とのさらに優れた，より深い統合に向けて継続的に取り組んでいる過程にあるため，将来変更される可能性がある．

## Highlights

- **GNN のための高度にモジュール化されたパイプライン：**
  - **データ：** データの読み込みとデータ分割
  - **モデル：** モジュール化された GNN 実装
  - **タスク：** ノードレベル，エッジレベル，グラフレベルのタスク
  - **評価：** 精度，ROC AUC，など
- **再現可能な実験設定：**
  - 各実験は*設定ファイルによって完全に記述される*
- **スケーラブルな実験管理：**
  - *何千もの GNN 実験を並列に*簡単に起動できる
  - ランダムシードや実験全体にわたる解析結果・図を*自動生成*する
- **柔軟なユーザーカスタマイズ：**
  - データローダー，GNN レイヤー，損失関数など，*独自のモジュールを簡単に登録*できる

## Why GraphGym?

**TL;DR：** GraphGym は，GNN 初心者，ドメインエキスパート，GNN 研究者のいずれにとっても有用である．

**シナリオ1：** グラフ表現学習の初心者で，GNN がどのように動作するかを理解したい場合：

これまでに GNN に関する数多くの刺激的な論文を読んできて，自分自身の GNN 実装を書いてみようとしているかもしれない．
素の PyG を使う場合でも，パイプラインの本質的な部分は自分自身でコーディングする必要がある．
GraphGym は，*標準化された GNN の実装と評価*について学び始めるのに最適な場所である．

[](../_images/graphgym_design_space.png)

**Figure 1：** モジュール化された GNN 実装．

**シナリオ2：** 自分の興味あるアプリケーションに GNN を適用したい場合：

GNN には数百通りものモデルが存在しうること，そしてその中から最良のモデルを選ぶことが非常に難しいことをご存じだろう．
さらに悪いことに，[GraphGym の論文](https://arxiv.org/abs/2011.08843) は，タスクが異なれば最良の GNN 設計も大きく異なることを示している．
GraphGym は，*何千もの GNN を並列に試す*ためのシンプルなインターフェースを提供し，自分のタスクに対する最良の設計を理解する助けとなる．
また，GraphGym は，1,000万通りの GNN モデル・タスクの組み合わせを調査した結果に基づく，いわば「お勧め」の GNN 設計空間も提案している．

[](../_images/graphgym_results.png)

**Figure 2：** 望ましい GNN 設計選択のためのガイドライン．

**シナリオ3：** 新しい GNN モデルを考案したり，新しい GNN タスクを提案したりしたい GNN 研究者の場合：

例えば，新しい GNN レイヤー `ExampleConv` を提案したとしよう．
GraphGym は，`ExampleConv` が，例えば [`GCNConv`](../generated/torch_geometric.nn.conv.GCNConv.html#torch_geometric.nn.conv.GCNConv) よりも優れていることを説得力を持って示す助けとなる：
1,000万通りの可能なモデル・タスクの組み合わせからランダムにサンプリングした場合，他の条件（計算コストを含む）をすべて固定したとき，`ExampleConv` はどのくらいの頻度で [`GCNConv`](../generated/torch_geometric.nn.conv.GCNConv.html#torch_geometric.nn.conv.GCNConv) を上回るだろうか？
さらに，GraphGym はハイパーパラメータ探索を簡単に行う助けとなり，どの設計選択がより優れているかを*可視化*することもできる．
要するに，GraphGym は GNN の研究を大いに促進できる．

[](../_images/graphgym_evaluation.png)

**Figure 3：** 例えば `BatchNorm` のような，ある GNN 設計次元に関する評価．

## Basic Usage

> **Note**
>
> GraphGym を使用するには，PyG に追加の依存パッケージが必要である．
> `pip install torch-geometric[graphgym]` を実行することでインストールできる．

GraphGym を使用するには，GitHub から PyG をクローンし，`graphgym/` ディレクトリへ移動する必要がある．

```bash
git clone https://github.com/pyg-team/pytorch_geometric.git
cd pytorch_geometric/graphgym
```

- **単一の実験を実行する：**
  `run_single.sh` を介して GraphGym で実験を実行する．
  設定は `configs/pyg/example_node.yaml` で指定される．
  デフォルトの実験は，[`Planetoid`](../generated/torch_geometric.datasets.Planetoid.html#torch_geometric.datasets.Planetoid) データセット（ランダムな 80/20 の train/validation 分割を使用）に対するノード分類についてのものである．

```bash
bash run_single.sh # run a single experiment
```

- **バッチの実験を実行する：**
  `run_batch.sh` を介して GraphGym でバッチの実験を実行する．
  設定は `configs/pyg/example_node.yaml`（基本アーキテクチャを制御する）と `grids/example.txt`（グリッドサーチの方法を制御する）で指定される．
  この実験では，推奨される GNN 設計空間の中から 96 個のモデルを，2 つのグラフ分類データセットに対して検証する．
  各実験は 3 回繰り返され，8 個のジョブが同時に実行されるように設定されている．
  インフラストラクチャによっては，すべての実験を終えるのに長時間かかる場合がある．
  `Ctrl-C` で実験を中断することもできる（GraphGym はすべてのプロセスを適切に終了する）．

```bash
bash run_batch.sh # run a batch of experiments
```

- **CPU バックエンドで GraphGym を実行する：**
  GraphGym は CPU バックエンドにも対応している．`*.yaml` ファイルに `accelerator: cpu` という行を追加するだけでよい．

## In-Depth Usage

GraphGym を使用するには，GitHub から PyG をクローンし，`graphgym/` ディレクトリへ移動する必要がある．

```bash
git clone https://github.com/pyg-team/pytorch_geometric.git
cd pytorch_geometric/graphgym
```

- **単一の実験を実行する：**
  完全な例は `run_single.sh` に記載されている．

  - **設定ファイルを指定する：**
    GraphGym では，実験は `*.yaml` ファイルによって完全に指定される．
    `*.yaml` ファイルで指定されていない設定は，[`torch_geometric.graphgym.set_cfg()`](../modules/graphgym.html#torch_geometric.graphgym.set_cfg) にあるデフォルト値によって埋められる．
    例えば，`configs/pyg/example_node.yaml` には，データセット，学習手順，モデルなどについての設定が含まれている．
    各設定項目の具体的な説明は，[`set_cfg()`](../modules/graphgym.html#torch_geometric.graphgym.set_cfg) に記載されている．

  - **実験を起動する：**
    例えば，`run_single.sh` では次のようになる．

```bash
python main.py --cfg configs/pyg/example_node.yaml --repeat 3
```

  `--repeat` を介して，異なるランダムシードで繰り返す回数を指定できる．

  - **結果を理解する：**
    実験結果は自動的に `results/${CONFIG_NAME}/` に保存される．
    上記の例では，これは `results/pyg/example_node/` に相当する．
    異なるランダムシードの結果は，それぞれ異なるサブディレクトリ（例：`results/pyg/example_node/2`）に保存される．
    すべてのランダムシードにわたる集計結果は，各指標の平均値と標準偏差 `_std` を含めて，`results/example/agg` へ*自動的に*生成される．
    Train/validation/test の結果は，さらに `results/example/agg/val` のようなサブディレクトリに保存される．
    ここで，`stats.json` には各エポック後のランダムシードにわたる集計結果が保存され，`best.json` には*検証精度が最も高いエポック*の結果が保存される．

- **バッチの実験を実行する：**
  完全な例は `run_batch.sh` に記載されている．

  - **ベースファイルを指定する：**
    GraphGym はバッチの実験の実行をサポートしている．
    まず，`--config` を介してベースとなるアーキテクチャを選択する必要がある．
    バッチの実験は，このベースアーキテクチャの特定の設定を変化させることによって作成される．

  - **（オプションで）計算予算のためのベースファイルを指定する：**
    さらに，GraphGym では，`--config_budget` を介して，グリッドサーチの*計算予算を制御する*ためのベースアーキテクチャを選択できる．
    計算予算は現在，学習可能なパラメータ数によって測定され，基盤となる GNN の隠れ層の次元数を自動調整することによって制御される．
    `--config_budget` が指定されない場合，GraphGym は計算予算を制御しない．

  - **グリッドファイルを指定する：**
    グリッドファイルは，バッチの実験を生成するために，ベースファイルをどのように変化させるかを記述する．
    例えば，ベースファイルは，[`Planetoid`](../generated/torch_geometric.datasets.Planetoid.html#torch_geometric.datasets.Planetoid) データセットに対する 3 層 GCN によるノード分類の実験を指定するかもしれない．
    そして，グリッドファイルは，レイヤー数，モデルアーキテクチャ，データセット，タスクのレベルなど，さまざまな次元に沿って実験をどのように変化させるかを指定する．

  - **バッチの実験のための設定ファイルを生成する：**
    上記で指定した情報に基づいて生成する．
    例えば，`run_batch.sh` では次のようになる．

```bash
python configs_gen.py --config configs/${DIR}/${CONFIG}.yaml \
  --config_budget configs/${DIR}/${CONFIG}.yaml \
  --grid grids/${DIR}/${GRID}.txt \
  --out_dir configs
```

  - **バッチの実験を起動する：**
    例えば，`run_batch.sh` では次のようになる．

```bash
bash parallel.sh configs/${CONFIG}_grid_${GRID} $REPEAT $MAX_JOBS $SLEEP
```

  各実験は `$REPEAT` 回繰り返される．
  すべてのジョブを順次起動するためのキューシステムを実装しており，`$MAX_JOBS` 個のジョブが同時に実行される．
  実運用では，このシステムは数千のジョブを扱う場合でも優れた性能を発揮する．

  - **結果を理解する：**
    実験結果は自動的にディレクトリ `results/${CONFIG_NAME}_grid_${GRID_NAME}/` に保存される．
    上記の例では，これは `results/pyg/example_grid_example/` に相当する．
    各実験を実行した後，GraphGym はさらに，異なるモデル間で自動的に平均を取り，`results/pyg/example_grid_example/agg` に保存する．
    ここで，`val.csv` は各モデル設定について*最終*エポックにおける検証精度を表し，
    `val_best.csv` は平均検証精度が最も高いエポックにおける結果を表し，
    `val_best_epoch.csv` は，異なるランダムシードにわたって平均した検証精度が最も高いエポックにおける結果を表す．
    テストセットの分割が用意されている場合，`test.csv` は各モデル設定について*最終*エポックにおけるテスト精度を表し，
    `test_best.csv` は平均検証精度が最も高いエポックにおけるテストセットの結果を表し，
    `test_best_epoch.csv` は，異なるランダムシードにわたって平均した検証精度が最も高いエポックにおけるテストセットの結果を表す．

## Customizing GraphGym

GraphGym の特長の一つは，カスタマイズしたモジュールを簡単に登録できることである．
プロジェクトごとに，異なるカスタマイズモジュールを持つ独自の GraphGym のコピーを持つことができる．
例えば，[“Design Space for Graph Neural Networks”](https://arxiv.org/abs/2011.08843) と [“Identity-aware Graph Neural Networks”](https://arxiv.org/abs/2101.10320) の各論文は，カスタマイズされた GraphGym を用いた2つの成功例であり，それらの詳細は[こちら](https://github.com/snap-stanford/GraphGym#use-case-design-space-for-graph-neural-networks-neurips-2020-spotlight)で確認できる．
最終的には，GraphGym を用いた個々のプロジェクトはすべて，それぞれに固有のものとなる．

GraphGym をカスタマイズする方法は2通りある：

- PyG パッケージの外側にある `graphgym/custom_graphgym` ディレクトリを使う：
  PyG 本体に手を加えることなく，ここにカスタマイズしたモジュールを登録できる．この方法は，自分自身のカスタマイズしたプロジェクトに最適である．

- PyG パッケージの内側にある `torch_geometric/graphgym/contrib` ディレクトリを使う：
  優れたカスタマイズモジュールを考案した場合，そのファイルを `torch_geometric/graphgym/contrib` に直接コピーし，PyG に対して**プルリクエストを作成する**ことができる．
  こうすることで，そのアイデアは PyG のインストールに同梱されるようになり，はるかに高い可視性と影響力を持つことになる．

具体的には，以下のカスタマイズされたモジュールがサポートされている．

- Activations：`custom_graphgym/act/`
- Customized configurations：`custom_graphgym/config/`
- Feature augmentations：`custom_graphgym/feature_augment/`
- Feature encoders：`custom_graphgym/feature_encoder/`
- GNN heads：`custom_graphgym/head/`
- GNN layers：`custom_graphgym/layer/`
- Data loaders：`custom_graphgym/loader/`
- Loss functions：`custom_graphgym/loss/`
- GNN network architectures：`custom_graphgym/network/`
- Optimizers：`custom_graphgym/optimizer/`
- GNN global pooling layers (for graph classification only)：`custom_graphgym/pooling/`
- GNN stages：`custom_graphgym/stage/`
- GNN training pipelines：`custom_graphgym/train/`
- Data transformations：`custom_graphgym/transform/`

それぞれのディレクトリには，`torch_geometric.graphgym.register()` を介してカスタマイズしたモジュールを登録する方法を示す例が少なくとも一つ用意されている．
新しいカスタマイズモジュールを追加すると，新しい設定項目が必要になる場合がある点に注意してほしい．
そのような場合，新しい設定項目は `custom_graphgym/config/` を介して登録できる．
