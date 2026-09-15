# `sql/synthesis/` 配下 SQL ファイルの処理内容

`sql/synthesis/` 配下の各 `*.sql` は、`db/sqlite` / `db/duckdb` に取り込んだ**生テーブル**を、
学習・分析用の**中間テーブル（`*_tmp`）または特徴量ビュー**へ変換する DuckDB スクリプトである。
生テーブル名・シンボル名の対応は [`scripts/datap/db/cons.py`](../../scripts/datap/db/cons.py) の
`tbl_names` / `doc_symbols` を参照。

| ファイル | 入力テーブル | 出力 | 系列 |
|:-|:-|:-|:-|
| [`equities_bars.sql`](equities_bars.sql) | `eqt_main` | `eqt_main_tmp` | equities |
| [`equities_investor-type.sql`](equities_investor-type.sql) | `eqt_inv` | SELECT 結果（ビュー相当） | equities |
| [`futures.sql`](futures.sql) | `drv_ftr` | `drv_ftr_tmp` | derivatives |
| [`options.sql`](options.sql) | `drv_opt` | `drv_opt_tmp` | derivatives |
| [`fin_summary.sql`](fin_summary.sql) | `fin_sum` | `fin_sum_tmp` | financial |
| [`indices_put_name.sql`](indices_put_name.sql) | `idx_prc` | `idx_prc_tmp` | index |
| [`margin_breakdown.sql`](margin_breakdown.sql) | `mbd_qtt` | （テーブル名未指定） | markets |

---

## `equities_bars.sql`

**目的**：株式日次バー（`eqt_main`）を整形し、調整済み価格の前方補完・セッション別 OHLC の欠損補完・
IPO 初日フラグ付与・業種／市場コードの指数テーブル互換化を行った `eqt_main_tmp` を作る。

**主な処理**

1. `base`（内側サブクエリ）
   - `Date` を `DATE` 型 `TradeDate` に変換。
   - `LAST_VALUE(AdjC IGNORE NULLS)` で調整後終値 `AdjC_f` を前方補完。
   - `WHERE` で **2020-10-01（東証システム障害日）**の一部銘柄行（`Code` 5 桁目が `1/2/9`）を除外。
2. `base`（外側）
   - 場（セッション）別の調整後終値を補完：
     `AAdjC_f = COALESCE(AAdjC, AdjC_f, MAdjC)`（後場）、
     `MAdjC_f = COALESCE(MAdjC, LAG(AAdjC_f))`（前場、無ければ前日後場）。
   - `Code` パーティション内で最初の行（`ROW_NUMBER() OVER w = 1`、`w = PARTITION BY Code ORDER BY TradeDate`）
     **かつ** その `TradeDate` がデータセット全体の最古日（`MIN(TradeDate) OVER ()`、実質 2008-05-07 のデータ取得開始日）
     より後である行を `IPO = 1` とする。
     - 旧実装は `MAdjC_f IS NULL` を条件にしていたが、上場初日に寄り付き取引があると `MAdjC` が非 NULL になり
       `IPO` が 0 のままになる不具合があった。
     - 単純に「`Code` ごとの最初の行」だけで判定すると、2008-05-07（データ取得開始日）時点で
       **既に上場済みだった銘柄**（データ取得範囲の先頭に居合わせただけの銘柄。例：`13010`）まで
       誤って `IPO = 1` になってしまうため、「データセット全体の最古日より後」という条件を追加して除外している。
3. `base_v2`：補完後の各終値の NULL を `0` 埋め。
4. `eqt_main_o`：日次／前場／後場それぞれの OHLC、値幅上限・下限（`UL`/`LL` 等）、
   業種コード `S33`/`S17`、市場コード `Mkt`、信用区分 `Mrgn` を抽出。
5. 最終 `SELECT`（`base_v2` に `eqt_main_o` を `LEFT JOIN`）
   - O/H/L が欠損の場合は当日終値で埋める（`COALESCE(o.DAdjO, t.DAdjC)` 等）。
   - `S33`：内部業種コード → 東証業種別指数と同じコード体系（`'0040'`〜`'0060'`, `'9999'`）へ変換。
   - `S17`：TOPIX-17 業種番号 → `'0080'`〜`'0090'` へ変換。
   - `Mkt`：市場コード＋日付レンジで市場区分コードへ変換（2022/06/27 以降のプライム／スタンダード／
     グロース、2022/04/04〜06/27 の移行期コード、マザーズ、東証一部／二部、JASDAQ など**市場再編の履歴**を反映）。
   - `WHERE o._Mkt != 0105` で **TOKYO PRO MARKET を除外**。

---

## `equities_investor-type.sql`

**目的**：投資部門別売買状況（`eqt_inv`）の生の売り／買い／合計金額を、
**売買インバランス比率**と**委託総額に対する構成比（ウェイト）**の特徴量に変換する。
`CREATE TABLE` は伴わず `SELECT` 結果を返す（特徴量ビュー相当）。

**主な処理**

1. `spare_feature` CTE：複合投資家グループを合算。
   - `FinIns*` ＝ 生損保 `InsCo` ＋ 銀行 `Bank` ＋ 信託銀行 `TrstBnk` ＋ その他金融 `OthFin`（金融機関計）。
   - `Ins*` ＝ 投資信託 `InvTr` ＋ 事業法人 `BusCo` ＋ その他法人 `OthCo` ＋ `FinIns`（法人計）。
   - `WHERE` で `PubDate >= 2008-05-07`、`Section != 'TokyoNagoya'` に限定。
2. 最終 `SELECT`（`eqt_inv` と `spare_feature` を `PubDate`・`Section` で `JOIN`）
   - `PubDate` を `DATE` 化。`Section` を `Section_id`（`TSE1st=1` … `TSEGrowth=7`、その他 `0`）へ数値化。
   - `*BSRatio` ＝ `(Sell+1)/(Buy+1)`：投資家区分別の売買比率（`+1` はゼロ除算回避の平滑化）。
     対象：自己 `Prop`、委託 `Brk`、総計 `Tot`、個人 `Ind`、海外 `Frgn`、証券会社 `SecCo`、
     `InvTr`／`BusCo`／`OthCo`／`FinIns`／`InsCo`／`Bank`／`TrstBnk`。
   - `*Weight` ＝ 区分別 `Tot` / 委託 `BrkTot`：委託売買代金に占める構成比。
   - `TotRatio` ＝ `(PropTot+1)/(BrkTot+1)`。
   - `OthFin` の比率・ウェイトは**多重共線性回避のためコメントアウトで除外**。

---

## `futures.sql`

**目的**：先物日次バー（`drv_ftr`）を整形し、`drv_ftr_tmp` を作る。
主眼は **`DeviationRate`（清算値乖離率）と `SQRemainingDays`（SQ までの残日数）の欠損補完**。

**主な処理**

1. `base_ftr`
   - `Date` 文字列先頭 10 桁 → `DATE` 型 `TradeDate`。
   - 場別 OHLC（`MO`〜`EC`）、`VoOA`・`Settle`・`SQD`・`LTD`・`CM`・`CCMFlag` を `EXCLUDE`。
   - `DeviationRate = log((Settle+1)/(C+1))`：清算値と終値の乖離。
   - `SQRemainingDays = (LTD + 1) - TradeDate`：最終取引日までの日数。
   - `CM`：先頭 7 文字 → `'YYYY-MM'`（限月）。
   - `NULL_TYPE_1`：`DeviationRate` の欠損マスク。
2. `base_v1`：`Code, CM` でパーティション、`TradeDate` 昇順。行番号 `rn`、
   次行の取引日 `Lag_TradeDate`（`LAG(..., -1)` ＝ LEAD 相当）を付与。
3. `base_v2`：各 `Code, CM` グループの最終行を `isMax` で判定。
   `SQRemainingDays_NULLS` ＝ 最終行なら `1`、それ以外は「次の取引日までの日数」。
4. `base_v3`：`TradeDate` 降順の累積和で `SQRemainingDays` を再構成
   （＝限月末までの**取引日数**を数え直し、`LTD` 由来値の欠損・不整合を吸収）。
5. `filled`：`base_ftr` と `base_v3` を結合。`DeviationRate` の NULL は `0` に置換、
   `SQRemainingDays` は再構成値を採用。
6. 最終出力列：`TradeDate, Code, EmMrgnTrgDiv, O, H, L, C, Vo, Va, OI,
   DeviationRate, SQRemainingDays, CM, NULL_TYPE_1`。

---

## `options.sql`

**目的**：オプション日次バー（`drv_opt`）を整形し、`drv_opt_tmp` を作る。
`moneyness`・理論価格乖離・IV・SQ 残日数を導出し、欠損は `0` 埋め＋マスク列で管理する。

**主な処理**

1. `base_opt`
   - `Date` 先頭 10 桁 → `DATE` 型 `TradeDate`。
   - 欠損率の高い列を `EXCLUDE`：場別 OHLC（`EO`〜`EC` 約 92%欠、`MO`〜`MC`、`AO`〜`AC`）、
     `SQD`（100%欠）、`Theo/BaseVol/IR/CCMFlag`（約 22%欠 → NULL-TYPE-1）、
     `Settle/UnderPx/VoOA/Strike`（約 6%欠 → NULL-TYPE-2）。
   - `DeviationRate = log((Settle+1)/(Theo+1))`：清算値と理論価格の乖離。
   - `Moneyness = log(UnderPx / Strike)`。
   - `SQRemainingDays = (LTD + 1) - TradeDate`。
   - `CM` → `'YYYY-MM'`。
   - `NULL_TYPE_1`（`DeviationRate` 欠損マスク）、`NULL_TYPE_2`（`Moneyness` 欠損マスク）。
2. `filled`：`DeviationRate, Moneyness, IV, SQRemainingDays` の NULL を `0` に置換。
3. 最終出力列：`TradeDate, Code, EmMrgnTrgDiv(=PCDiv), ProdCat, UndSSO,
   O, H, L, C, Vo, Va, OI, Moneyness, DeviationRate, SQRemainingDays, IV, CM,
   NULL_TYPE_1, NULL_TYPE_2`。
   - 先物と異なり `SQRemainingDays` の取引日数再構成は行わず、単純に `0` 埋めする。

---

## `fin_summary.sql`

**目的**：決算短信サマリー（`fin_sum`）を、水準・単四半期利益・成長率／達成率・
一株指標・キャッシュフローからなる**密な対数スケール特徴量テーブル** `fin_sum_tmp` に変換する。
存在フラグ（`Exist_*`）と全欠損フラグ（`NULL_Flag`）も付与する。
詳細解説は [`md/RE_fins_summary.md`](../../md/RE_fins_summary.md) 参照。

**マクロ**（`CREATE OR REPLACE TEMP MACRO`）

| マクロ | 役割 |
|:-|:-|
| `Cast2Date(x)` | 文字列日時 → `DATE` 型 |
| `isExist(x)` | NULL なら `0`、非 NULL なら `1` |
| `CalcRatio(x, y)` | `x*y = 0` なら `0`、それ以外 `x/y`（ゼロ除算回避） |
| `ffill(x, w, …)` | 前方補完。`w` で窓範囲を切替（`*`＝四半期→年→全期間の順, `Y`＝年, `Q`＝同四半期, `A`＝全期間） |
| `getLag(x, w, …)` | `LAG` 取得。`w`＝`Y`/`Q`/`A`/`S`（単純窓）で窓を切替 |
| `myLog(x)` | 符号付き対数：`x>0`→`log(x)`, `x<0`→`-log(-x)`, `x=0`→`0` |

**CTE パイプライン**（`fin_sum_tmp`）

| CTE | 処理 |
|:-|:-|
| `ini` | 日付列を `DATE` 化。`L_DiscDate`（前回開示日）・`gap_DiscDate_CurPerEn`（開示日−会計期間末）を算出。`WHERE` で `CurPerType ∈ {1Q,2Q,3Q,FY}`、`DocType` が連結・日本基準の決算短信に合致する行のみに限定 |
| `base` | `DiscDate - L_DiscDate > 60`（訂正・重複開示の除外）かつ `0 < gap < 60`（期末から約 2 か月以内の開示）で行を絞る |
| `EasyRepl` | CF 各項目を `0` 埋め、予想配当 `FDiv*` を `COALESCE(FDiv*, NxFDiv*)` で補完 |
| `isExistBinary` | `Eq, TA, Sales, OP, OdP, NP`、株式数、CF の存在フラグ |
| `ForwardFill_pre` | `TA`・`Eq` を `ffill('*')` |
| `ForwardFill` | `Sales/OP/OdP/NP`、株式数、`EqAR`、予想配当、予想 `Sales/OP/OdP/NP/EPS` を `ffill` |
| `ReallyGain` | 期首来累計値から前四半期分（`getLag('Y')`）を差し引き、**単四半期の実額**に変換 |
| `PreQ_Vals` | 前四半期の `TA/Eq`（`getLag('S')`）、前年同四半期値（`lysQ`, `getLag('Q')`）、前四半期の成長（`preQ`, `getLag('S')`）、前回予想配当 |
| `calculated` | 対売上高比率、対前四半期・対前年同期の成長率、達成率（実績 vs 予想）、`TA/Eq` 成長率、自己株式／発行済株式比率 |
| `SimpleQuery` | `CurPerType` に応じた配当（`Div`, `FDivNxQ`）、`EPS/BPS`（`Eq`／株式数からのフォールバック付き）、`DivAnn`（年間合計）、`FCF = CFO+CFI` を確定し、多数の特徴量に `myLog` を適用 |
| `Aggr` | `SimpleQuery` と `isExistBinary` を結合 |
| `GetNULLFlag` | 全列を `LIST_REDUCE` で総和し、全列 NULL の行を検出 |
| `fill_NULL_BY_ZERO` | 全特徴量を `0` 埋めし、カテゴリ別（Profit Ratio / Sales / OP / OdP / NP / Balance Sheet / Div / Shares / Indicator / Cash Flow）に整理して出力。`NULL_Flag` を付与 |

最終行は `SELECT * FROM fill_NULL_BY_ZERO`。

---

## `indices_put_name.sql`

**目的**：指数価格テーブル（`idx_prc`）の全列に加え、
`Code` から**指数名 `IdxNm`** と**業種リンク用コード `S33` / `S17`** を導出した `idx_prc_tmp` を作る。
これにより指数系列を株式（`eqt_main_tmp`）と業種・市場単位で結合できる。

**主な処理**（`SELECT *,` ＋ 3 つの派生 `CASE` 列）

1. `IdxNm`：`Code` → 日本語の指数名称。
   - 東証業種別指数 33 業種（`'0040'`〜`'0060'`）とその「配当込み」版（`'6040'`〜）
   - TOPIX-17（`'0080'`〜`'0090'`）と配当込み版（`'6080'`〜）
   - プライム／スタンダード／グロース市場指数（`'0500'`〜）と移行期の配当込みコード（`'7000'`〜）、
     マザーズ／グロース市場 250、TOPIX、東証二部総合指数、JASDAQ INDEX
   - JPX 指数（プライム 150、スタートアップ急成長 100、日経インデックス 400）
   - TOPIX 規模別（Core30 / Large70 / 100 / Mid400 / 500 / Small / 1000 / Small500）
   - TOPIX バリュー／グロース、REIT 指数、その他（配当フォーカス 100、税引後配当込み等）
2. `S33`：業種別指数コード（`'0040'`/`'6040'` などのペア）→ `eqt_main` と同じ S33 業種コード
   （`'0050'`, `'1050'`, …, `'9050'`）。
3. `S17`：TOPIX-17 指数コード → S17 業種番号 `'1'`〜`'17'`。

> **備考（要修正）**：現状の SQL は `S33` の直前・`S17` の直前にカンマが無く、
> かつ末尾が `END AS Mkt` で外側 `CASE` にラップされた形になっており、そのままでは実行できない。
> 意図は上記 3 列（`IdxNm`, `S33`, `S17`）を並べて `SELECT` することにあると解釈している。

---

## `margin_breakdown.sql`

**目的**：信用取引内訳の数量テーブル（`mbd_qtt`）に対し、
`Date`・`Code` 以外の全数量列へ `log(x + 1)` 変換を一括適用する。

**処理**

```sql
CREATE OR REPLACE TABLE <未指定> AS (
  SELECT
    Date, Code,
    LOG(COLUMNS(* EXCLUDE (Date, Code)) + 1)
  FROM mbd_qtt
);
```

- `COLUMNS(* EXCLUDE (Date, Code))` で残り全列をまとめて対数化（DuckDB の列式）。
- `+ 1` はゼロ・小値対策の平滑化。

> **備考（要修正）**：`CREATE OR REPLACE TABLE` の直後に**出力テーブル名が欠落**しており、
> 括弧・セミコロンの対応も崩れているため、このままでは実行できない。
> 命名規約上の出力名は `mbd_qtt_tmp`（他系列に倣うと `*_tmp`）が妥当と思われる。
