# CLAUDE.ja.md

`CLAUDE.md`（Claude Codeが自動的に読み込む本体ファイル、英語）の日本語版です。内容は同一で、人間が読む用の対訳として用意しています。**Claude Codeへの指示ファイルとしては`CLAUDE.md`が正となるため、内容を変更する場合は両方のファイルを更新してください。**

（`CLAUDE.md`側にも同趣旨の指示を明記済み: `CLAUDE.md`の内容を変更した際は、同じ変更を同じターン内で`CLAUDE.ja.md`にも反映すること。）

## プロジェクト概要

個人の研究用リポジトリ（日本株・デリバティブ）。パイプラインの全体像は以下の通り。

1. **ダウンロード**: J-Quants API（Premiumプラン想定）から市場データを取得する。
2. **構築**: 生のCSV/APIデータをSQLiteにビルドし、DuckDBに変換する（`db/duckdb/*.duckdb`、株価・デリバティブ・決算・信用残高等、データ領域ごとに1ファイル）。さらにそれらを`db/synthesis/synthesis.duckdb`（スキーマ`imp`/`raw`/`store_others`）へ統合する。
3. **グラフ構築**: `synthesis.duckdb`から、GNNによる株価変動予測用のPyTorch Geometric異種グラフ（`HeteroData`）を構築する。
4. **モデル**: 構築したグラフ上でGNNの学習・評価を行う（`model/`配下、現状は最小限・WIP）。

生データはコミットしない方針で、`.gitignore`により`**/*.duckdb`・`**/*.db`・`**/*.sqlite`・`**/*.csv`・`**/*.parquet`・`**/*.json`等が除外される（`.gitkeep`のみ残る）。J-Quants APIキーは環境変数`jq_api_key`経由で渡すこと。コード中への平打ちは厳禁。

## コマンド

本プロジェクトは依存関係・venv管理に`uv`を使用する（Python >= 3.11、`pyproject.toml`参照。`.venv`は既に存在）。

```bash
uv run download_data_main.py           # J-Quants APIからデータ取得（日付範囲・レート制限などは --help 参照で上書き可能）
uv run build_db_main.py build <type> [-f|-o]   # csvからsqlite dbを構築（例: build drv -f で先物）
uv run build_db_main.py convert <type> [-f|-o]   # sqlite db -> duckdb 変換（例: convert drv -f）
uv run build_graph_main.py             # 旧・グラフ構築エントリポイント（scripts/construct_graph.py、レガシー）
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

これは実際に踏んだ地雷への対処。リポジトリ直下にある`test_temp.py`は本物のテストではなく、モジュールのトップレベルで`mock_code(serial_id=9999)`（＝グラフ構築パイプライン全体を実DBへの副作用込みで実行する処理）を直接呼び出す使い捨てスクリプトだった。このファイル名がpytestのデフォルト収集パターン`test_*.py`に一致してしまうため、何も指定せず`uv run pytest`を実行するとこのファイルがimport・実行され、収集の裏でパイプラインの本実行が走ってしまうことを実機で確認した（実際にハングし、バックグラウンドで停止させる事態になった）。`testpaths = ["tests"]`によりデフォルトの収集対象を`tests/`ディレクトリに限定し、これが意図せず起きないようにした（`uv run pytest test_temp.py`のように明示的にパスを指定した場合は引き続き実行される。これは意図的な操作なので問題ない）。`pythonpath = ["."]`は、`tests/`配下に`__init__.py`を置かない方針のもとで`tests/*.py`から`scripts...`をimportできるよう、リポジトリルートをテスト実行時の`sys.path`に追加するもの。`tests/test_smoke.py`に最小限のスモークテスト（importのみ、DBアクセス無し）を用意したが、それ以上の実質的なテストカバレッジはまだ無い。

## ディレクトリマップ

- `scripts/api/` — J-Quants APIの低レベルダウンロードヘルパー（同期・非同期）。
- `scripts/download.py`、`scripts/build_db.py`、`scripts/construct_graph.py` — ルートの`*_main.py`から呼ばれるトップレベルの処理。
- `scripts/datap/db/` — CSV/API → SQLite → DuckDB の構築処理（`constructor.py`、`cons.py`、`base/{cvt,hetero,homo,scratch}.py`）。
- `scripts/datap/graph/` — **現在アクティブに開発しているグラフ構築パイプライン**（PyG `HeteroData`）。作業のほとんどはここで行われる。主なファイル:
  - `data_pipeline.py` — ノード/エッジ登録（`preprocess`クラス）、`HeteroData`組み立て（`graphDataSet`）、`NeighborLoader`設定（`get_loaders`）。
  - `capm_corr.py` — CAPM残差のローリング相関による`stock__corr__stock`エッジ（52週窓。市場ポートフォリオという比較対象が必要なため株式限定）。
  - `derivative_corr.py` — 同一ピアグループ（同一`UndSSO`/`ProdCat`）内の生リターンのローリング相関による`option__corr__option`/`future__corr__future`エッジ（デリバティブは短命かつ市場ポートフォリオに相当するものが無いため、株式より短い窓）。
  - `cons.py` — `rel_sql`（DB/SQLファイルパス。`sql/graph/`配下を指す。ハイパーパラメータではない）と`graph_params`（**ユーザが調整すべき全ハイパーパラメータの集約先**: 相関の窓・閾値、vocabディレクトリ、分割比率、`NeighborLoader`のバッチサイズ・ホップ数等。このパイプライン内の全関数はデフォルトで`graph_params.*`を参照し、キーワード引数で個別上書き可能）。
  - `sql.py` — `sql/graph/`配下のSQLファイルをラップする`fetch.*`/`insert.*`/`create.*`静的メソッド（詳細は後述）。
  - `DS/vocab/` — グラフのノード特徴量用カテゴリカルvocabの永続化先。
  - `store/` — 中間成果物のキャッシュ（例: CAPM残差行列のparquet）。
- `sql/` — リポジトリ内の手書きSQLファイル全て。パイプライン段階ごとにまとめてある（以前は`db/sql/`や`scripts/datap/graph/sql/`等に分散していた）:
  - `sql/synthesis/` — 生テーブル（`db/duckdb`）を`synthesis.imp.*`の中間テーブル・特徴量ビューへ変換するDuckDBスクリプト群。現状は手動実行（Pythonから自動化されたエントリポイントは無い）。`sql/synthesis/_description.md`に各ファイルの入出力テーブルと生カラムの意味（例: `Mkt`市場コードの対応表: `0000`=旧東証一部、`0500`=プライム等）がまとめられている。
  - `sql/graph/` — `scripts/datap/graph/sql.py`が使う、`HeteroData`構築用クエリ群。ノードタイプごとの週次集約クエリ（株式用`get_table_to_CAPM.sql`、`get_table_to_option.sql`、`get_table_to_future.sql`、`get_fin_data_by_week.sql`）、graph-infoテーブルのDDL（`create_graph_info_table.sql`）、ノード/エッジ/feats挿入用テンプレート（`insert_to_*_table.sql`）。パスは`scripts/datap/graph/cons.py`の`rel_sql`クラスに集約されているので、変更する際はそこを直す（他所にパスをハードコードしない）。
- `db/duckdb/`、`db/sqlite/`、`db/synthesis/` — 上記のDB層（これを構築・投入する生SQLは現在`sql/synthesis/`配下にある）。
- `model/` — GNNモデルのコード（現状は最小限のWIP `Dataset`ラッパーのみ）。
- `notebooks/`、`graph_lab/`、`to_visualize_graph.ipynb` — 探索・検証用ノートブック。`graph_lab/sql/archive/`には`sql/graph/`に置き換えられた初期の試作クエリを参考用に残してある（コードからは参照されない）。
- `claude_output/` — Claude Codeセッションが実装内容をまとめたMarkdownレポート/仕様書の格納先（例: `graph_spec.md`、`derivative_nodes_edges_implementation.md`、`heterodata_batch_output_explained.md`）。作業内容のまとめ・仕様書作成を依頼された場合、特に指示が無ければここに出力する。
- `csv/`、`masks/`、`images/`、`md/` — データ/出力用の作業ディレクトリ（中身はgitignore対象）。
- `logs/` — 通常のログファイル・TensorBoardの実行ログ・モデル学習実行ログが混在して煩雑にならないよう、サブディレクトリに分離してある:
  - `logs/text/` — 通常の`*.log`テキストログファイル（詳細は後述の「ログ出力先」の注意点を参照）。
  - `logs/tensorboard/` — `model/baseline/train.py`が書き出すTensorBoardの実行ディレクトリ（イベントファイル）。
  - `logs/model_result/` — `model/<alias>/train.py`（例: `model/baseline/train.py`）の実行1回につき1ファイルの`*.log`。その実行中に標準出力へ表示される内容（パース済みハイパーパラメータ、エポックごとのtrain/val loss・acc、各種保存先パスなど）をそのまま書き出したもの。詳細は後述の「ログ出力先」の注意点を参照。

## このリポジトリ特有の注意点・落とし穴

- **`graph_v2` → `graph` への改称の経緯**: グラフパイプラインのディレクトリは以前`scripts/datap/graph_v2/`という名前だった。改称時に取りこぼした`graph_v2`参照（importパス、キャッシュファイルパス等）が実際にバグを引き起こしている（キャッシュの静かなミス、`ModuleNotFoundError`等）。どこかで`graph_v2`という文字列を見かけたら、意図的なものではなく改称の取りこぼしバグである可能性が高い。
- **DuckDBの一括insert規約**: このパイプラインの`insert.*`ヘルパーは`INSERT INTO table (SELECT * FROM data_list)`という形で、**呼び出し元Pythonフレーム内にある`data_list`という名前のローカル変数**をDuckDBが直接スキャンする仕組みに依存している。ドキュメント化されていないが動作上必須の規約であり、insert呼び出し箇所でこの変数名を変更しないこと。
- **コードごとにループしながら1行ずつDBにinsertする実装は避ける**: 銘柄・オプション・先物の多数のコードにまたがってエッジ/特徴量を構築する際、このパターンで実際に約30分規模の性能劣化が発生した実績がある。`groupby()/shift()`やpivotベースのベクトル化（`derivative_corr.py`、`data_pipeline.py`の`_prev_chain_preprocess`を参照）＋1回のバルクinsertを優先すること。
- **`HeteroData`のrepr表記**: 出力された`HeteroData`/`NeighborLoader`バッチの`x=[258, 12]`のような表記は、テンソルの**値ではなく形状（shape）**を表す。
- DuckDBのグラフ情報テーブル（`node_type`、`edge_type`）はフリーテキストのVARCHARであり、新しいノード/エッジタイプの追加はスキーマに対して非破壊的。新規追加時はDB側ではなく、Python側のレジストリ（`data_pipeline.py`内の`REVERSE_RELATIONS`、`CATEGORICAL_COLUMNS`、`using_df_list`）を拡張すればよい。
- **ログ出力先**: スクリプトやその場限りの実行で書き出す通常のテキストログファイルは、必ず`./logs/text/`配下に出力すること（例: `logs/text/<script>_<timestamp>.log`）。リポジトリ直下や`./logs/`直下、その他の場所に置いてはいけない。`scripts/api/download_util_async.py`は既にこの規約に従っている（`logging.basicConfig(filename=f"logs/text/{...}.log", ...)`）ので、新しくログ設定を書く際のパターンとして参照すること。TensorBoardの実行ログはこれとは別扱いで、`./logs/tensorboard/`配下に出力する（`model/baseline/train.py`の`--log-dir`のデフォルト値を参照）。モデル学習の実行ログはさらに別扱い（3つ目のケース）で、`./logs/model_result/`配下に、実行1回につき`<timestamp>_<alias>.log`という1ファイルとして出力する（`model/baseline/train.py`の`logging.basicConfig(handlers=[StreamHandler, FileHandler(...)])`の設定を参照。標準出力に表示される内容——パース済みCLI引数を全て含む`[params]`行も含む——をそのままそのファイルにも書き出す。`--no-file-log`を渡すとファイルハンドラのみ無効化でき、標準出力への表示には影響しない）。3つのサブディレクトリはいずれもgitignore対象（ディレクトリマップ参照）なので、コミットを汚染することはない。
