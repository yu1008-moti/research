# model/baseline/ 訓練過程のリソース分析（GPUメモリ・推奨CPU/GPUスペック）

実施日: 2026-09-16。`scripts/datap/graph/DS/processed/data_9999_full.pt`（既存キャッシュ、serial_id=9999、
`START_WEEK_ID`〜`END_WEEK_ID` 全期間）を使い、`model/baseline/train.py` と同一の
`get_loaders()` / `BaselineHeteroGNN`（既定ハイパーパラメータ: `hidden_dim=64, num_layers=2,
batch_size=32, num_neighbors_per_hop=10, num_hops=2`）で、実際に学習ループを数十バッチ走らせて
メモリ・速度を実測した。数値の大半は実測値であり、推測ではない（実測でない箇所は明記する）。

## 実測環境

| 項目 | 値 |
|---|---|
| CPU | 12th Gen Intel Core i7-12650H（10コア/16スレッド） |
| RAM | 32GB |
| GPU | NVIDIA GeForce RTX 3050 Laptop 6GB（Driver 591.74） |
| PyTorch | 2.13.0+cu132 |

## グラフ規模（`data_9999_full.pt`, ディスク上2.3GB）

| node_type | ノード数 |
|---|---:|
| stock | 3,307,035 |
| statement | 212,340 |
| option | 9,348,313 |
| future | 62,840 |
| **合計** | **約1,293万** |

エッジ総数は約4,055万本（`option,prev,option` だけで907万本、`stock⇄option` の
`derivative`/`rev_derivative` 往復で計1,768万本、`stock,corr,stock` が613万本、
`stock⇄future` 往復が687万本など）。**option ノードがグラフ全体の72%を占め、支配的**。

## 1. GPUメモリ

### 実測（1バッチ = seed 32ノード、2ホップ、各ホップ最大10近傍）

| 指標 | 実測値 |
|---|---:|
| バッチ内サブグラフ 平均ノード数 | 940.1（最大1,226） |
| バッチ内サブグラフ 平均エッジ数 | 1,177.2（最大1,506） |
| `torch.cuda.max_memory_allocated` | 25.0 MB |
| `torch.cuda.max_memory_reserved` | 30.0 MB |
| `nvidia-smi` 実測（CUDAコンテキスト込み） | **141 MiB** / 6,144 MiB |

現行のベースラインモデル（総パラメータ 216,734個）・既定ハイパーパラメータでは、
学習中のGPUメモリ使用量は実質無視できる水準（200MB未満）だった。理由:

- グラフ全体（1,293万ノード）は CPU 側の `HeteroData` として保持され、GPUには
  `NeighborLoader` がサンプリングした**そのバッチ分のサブグラフのみ**が転送される
  （`train.py` の `batch = batch.to(device)`）。
- seed 32件・2ホップ・各ホップ10近傍という設定では、サブグラフはノード数百〜千程度に収まる。
- モデル自体が小さい（`hidden_dim=64`, `num_layers=2`）。

### CPU-only との速度比較（実測、50バッチ平均、3バッチウォームアップ後）

| device | 1バッチあたり | スループット |
|---|---:|---:|
| CPU | 114.0 ms | 8.8 batch/s |
| CUDA | 110.3 ms | 9.1 batch/s |

**GPUとCPU-onlyでほぼ同速**。ボトルネックはGPU計算ではなく、`NeighborLoader` による
サブグラフサンプリング（CPU側、`get_loaders()` が `num_workers` を指定していないため
シングルスレッド・メインプロセス実行）にある。現行設定ではGPUを使う恩恵は薄い。

### 今後スケールさせる場合の注意点

- `hidden_dim` / `num_layers` / `batch_size` / `num_neighbors_per_hop` / `num_hops` を
  増やすとサブグラフ・活性化のサイズが増える。特に `stock, derivative, future` は
  ハブ構造（`future` 側の `rev_derivative` 次数がその週の対象銘柄数と同程度＝数百〜数千）
  であるため、`num_hops` を増やす、または `future` 方向の近傍数を上げると
  サブグラフが急激に膨張しうる（[heterodata_batch_output_explained.md](heterodata_batch_output_explained.md) の懸念点も参照）。
- `sampler="hgt"`（`HGTLoader`）は現行環境で `torch-sparse` 未導入のため動作未検証。
- 現状の6GB GPU（RTX 3050 Laptop）は今回の設定に対して大幅なオーバースペック。

## 2. CPU / RAM

### 実測

| タイミング | プロセスRSS |
|---|---:|
| 起動直後（torch import後） | 0.50 GB |
| `get_loaders()` 完了直後（グラフをRAMに展開） | **5.71 GB** |
| 学習30バッチ後 | 6.33 GB |

`data_9999_full.pt`（ディスク上2.3GB）を `HeteroData` としてデシリアライズし、
`NeighborLoader` が参照可能な状態でメインプロセスに保持するだけで**約5.2GBのRAM**を消費する
（`num_workers=0` のためこのメモリはメインプロセス1つに集約される。仮に
`num_workers>0` にすると、実装次第でワーカープロセスごとにグラフが複製されうる点に注意）。
このメモリは学習プロセスの生存期間中ずっと保持される。

### 訓練速度のボトルネック

| split | シードノード数（stock, is_target かつ期間内） | batch_size=32時のバッチ数 |
|---|---:|---:|
| train | 1,238,577 | 38,706 |
| val | 273,868 | 8,558 |
| test | 205,956 | 6,436 |

実測 0.11〜0.14秒/バッチ から、**train 部分だけで1エポックあたり約70〜90分**、
val/test を含めると1エポック全体で100分超と見積もられる。これはコミットログ
`d3dcdb3`「動作確認完了，ただしめちゃくちゃ遅い．対策が必要．」に対応する実態と考えられる。
ボトルネックはGPU計算ではなく、CPU側・シングルスレッドの `NeighborLoader` サンプリングにある。

## 推奨スペック

### GPU
- 現行のモデル規模・ハイパーパラメータでは **4〜6GB VRAM で十分すぎる**（実測 <200MB）。
  今回計測に使ったRTX 3050 Laptop 6GBは大幅なオーバースペックであり、GPUが無くてもCPU-onlyで
  ほぼ同速に学習できる（実測でほぼ差なし）。
- 将来 `hidden_dim`/`num_layers`/`batch_size` を大きく引き上げる、または `future` 方向の
  近傍サンプル数を増やしてハブノード経由のサブグラフを大きくする場合はGPUの恩恵が出てくる
  可能性があるため、余裕を見るなら8GB程度あれば当面困らない。

### CPU / RAM
- **RAM**: グラフを保持するだけで5〜6GB。OSやIDE、並行して動くDBビルド処理等を考えると
  **16GBが最低ライン、余裕を持つなら現状と同じ32GB程度を推奨**（32GBあれば`num_workers>0`化
  による複数プロセスへのグラフ複製にも耐えやすい）。
- **CPU**: `NeighborLoader` のサンプリングがシングルスレッドで律速するため、コア数より
  シングルコア性能（クロック/IPC）を重視した方がよい。現行のi7-12650Hで1バッチ0.11〜0.14秒。

### 学習を高速化したい場合（参考、コード側の対策）
GPU/RAMを増強するより、以下のコード側対策の方が効果が大きいと考えられる。

- **`num_workers>0`（実装済み・検証済み、追記 2026-09-16）**: `get_loaders()` に
  `num_workers` 引数を追加し、`train.py` は `--num-workers`（既定2）から渡す
  （`scripts/datap/graph/cons.py` の `graph_params.NUM_WORKERS` はライブラリ既定値として
  0のまま据え置き、安全側）。0より大きい場合のみ内部で `persistent_workers=True` /
  `prefetch_factor=4` を付与する。
  実測（既定ハイパーパラメータ、モデルの forward/backward 込みの1バッチあたり時間）:

  | num_workers | ms/batch | 合計RSS（main+workers） |
  |---:|---:|---:|
  | 0 | 91.8 | 4.52 GB |
  | 2 | 36.1（**約2.5倍**） | 10.20 GB |
  | 4 | 35.3（2からの伸びはほぼ無し） | 13.98 GB |

  Windowsの`multiprocessing`は`spawn`方式（`fork`のCOW共有が効かない）だが、
  PyTorchのテンソルIPCが共有メモリ経由で巨大テンソル本体（グラフ全体5〜6GB相当）自体は
  複製しないため、ワーカー1つあたりの純増は約2〜3GB程度に収まる（CSRサンプリング構造の
  再構築＋Pythonインタプリタ分と見られる）。32GB環境なら train/val/test 全ローダーの
  ワーカーが同時に常駐しても実測ベースで20GB台に収まり安全。**2で費用対効果が頭打ちになる
  ため、既定値は2とした。**
  注意点（`graph_params.NUM_WORKERS` のdocstringにも明記）: Windowsのspawnは
  ワーカープロセスでモジュールのトップレベルコードを再実行するため、`num_workers>0` で
  `get_loaders()` を呼ぶ側は必ず `if __name__ == "__main__":` 配下で呼ぶこと。
  repo root の `test_temp.py` はこのガード無しに `get_loaders()` をトップレベルで
  呼んでいる（CLAUDE.md参照）ため、ライブラリ側の既定値は0のまま変更していない。

- **`pin_memory`（検証済み・不採用、追記 2026-09-16）**: 同条件で `pin_memory=True` を
  試したところ 37.5ms/batch と `pin_memory=False`（36.1ms/batch）から有意な改善は
  見られず、むしろ常駐RSSが +約2GB 増えた（num_workers=2時: 10.20GB→12.43GB）。
  理由は「GPUメモリ」節で示した通りGPU側の計算・転送コストが実測 <30MB/バッチと
  もともと無視できる水準で、H2D転送そのものはボトルネックではないため。
  そのため今回は実装を見送った（`hidden_dim`/`batch_size`を大幅に引き上げてGPU側の
  転送量・計算量が支配的になった場合は再検討の余地がある）。

- `num_neighbors_per_hop` / `num_hops` を下げてサンプリングコスト自体を削減する（未検証・提案）。
- ハブ構造になっている `stock, derivative, future` / `future, rev_derivative, stock` の
  近傍数だけ個別に絞る（`get_loaders()` の `num_neighbors` 引数で関係ごとに上書き可能、
  未検証・提案）。
