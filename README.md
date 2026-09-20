# 研究用のリポジトリ

## 目的

データ処理がメインだが，可能ならモデル実装から評価まで同じリポジトリで実行する．

## 使い方

api-key を自身のコンピュータの環境変数（jq_api_key）に設定したら，以下でデータを取得することが可能となる．このとき注意されたいのが，コードに api-key の平打ちをしないことだ．また，本研究では プロジェクト管理ツールである uv を活用して開発した背景があり，CLI では uv から実行している．原理的には不要だが，もし気になるなら各自でインストールされたい．

```bash
uv run download_data_main.py 
```

ただし，本プロジェクトは J-Qaunts の Premium プランを想定している．そのため，コードを流用する際には API コール制限に注意すること．取得に関して設定を変更する場合は，`download_data_main.py` を書き換える必要はなく，CLI 引数で上書きできる．

```bash
uv run download_data_main.py --per-sec-rate-limit 5
# 500req/min -> 8req/sec -> buffered: 5req/sec
# According to your plan, you can change this limit-number
```

データを取得後，masks/only_date_mask.npy を用いて，取引可能な日付以外のデータを除去する必要がある．そのためには，

1. test/to_get_base_information.ipynbを実行
2. test/to_create_masks.ipynb を実行
3. test/to_extract_valid_data.ipynbを実行

本当はここまでワンセットで実装したいが，時間がないため利用者の理解力がエクセレントであることを祈る．

また，データを取得した後，sqlite3／duckdbへデータを変換可能である．ちなみに私は duckdb がお気に入りである．duckdbへ変換する場合は，以下のコードを実行してほしい．ちなみに，以下のコードは例なので，用途に応じてフラグや引数を変える必要がある．今回は，先物データを sqlite3 形式で保存した後，続けて duckdb 形式に保存している．constant.py ファイルの設定を変更すると１行目だけで済むのだが，変更は推奨しない．
`uv run download_data_main.py --help` で他の引数（`--range-type`／`--fetch-time-length`／`--fetch-time-scale`／`--from-date`／`--to-date`／`--async-semaphore-limit`）も確認できる．

また，データを取得した後，sqlite3／duckdbへデータを変換可能である．ちなみに私は duckdb がお気に入りである．duckdbへ変換する場合は，以下のコードを実行してほしい．ちなみに，以下のコードは例なので，用途に応じてフラグや引数を変える必要がある．今回は，先物データを sqlite3 形式で保存した後，続けて duckdb 形式に保存している．

```bash
uv run build_db_main.py build drv -f
uv run build_db_main.py convert drv -f
```

これで，先物データを duckdb で扱えるようになる．<br>

## 使ってみたい・使えそうな技術・知見

- Lee-Hanning の検定 <https://www.msi.co.jp/solution/stuaward/2010/10ibara.pdf>
- flash attention <https://zenn.dev/uchiiii/articles/306d0bb7ef67a7>

## 注意事項

ここから先を現在でも開発中であり，もし縁あって私の後輩が本リポジトリを使用することがあれば，なんでも聞いてほしいと思っている．

ただし，もちろん API をしっかり契約することを求める．

また，本プロジェクト内において散見される株価データ等は，J-Quants から取得したデータではない．説明のために仮定した株価・外部から取得した誰でも利用可能なデータベースから直接取得している．

さらに，生データを断じて載せていない点は強調しておきたい．

再三申し上げるが，J-Quants の API を利用する場合は，必ず **各人単位** にて契約を行うこと．

## プロジェクト内 Markdown ファイル一覧

リポジトリ内に存在する全 Markdown ファイルのパスと内容サマリ（2026-09-17 時点）。

### 指示・設定ファイル

| パス | サマリ |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Claude Code 向けのリポジトリ運用指示（英語・正本）。プロジェクト概要・コマンド一覧・ディレクトリマップ・このリポジトリ特有の注意点（`graph_v2`残骸バグ，DuckDBの`data_list`規約，per-codeループ禁止，ログ出力先など）をまとめている。 |
| [`CLAUDE.ja.md`](CLAUDE.ja.md) | `CLAUDE.md`の日本語対訳（人間向け）。内容は同一で、`CLAUDE.md`更新時に同期する運用。 |

### `claude_output/` — Claude Code セッションの実装報告・調査レポート

| パス | サマリ |
|---|---|
| [`claude_output/graph_spec.md`](claude_output/graph_spec.md) | `scripts/datap/graph/`配下（`data_pipeline.py`・`capm_corr.py`・`derivative_corr.py`・`cons.py`・`sql.py`・`main.py`）の全関数・全クラスのシグネチャ・処理内容・前提条件・副作用を網羅した関数レベル仕様書。4ノードタイプ（stock/statement/option/future）・12エッジタイプの構造や`graph_v2`改称の経緯にも言及。 |
| [`claude_output/derivative_nodes_edges_implementation.md`](claude_output/derivative_nodes_edges_implementation.md) | オプション・先物ノードとその関連6エッジタイプを追加した実装報告。ダングリングエッジバグと`option_prev_option_preprocess`の性能問題（約30分→数秒）の発見・修正、`graph_params`へのハイパーパラメータ一元化を記録。 |
| [`claude_output/heterodata_batch_output_explained.md`](claude_output/heterodata_batch_output_explained.md) | `NeighborLoader`が返す`HeteroData`バッチのprint出力の読み方（`x=[N,D]`はshapeであること等）を解説。`stock,derivative,future`エッジのハブ構造や`num_neighbors`均一設定など今後のチューニング論点も記載。 |
| [`claude_output/baseline_training_resource_analysis.md`](claude_output/baseline_training_resource_analysis.md) | `model/baseline/`学習時のGPU/CPU/RAMリソースを実測したレポート。GPUメモリは実質無視できる水準（<200MB）で、ボトルネックはCPU側`NeighborLoader`サンプリングにあると結論。`num_workers`導入（2.5倍高速化）や`pin_memory`検証（不採用）も記録。 |
| [`claude_output/reports/train_bottleneck_investigation_20260916.md`](claude_output/reports/train_bottleneck_investigation_20260916.md) | `torch.profiler`を用いたAdam.stepボトルネック調査。「Self CUDA 37%」が表示上のアーティファクトだったこと、実コストは`aten::mm`とEmbedding backwardが中心であること、GPUメモリ懸念の誤解の解消などを記録。 |

### `md/` — データ調査・設計メモ（データ処理用スクラッチ）

| パス | サマリ |
|---|---|
| [`md/feats/Node_Code_Rule.md`](md/feats/Node_Code_Rule.md) | ノードを一意に決定するNODE_IDルールの試案（未完成・検討中）。 |
| [`md/feats/RE_fins_summary.md`](md/feats/RE_fins_summary.md) | 決算情報（`fin_sum`）の特徴量処理方針まとめ。メタ特徴量・配当情報・決算情報の運用方法と、`fin_summary.sql`のマクロ定義・CTEパイプラインの詳細解説。 |
| [`md/feats/drv_ftr_study.md`](md/feats/drv_ftr_study.md) | 先物データ（`drv_ftr`）調査。CodeのProdCat体系整理と`SQRemainingDays`欠損補完等の特徴量操作をまとめる。 |
| [`md/feats/drv_opt_study.md`](md/feats/drv_opt_study.md) | オプションデータ（`drv_opt`）調査。`IR`/`SQD`等の不使用列の根拠、`Theo`/`Settle`等の共線性検討とそれに基づく`DeviationRate`/`Moneyness`等の特徴量設計。 |
| [`md/feats/eqt_ivt_study.md`](md/feats/eqt_ivt_study.md) | 投資部門別データ（`eqt_inv`）調査。`Section`/`Mkt`対応表、投資家区分別の売買比率・ウェイト特徴量のSQL設計。 |
| [`md/feats/eqt_main_study.md`](md/feats/eqt_main_study.md) | 指数データ利用方針。`Mkt`カテゴリ・S33/S17業種カテゴリの対応表整理と、`eqt_main_tmp`構築SQLの解説（市場再編履歴の反映含む）。 |
| [`md/feats/fins_summary.md`](md/feats/fins_summary.md) | 決算情報（fins_summary）の開示書類種別ごとの使用可否判定、Div系特徴量の欠損率・組み合わせパターンの整理。 |
| [`md/feats/how_build_db.md`](md/feats/how_build_db.md) | DB構築のTODO・進捗管理。各データタイプの構築済み/無視項目とその理由の一覧。 |
| [`md/feats/how_to_forward_fill.md`](md/feats/how_to_forward_fill.md) | 株価欠損データの前方補完ルールとBefore/After例（架空データ使用）。 |

### モデル関連

| パス | サマリ |
|---|---|
| [`model/README.md`](model/README.md) | `model/`配下の運用ルールとグラフデータ（`HeteroData`）リファレンス。ノード/エッジタイプ一覧、ラベル(`y`/`y_valid`)の扱い、既知のNaN・スケール問題、`train.py`/`eval.py`の規約をまとめた頻用参照ドキュメント。 |
| [`model/baseline/model_structure.md`](model/baseline/model_structure.md) | `write_model_structure_md()`による`BaselineHeteroGNN`のモジュール階層自動生成ドキュメント（Mermaid図）。`train.py`実行毎に上書き。 |

### その他

| パス | サマリ |
|---|---|
| [`fix_error_report.md`](fix_error_report.md) | Marp形式のスライドメモ。東証・大証統合による決算-株価データ不整合、`train.py`のACCESS_VIOLATIONクラッシュの切り分けと対策（`build_graph_cache_main.py`分離）、HGT論文との比較検討・`HGTLoader`導入見送り、`batch_size`増加によるNeighborLoaderオーバーヘッド削減（37分→2.75分）の検討記録。 |
| [`notebooks/readme.md`](notebooks/readme.md) | `notebooks/`配下の全ファイルが閲覧不可設定である理由（著作権・個人情報保護のため）の説明。 |
| [`sql/README.md`](sql/README.md) | `sql/`ディレクトリ全体の構成説明。`synthesis/`（生テーブル→中間テーブル変換、手動実行）と`graph/`（グラフ構築用、`sql.py`経由）の役割分担、パス管理は`cons.py`の`rel_sql`に集約する旨。 |
| [`sql/synthesis/_description.md`](sql/synthesis/_description.md) | `sql/synthesis/`配下各SQLファイル（`equities_bars.sql`・`equities_investor-type.sql`・`futures.sql`・`options.sql`・`fin_summary.sql`・`indices_put_name.sql`・`margin_breakdown.sql`）の入出力テーブルとCTE単位の処理内容を詳細解説。`indices_put_name.sql`・`margin_breakdown.sql`に構文上の要修正点があることも指摘。 |
