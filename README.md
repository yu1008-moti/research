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

リポジトリ内に存在する主要な Markdown ファイルのパスと内容サマリ（2026-10-11 時点。モデル・データ構築フローの再構築に伴い旧フロー関連の文書は整理済み）。

### 指示・設定ファイル

| パス | サマリ |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Claude Code 向けのリポジトリ運用指示（英語・正本）。プロジェクト概要・コマンド一覧・ディレクトリマップ・このリポジトリ特有の注意点（`graph_v2`残骸バグ，DuckDBの`data_list`規約，per-codeループ禁止，ログ出力先など）をまとめている。 |
| [`CLAUDE.ja.md`](CLAUDE.ja.md) | `CLAUDE.md`の日本語対訳（人間向け）。内容は同一で、`CLAUDE.md`更新時に同期する運用。 |

### `claude_output/` — Claude Code セッションの仕様書・調査レポート

| パス | サマリ |
|---|---|
| [`claude_output/graph_spec.md`](claude_output/graph_spec.md) | 再構築中のデータ構築フロー仕様（`db_connect.py` → `dataset.py` → `preprocess/*`）。実在するコードのみを記述し、未実装箇所と既知の不整合も列挙。旧仕様は git 履歴を参照。 |

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
| [`model/README.md`](model/README.md) | `model/`配下の運用ルール（`model/<alias>/` 構成、`train.py`/`eval.py` の共通引数、ログ・保存物の置き場）。旧 `HeteroData` リファレンスは再構築に伴い破棄。 |

### その他

| パス | サマリ |
|---|---|
| [`scripts/datap/graph/dscribe.md`](scripts/datap/graph/dscribe.md) | 学習データ構築方法の個人メモ（使用期間、前処理をディスク保存前に行う理由、カテゴリ/日付マッピング）。 |
| [`md/my_memo/labeling_memo.md`](md/my_memo/labeling_memo.md) | ラベル `y`（翌営業日リターン）を3クラスに分ける検討クエリと分位点・クラス比率の実測。 |
| [`notebooks/readme.md`](notebooks/readme.md) | `notebooks/`配下の全ファイルが閲覧不可設定である理由（著作権・個人情報保護のため）の説明。 |
| [`sql/README.md`](sql/README.md) | `sql/`ディレクトリ全体の構成説明。`synthesis/`（生テーブル→中間テーブル変換、手動実行）・`graph/`（旧・週次）・`graph_v2/`（新・日次）の役割分担。 |
| [`sql/synthesis/_description.md`](sql/synthesis/_description.md) | `sql/synthesis/`配下各SQLファイル（`equities_bars.sql`・`equities_investor-type.sql`・`futures.sql`・`options.sql`・`fin_summary.sql`・`indices_put_name.sql`・`margin_breakdown.sql`）の入出力テーブルとCTE単位の処理内容を詳細解説。`indices_put_name.sql`・`margin_breakdown.sql`に構文上の要修正点があることも指摘。 |
