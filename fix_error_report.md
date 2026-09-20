---
title: メモ
author: 264441008
marp: true
style: |
  section {
    background-color: #ffffff;
  }

  h1, h2, h3, h4, h5, h6 {
    color: #333333;
  }
---

<!-- theme: default -->
<!-- paginate: true -->
<!-- _class: lead -->

# データ上のエラーとその詳細

2013/07/16 以前の決算発表履歴があるにもかかわらず，対応する株価データが存在しない．

- **原因**
  - 東証・大証が市場統合したため．[記事](https://media.rakuten-sec.net/articles/-/52911)
  - 大証の株価データは API では取得できない．
- **影響**
  - 決算-株価のエッジが正常に構築できない．
- **対策**
  - 株価ノードが実在する(week, code)にのみエッジを張る．
  - 決算データは貴重なため，そのまま保持する．
  - 決算-株価におけるエッジを該当区間で削除する．

---

# データ上のエラーとその詳細（続き）

2013/07/16 以前の決算発表履歴があるにもかかわらず，対応する株価データが存在しない．

- 1214件についてデータ上のエラーが発生している．
  - そのうち，1092件が 2013/07/16 以前の決算データを持つ．
  - その他，名証上場後に東証へ上場替えした銘柄など122件も同様の原因でエラーが発生している（以下例）
    - ex.) 5356：名証に上場後，2024/03/18 に東証Sに上場した．[記事](https://www.mino-ceramic.co.jp/ir/message/)
    - ex.) 5461：名証に上場後，2022/12/28 に東証Pに上場した．[記事](https://www.chubukohan.co.jp/news/info/2665/)

---

# 学習スクリプトの異常終了

`model/baseline/train.py` 実行時に，ログ出力もエラーメッセージも無いままプロセスが終了する障害が発生した．

- **症状**
  - `uv run python -m model.baseline.train --serial-id 9999 --epochs 20` を実行すると，PyTorch Geometric の定型メッセージ `Processing...` の表示を最後に，何も出力されずプロンプトに戻る．

---

# 学習スクリプトの異常終了

- **切り分け**
  - `echo %ERRORLEVEL%` で終了コードを確認したところ `-1073741819`（`0xC0000005` = `ACCESS_VIOLATION`）であり，Python例外ではなくネイティブクラッシュと判明．
  - 同一構成での再実行でもクラッシュまでの時間が90秒〜7分超とばらつき，決定論的なバグというよりタイミング依存の競合状態（レースコンディション）の可能性が高いと判断．

---

# 学習スクリプトの異常終了（原因の切り分け）

- **有力な要因**
  - GNNモデル定義（`model/baseline/model.py`，`torch_geometric.nn.GraphConv`/`HeteroConv` を使用）の import と，グラフ構築パイプライン（`scripts/datap/graph/data_pipeline.py`：pandas/duckdb/statsmodels を多用する CAPM 相関計算・財務諸表前処理など）の重い処理が，同一プロセス内で重なることが引き金と推定．

---

# 学習スクリプトの異常終了（原因の切り分け）

- **除外できた要因**
  - TensorBoard の import／`torch_geometric.nn` 単体の import／import の順序／`KMP_DUPLICATE_LIB_OK`／スレッド数制限（`OMP_NUM_THREADS` 等）— いずれも単独では解消せず．
  - `model` パッケージの名前空間衝突（`sys.path` 上の他ディレクトリとの重複）も確認したが該当なし．
- 上記より，単一の import が原因という決定論的な説明はできず，ネイティブライブラリ初期化時の何らかの競合と推定するに留まった．

---

# 学習スクリプトの異常終了（対策と検証）

- **対策**
  - `build_graph_cache_main.py` を新規作成し，GNNモデル定義を一切 import せずにグラフキャッシュ（`scripts/datap/graph/DS/processed/data_<serial_id>_full.pt`）を事前構築する運用に変更．
  - 一度キャッシュが存在すれば，PyG の `InMemoryDataset` は `process()`（＝危険なコードパス）を二度と呼ばなくなる．
  - `train.py` 側でも `model.baseline.model` の import を `get_loaders()` 呼び出し後まで遅延させ，危険な処理区間との同居時間を減らした（保険的対応）．

---

# 学習スクリプトの異常終了（対策と検証）

- **検証**
  - `--epochs 2` で再実行し，クラッシュなく完走することを確認（`train_acc=0.6626`，`test acc=0.5161`）．

---

# 学習スクリプトの異常終了（今後の運用）

- 新しい `serial_id` でグラフを構築する場合は，必ず `build_graph_cache_main.py --serial-id <id>` を先に実行してキャッシュを作成してから `train.py` を実行する．
- 前回実行が異常終了した場合，`scripts/datap/graph/DS/graph_info_<serial_id>.duckdb` が中途半端な状態で残ることがある（`_ensure_db_built()` はファイルの存在有無だけで再構築要否を判断するため）．再構築前に `--force` オプションで削除するか，手動で削除すること．
- 根本原因（ネイティブライブラリ競合と推定）の完全な特定には至っていないため，同様の症状が再発した場合は本メモを参照すること．

---

# 学習時間短縮の検討（HGT論文との比較）

Heterogeneous Graph Transformer（HGT）[Hu+ 2020, [arXiv:2003.01332](https://arxiv.org/abs/2003.01332)] と本プロジェクトのグラフ規模を比較した．

| | HGT（Open Academic Graph） | 本プロジェクト |
|---|---|---|
| ノード数 | 約1.79億 | 約1293万 |
| エッジ数 | 約22.4億 | 約4055万 |
| ノードタイプ数 | 5 | 4 |

---

# 学習時間短縮の検討（HGT論文との比較）
- HGTのグラフはノード数で約14倍，エッジ数で約55倍大きい．
- HGTはこの規模を実用的な時間で学習するため，**HGSampling**（ノードタイプごとに独立したサンプリング予算を持ち，次数で正規化した重要度でサンプリングする手法）を提案している．これにより次数の高いハブノードがサンプリングを支配するのを防いでいる．

---

# HGTLoader 導入の試みと見送り

PyTorch Geometric には HGSampling をそのまま実装した `torch_geometric.loader.HGTLoader` が存在するため，`NeighborLoader` からの置き換えを試みた．

- **結果**: `HGTLoader` は内部で `torch-sparse` を要求するが，本プロジェクトの環境（`torch 2.13.0+cu132`）向けのビルド済み wheel が存在せず，ソースビルドも `torch` 未検出でただちに失敗した．
- ソースビルドを強行するには C++/CUDA ビルド環境が別途必要で，かつ新たなネイティブ拡張の追加は今回のクラッシュ調査で扱った問題と同種のリスクを伴う．

---

# HGTLoader 導入の試みと見送り

PyTorch Geometric には HGSampling をそのまま実装した `torch_geometric.loader.HGTLoader` が存在するため，`NeighborLoader` からの置き換えを試みた．
- **判断**: 今回は `HGTLoader` の有効化を見送り，追加の依存関係が不要な `NeighborLoader` 側のハイパーパラメータ調整で対応する方針に変更．`get_loaders()` の `sampler` 引数（`'neighbor'` / `'hgt'`）は実装済みのまま残してあるため，環境が整えば将来的に切り替え可能．

---

# ボトルネックの実測

「学習が遅いのはノードタイプ比率の不均衡（例: option ノードが934万件と突出）が原因」という仮説を立てたが，`get_loaders()` が返す `train_loader` のバッチ構築を直接計測したところ，**この仮説は主要因としては裏付けられなかった**．

| 設定 | バッチ数/epoch | 平均時間/バッチ | 推定epoch時間 |
|---|---|---|---|
| 基準（hops=2, 近傍数=10, batch=32） | 38,706 | 57.5ms | 約37分 |
| hops=1 | 38,706 | 29.5ms | 約19分 |
| 近傍数=5 | 38,706 | 28.4ms | 約18分 |
| **batch_size=256** | 4,839 | 34.2ms | **約2.75分** |

---

# ボトルネックの実測

- ホップ数・近傍数を減らすと1バッチの処理時間はおよそ半減するが，効果は限定的．
- 支配的だったのは **`batch_size=32` に対し学習対象の stock ノードが非常に多く，1epoch あたり38,706バッチにもなっていた**こと．`NeighborLoader` の1バッチあたり固定オーバーヘッド（Python側のループ・辞書構築・GPU転送）がバッチ数に比例して積み上がっていた．
- `batch_size` を256に増やすとバッチ数が1/8になり，1バッチの処理時間はほぼ変わらないため，**エポック全体で約13.5倍の高速化**（37分→2.75分）が見込める．

---

# 学習時間短縮への対応

- `scripts/datap/graph/data_pipeline.py` の `get_loaders()` に `sampler`（`'neighbor'`/`'hgt'`）・`num_neighbors_per_hop`・`num_hops` 引数を追加し，サンプリング方式・ホップ数・近傍数を切り替え可能にした．
- `model/baseline/train.py` に `--sampler`／`--num-neighbors-per-hop`／`--num-hops` オプションを追加し，CLIから調整可能にした．
- `model/baseline/train.py` に学習済みモデルの保存処理を追加し，`model/baseline/models/<run_name>.pt` に `state_dict` を保存するようにした．
- **次のステップ**: `--batch-size 256 --num-hops 1` で本番学習を実施し，実際の学習時間短縮と精度への影響（バッチサイズ増によるパラメータ更新回数減少の影響を含む）を検証する．

---

# 学習時間の長さに対する分析

- 浮動小数点制度を `float32` から `float16` に落としたが変化なし

||float32|float16|
|---|---|---|
|batch/sec|~11/batch|~11/batch|
