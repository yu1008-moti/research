# r8_Oct5v スキーマ テーブル説明

`db/synthesis/session.log` (DuckDB CLI セッションログ) から復元した、`synthesis.duckdb` 内 `r8_Oct5v` スキーマの作成過程と各テーブルの説明。

## 全体像

元データは `imp.*` (加工済み) または `raw.*` (生)。期間フィルタは `2000-01-01 ≤ TradeDate ≤ 2029-12-31` (実データは 2008-05-07 〜 2026-04-17)。

| テーブル | 元 | 粒度 | 役割 |
|---|---|---|---|
| `stocks` | `imp.eqt_main` | 銘柄×日 | 株価ノード |
| `statements` | `imp.fin_sum` | 銘柄×開示日 | 決算ノード |
| `futures` | `raw.drv_ftr` | 限月×日 | 先物ノード |
| `market_index` | `raw.idx_prc` | 指数×日 | 指数ノード |
| `y_label` | `imp.eqt_main` | 銘柄×日 | 教師ラベル |
| `mapping_nodeID` | 上記 4 ノード表 | ノード×日 | ノード名とグローバル ID の対応表 |

## 各テーブル

### stocks (株価ノード)
`imp.eqt_main` から 19 列を抽出。
- `TradeDate`, `Code`
- `MAdjO/H/L/C`, `MUpL`, `MLoL`: 前場の調整後 OHLC とストップ高・安の値幅 (列名からの推測)
- `AAdjO/H/L/C`, `AUpL`, `ALoL`: 後場の調整後 OHLC とストップ高・安の値幅 (同上)
- `AdjVo`: 調整後出来高
- `Mrgn`: 信用区分
- `S33`, `S17`: 業種コード
- `Mkt`: 市場コード

### statements (決算ノード)
`imp.fin_sum` の `DiscDate` を `TradeDate` に改名し先頭へ移動したもの。
- `CurPerType`, `CurFYEn`: 決算期の種別・期末日
- `log_Sales`, `log_OP`, `log_OdP`, `log_NP`: 売上・営業利益・経常利益・純利益の対数
- 各項目の `_GrowthRatio`, `_AchievementRatio`, `_ReallyGain`, `Exist_*`: 成長率、予想達成率、実質増分、データ有無フラグ
- `log_TA`, `log_Eq`, `log_EPS`, `log_BPS` など: 総資産、純資産、1 株当たり指標
- `log_FCF`, `log_CFO`, `log_CFI`, `log_CFF`, `log_CashEq`: キャッシュフロー系
- `Div`, `FDiv`, `DivAnn`: 配当
- `null_Flag`

### futures (TOPIX 先物ノード)
`raw.drv_ftr` の `ProdCat = 'TOPIXF'` のみ。
- `Code` は `substring(CM,3,2) || substring(Code,4,2)` で作った 4 桁の限月コード (例 `0806`, `1903`)
- `TradeDate` は `Date` を date 型へ変換
- 値の列: `O/H/L/C` (日通し)、`AO/AH/AL/AC` (日中)、`Vo`、`OI` (建玉)、`Va`、`VoOA`、`EmMrgnTrgDiv`、`LTD` (最終取引日)、`Settle` (清算値)、`CCMFlag` (中心限月フラグ)
- 初期名は `features`。`futures` に改名して `features` は drop
- `(TradeDate, Code)` の重複を `row_number()` の `inquiry_id = 1` で除去 (23,753 → 23,728 行)。除去後 `inquiry_id` 列は削除。重複は `EmMrgnTrgDiv` の違いが主因とみられる
- 出来高のない限月が `Settle` のみを持つ行が大半

### market_index (指数ノード)
`raw.idx_prc` を指定コードに絞ったもの。
- 対象: `0000`, `0040〜0060`, `0080〜0090` (TOPIX 本体と業種別指数と推測)。`0060` はリストに重複しているが結果は同じ
- 列: `TradeDate, Code, O, H, L, C, index_id` (`index_id` は `Code` のコピー)

### y_label (教師ラベル)
1. `imp.eqt_main` のうち `Mkt in ('0000','0500','7000')` に限定
2. 銘柄ごとに `lag(..., -1)` で翌営業日の `l1_TradeDate`, `l1_DAdjC` を取得
3. `return = l1_DAdjC / DAdjC - 1` (翌日リターン)
4. NULL / NaN / Inf / `AdjVo = 0` を除外 (temp テーブル `final_return`)
5. `final_return` に手作業の補正
   - 異常 10 行を `delete`
   - 銘柄 `86850` は分割による段差を `DAdjC`, `l1_DAdjC` の 10 倍補正で修正し、リターンを再計算
6. `-0.5 < return < 0.5` かつ `TradeDate < '2025-01-01'` で絞り、3 クラスの one-hot 列を付与
   - `negative`: `return < -0.006284`
   - `positive`: `return > 0.006289`
   - `neutral`: その間 (閾値は約 ±0.63%。3 クラスを均等にする狙いと推測)

列: `TradeDate, Code, return, Mkt, DAdjC, l1_DAdjC, l1_TradeDate, negative, positive, neutral`

備考: `r8_Oct5v.label` の作成は構文エラー (`create` の入れ子) で失敗し、最終的に存在しない。

### mapping_nodeID (ノード ID 対応表)
4 ノード表を UNION ALL し通し番号を付与したもの。
- 列: `TradeDate, Code, nodeType, nodeName, nodeID`
- `nodeType`: `stock` / `statement` / `future` / `mktIdx`
- `nodeName`: `<type>_<Code>_<YYYYMMDD>` (例 `stock_13010_20080507`)
- `nodeID`: `row_number() over()` で 1 から付番。最大 15,995,377 (総ノード数 約 1,600 万)
- 用途は PyG `HeteroData` のノード index と推測される

## 注意点
- `y_label` は `stocks` の全行を含まない (市場コード、リターン異常値、2025 年以降を除外)。結合すると欠ける行がある。
- `stocks` には `Mkt = '9999'` の行が多数ある。`y_label` は対象外の市場コードのため、これらにラベルは付かない。
- `mapping_nodeID` の `row_number() over()` は `order by` がないため、再実行で ID の並びが変わる可能性がある。安定させるなら `order by nodeType, TradeDate, Code` などを指定する。
