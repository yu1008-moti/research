# CLAUDE.ja.md

`CLAUDE.md`（Claude Codeが自動的に読み込む本体ファイル、英語）の日本語版です。内容は同一で、人間が読む用の対訳として用意しています。**Claude Codeへの指示ファイルとしては`CLAUDE.md`が正となるため、内容を変更する場合は両方のファイルを更新してください。**

（`CLAUDE.md`側にも同趣旨の指示を明記済み: `CLAUDE.md`の内容を変更した際は、同じ変更を同じターン内で`CLAUDE.ja.md`にも反映すること。）

## プロジェクト概要

個人の研究用リポジトリ（日本株・デリバティブ）。パイプラインの全体像は以下の通り。

1. **ダウンロード**: J-Quants API（Premiumプラン想定）から市場データを取得する。
2. **構築**: 生のCSV/APIデータをSQLiteにビルドし、DuckDBに変換する（`db/duckdb/*.duckdb`、株価・デリバティブ・決算・信用残高等、データ領域ごとに1ファイル）。さらにそれらを`db/synthesis/synthesis.duckdb`（スキーマ`imp`/`raw`/`store_others`）へ統合する。
3. **グラフ構築**: `synthesis.duckdb`から、GNNによる株価変動予測用のPyTorch Geometric異種グラフ（`HeteroData`）を構築する。
4. **モデル**: 構築したグラフ上でGNNの学習・評価を行う（`model/`配下）。**グラフ構築パイプラインとモデルのコードは現在ゼロから再構築中**であり、旧`data_pipeline.py`系パイプラインと`model/baseline/`はもう存在しない。作業ツリーに実在する内容は`claude_output/graph_spec.md`にまとめてある。

生データはコミットしない方針で、`.gitignore`により`**/*.duckdb`・`**/*.db`・`**/*.sqlite`・`**/*.csv`・`**/*.parquet`・`**/*.json`等が除外される（`.gitkeep`のみ残る）。J-Quants APIキーは環境変数`jq_api_key`経由で渡すこと。コード中への平打ちは厳禁。

## コマンド

本プロジェクトは依存関係・venv管理に`uv`を使用する（Python >= 3.11、`pyproject.toml`参照。`.venv`は既に存在）。

```bash
uv run download_data_main.py           # J-Quants APIからデータ取得（日付範囲・レート制限などは --help 参照で上書き可能）
uv run build_db_main.py build <type> [-f|-o]   # csvからsqlite dbを構築（例: build drv -f で先物）
uv run build_db_main.py convert <type> [-f|-o]   # sqlite db -> duckdb 変換（例: convert drv -f）
uv run build_graph_cache_main.py     # グラフキャッシュ構築エントリポイント（再構築中。claude_output/graph_spec.md参照）
```

`black`・`ruff`・`pytest`は`dev`依存関係グループ（`pyproject.toml`の`[dependency-groups] dev`）として利用可能。

```bash
uv run ruff check .     # lint
uv run black .          # フォーマット
uv run pytest           # テスト実行
```

`ruff`・`black`には専用設定は無く（`[tool.ruff]`/`[tool.black]`セクションなし、`ruff.toml`も無し）、それで問題ない。両者ともデフォルトで`.venv`・`.git`等を除外するため、設定無しでそのまま動作することを確認済み。

一方`pytest`には`pyproject.toml`に以下の設定が**必要だったため追加済み**:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`testpaths = ["tests"]`により、デフォルトの収集対象は`tests/`に限定される（かつてリポジトリ直下に、import時にグラフパイプライン全体を実行する使い捨ての`test_temp.py`があったため、直下に`test_*.py`名の使い捨てスクリプトを置かないこと）。`pythonpath = ["."]`はテスト実行中にリポジトリルートを`sys.path`に載せ、`__init__.py`パッケージ無しで`tests/*.py`から`import scripts...`できるようにする。`tests/test_db_connect.py`は現状、旧`db_connect`のAPIを前提としておりコードと不整合（`claude_output/graph_spec.md` §7参照）。

## ディレクトリマップ

- `scripts/api/` — J-Quants APIの低レベルダウンロードヘルパー（同期・非同期）。
- `scripts/download.py`、`scripts/build_db.py`、`scripts/construct_graph.py` — ルートの`*_main.py`から呼ばれるトップレベルの処理。
- `scripts/datap/db/` — CSV/API → SQLite → DuckDB の構築処理（`constructor.py`、`cons.py`、`base/{cvt,hetero,homo,scratch}.py`）。
- `scripts/datap/graph/` — **グラフ構築パイプライン（PyG `HeteroData`）、再構築中。** 正本の説明は`claude_output/graph_spec.md`。ファイル:
  - `db_connect.py` — `week`/`day`クラス。`get_table(name)`がSQLファイル（`string.Template`、`$START_DATE`/`$END_DATE`）を`db/synthesis/synthesis.duckdb`（read-only）に対して実行し、DataFrameを返す。
  - `dataset.py` — `MarketDataset`（PyGの`InMemoryDataset`）。`time_frame_mode`は`'w'`（週次）/`'d'`（日次）。
  - `preprocess/` — `node_utils.py`（`node_to_idx`・`varchar_to_idx`・`date_to_idx`・上場銘柄辞書）と、エッジ/ノード種別ごとのモジュール（`stock_corr_stock.py`・`stock_report_statement.py`・`stock_madeup_index.py`・`index_derivative_future.py`）。各々が`set_info(data, ...)`を持つ。
  - `loader.py` — `NeighborLoader`設定（スタブ）。
  - `dscribe.md` — 学習データ構築方法の個人メモ。
- `sql/` — リポジトリ内の手書きSQLファイル全て。パイプライン段階ごとにまとめてある（以前は`db/sql/`や`scripts/datap/graph/sql/`等に分散していた）:
  - `sql/synthesis/` — 生テーブル（`db/duckdb`）を`synthesis.imp.*`の中間テーブル・特徴量ビューへ変換するDuckDBスクリプト群。現状は手動実行（Pythonから自動化されたエントリポイントは無い）。`sql/synthesis/_description.md`に各ファイルの入出力テーブルと生カラムの意味（例: `Mkt`市場コードの対応表: `0000`=旧東証一部、`0500`=プライム等）がまとめられている。
  - `sql/graph/` — ノードタイプごとの旧・週次集約クエリ（`db_connect.week`が引き続き参照）。
  - `sql/graph_v2/` — 新・日次の取得クエリ（`fetch_*.sql`、`db_connect.day`が参照）とラベル設計メモ（`get_y.sql.md`）。
- `db/duckdb/`、`db/sqlite/`、`db/synthesis/` — 上記のDB層（これを構築・投入する生SQLは現在`sql/synthesis/`配下にある）。
- `model/` — GNNモデルのコード。現状は`model/common/`（early stopping・可視化ヘルパー）のみ。運用規約は`model/README.md`参照。
- `notebooks/`、`graph_lab/`、`to_visualize_graph.ipynb` — 探索・検証用ノートブック。`graph_lab/sql/archive/`には`sql/graph/`に置き換えられた初期の試作クエリを参考用に残してある（コードからは参照されない）。
- `claude_output/` — Claude Codeセッションが実装内容をまとめたMarkdownレポート/仕様書の格納先（現在は再構築後のデータ構築フロー仕様`graph_spec.md`のみ）。ユーザーが作業内容の要約/仕様書を求めた場合、指示がなければここに置く。
- `csv/`、`masks/`、`images/`、`md/` — データ/出力用の作業ディレクトリ（中身はgitignore対象）。
- `logs/` — 通常のログファイル・TensorBoardの実行ログ・モデル学習実行ログが混在して煩雑にならないよう、サブディレクトリに分離してある:
  - `logs/text/` — 通常の`*.log`テキストログファイル（詳細は後述の「ログ出力先」の注意点を参照）。
  - `logs/tensorboard/` — TensorBoardの実行ログ（イベントファイル）ディレクトリ。`model/<alias>/train.py`が書き出す（`--log-dir`のデフォルト）。
  - `logs/model_result/` — `model/<alias>/train.py`の実行1回につき1ファイルの`*.log`。その実行中に標準出力へ表示される内容（パース済みハイパーパラメータ、エポックごとのtrain/val loss・acc、各種保存先パスなど）をそのまま書き出したもの。詳細は後述の「ログ出力先」の注意点を参照。

## このリポジトリ特有の注意点・落とし穴

- **`graph_v2`の名前について**: `sql/graph_v2/`は再構築後パイプラインが使う*新しい*（日次）SQLディレクトリで、意図的なもの。一方、旧Pythonパッケージパス`scripts/datap/graph_v2/`はもう存在しないので、`scripts.datap.graph_v2`のimportは取りこぼしバグである。
- **コードごとにループしながら1行ずつDBにinsertする実装は避ける**: 銘柄・オプション・先物の多数のコードにまたがってエッジ/特徴量を構築する際、このパターンで実際に約30分規模の性能劣化が発生した実績がある。`groupby()/shift()`やpivotベースのベクトル化＋1回のバルクinsertを優先すること。
- **`HeteroData`のrepr表記**: 出力された`HeteroData`/`NeighborLoader`バッチの`x=[258, 12]`のような表記は、テンソルの**値ではなく形状（shape）**を表す。
- **ログ出力先**: スクリプトやその場限りの実行で書き出す通常のテキストログファイルは、必ず`./logs/text/`配下に出力すること（例: `logs/text/<script>_<timestamp>.log`）。リポジトリ直下や`./logs/`直下、その他の場所に置いてはいけない。`scripts/api/download_util_async.py`は既にこの規約に従っている（`logging.basicConfig(filename=f"logs/text/{...}.log", ...)`）ので、新しくログ設定を書く際のパターンとして参照すること。TensorBoardの実行ログはこれとは別扱いで、`./logs/tensorboard/`配下に出力する。モデル学習の実行ログはさらに別扱い（3つ目のケース）で、`./logs/model_result/`配下に、実行1回につき`<timestamp>_<alias>.log`という1ファイルとして出力する（`logging.basicConfig(handlers=[StreamHandler, FileHandler(...)])`の設定で、標準出力に表示される内容——パース済みCLI引数を全て含む`[params]`行も含む——をそのままそのファイルにも書き出す。`--no-file-log`を渡すとファイルハンドラのみ無効化でき、標準出力への表示には影響しない）。3つのサブディレクトリはいずれもgitignore対象（ディレクトリマップ参照）なので、コミットを汚染することはない。
