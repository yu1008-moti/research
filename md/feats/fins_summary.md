# 財務情報の調査

fins_summary データにおける特徴・処理をまとめて掲載する

## データの概要

使用可否の基準

- 🟢：使用推奨
- 🔵：使用可能
- 🟡：要データ処理
- 🔴：使用非推奨

### 使用する開示書類種別に整理

`*_Consolidated_*`は連結決算、`*_NonConsolidated_*`は非連結決算を表す。

|書類種別|概要|出現回数|使用可否|
|-|-|-|:-:|
|1QFinancialStatements_Consolidated_JP|第1四半期決算短信（連結・日本基準）|55639||
|1QFinancialStatements_NonConsolidated_JP|第1四半期決算短信（非連結・日本基準）|9708||
|2QFinancialStatements_Consolidated_JP|第2四半期決算短信（連結・日本基準）|54974||
|2QFinancialStatements_NonConsolidated_JP|第2四半期決算短信（非連結・日本基準）|9487||
|3QFinancialStatements_Consolidated_JP|第3四半期決算短信（連結・日本基準）|54613||
|3QFinancialStatements_NonConsolidated_JP|第3四半期決算短信（非連結・日本基準）|9427||
|FYFinancialStatements_Consolidated_JP|決算短信（連結・日本基準）|56891||
|FYFinancialStatements_NonConsolidated_JP|決算短信（非連結・日本基準）|9828||
|1QFinancialStatements_Consolidated_IFRS|第1四半期決算短信（連結・ＩＦＲＳ）|2371||
|2QFinancialStatements_Consolidated_IFRS|第2四半期決算短信（連結・ＩＦＲＳ）|2325||
|3QFinancialStatements_Consolidated_IFRS|第3四半期決算短信（連結・ＩＦＲＳ）|2340||
|FYFinancialStatements_Consolidated_IFRS|決算短信（連結・ＩＦＲＳ）|2370||
|FYFinancialStatements_Consolidated_REIT|決算短信（REIT）|1432||
|DividendForecastRevision|配当予想の修正|50||
|EarnForecastRevision|業績予想の修正|71430||
|REITDividendForecastRevision|分配予想の修正|50||
|REITEarnForecastRevision|利益予想の修正|809||

<details>
<summary>開示書類種別の詳細</summary>

使用しないものも含めて，全て表示している．

|書類種別|概要|出現回数|使用可否|
|-|-|-|:-:|
|FYFinancialStatements_Consolidated_JP|決算短信（連結・日本基準）|56891||
|FYFinancialStatements_Consolidated_US|決算短信（連結・米国基準）|387||
|FYFinancialStatements_NonConsolidated_JP|決算短信（非連結・日本基準）|9828||
|1QFinancialStatements_Consolidated_JP|第1四半期決算短信（連結・日本基準）|55639||
|1QFinancialStatements_Consolidated_US|第1四半期決算短信（連結・米国基準）|383||
|1QFinancialStatements_NonConsolidated_JP|第1四半期決算短信（非連結・日本基準）|9708||
|2QFinancialStatements_Consolidated_JP|第2四半期決算短信（連結・日本基準）|54974||
|2QFinancialStatements_Consolidated_US|第2四半期決算短信（連結・米国基準）|376||
|2QFinancialStatements_NonConsolidated_JP|第2四半期決算短信（非連結・日本基準）|9487||
|3QFinancialStatements_Consolidated_JP|第3四半期決算短信（連結・日本基準）|54613||
|3QFinancialStatements_Consolidated_US|第3四半期決算短信（連結・米国基準）|385||
|3QFinancialStatements_NonConsolidated_JP|第3四半期決算短信（非連結・日本基準）|9427||
|OtherPeriodFinancialStatements_Consolidated_JP|その他四半期決算短信（連結・日本基準）|50|🔴|
|OtherPeriodFinancialStatements_Consolidated_US|その他四半期決算短信（連結・米国基準）|0|🔴|
|OtherPeriodFinancialStatements_NonConsolidated_JP|その他四半期決算短信（非連結・日本基準）|10|🔴|
|FYFinancialStatements_Consolidated_JMIS|決算短信（連結・ＪＭＩＳ）|0|🔴|
|1QFinancialStatements_Consolidated_JMIS|第1四半期決算短信（連結・ＪＭＩＳ）|0|🔴|
|2QFinancialStatements_Consolidated_JMIS|第2四半期決算短信（連結・ＪＭＩＳ）|0|🔴|
|3QFinancialStatements_Consolidated_JMIS|第3四半期決算短信（連結・ＪＭＩＳ）|0|🔴|
|OtherPeriodFinancialStatements_Consolidated_JMIS|その他四半期決算短信（連結・ＪＭＩＳ）|0|🔴|
|FYFinancialStatements_NonConsolidated_IFRS|決算短信（非連結・ＩＦＲＳ）|12|🔴|
|1QFinancialStatements_NonConsolidated_IFRS|第1四半期決算短信（非連結・ＩＦＲＳ）|12|🔴|
|2QFinancialStatements_NonConsolidated_IFRS|第2四半期決算短信（非連結・ＩＦＲＳ）|13|🔴|
|3QFinancialStatements_NonConsolidated_IFRS|第3四半期決算短信（非連結・ＩＦＲＳ）|14|🔴|
|OtherPeriodFinancialStatements_NonConsolidated_IFRS|その他四半期決算短信（非連結・ＩＦＲＳ）|0|🔴|
|FYFinancialStatements_Consolidated_IFRS|決算短信（連結・ＩＦＲＳ）|2370||
|1QFinancialStatements_Consolidated_IFRS|第1四半期決算短信（連結・ＩＦＲＳ）|2371||
|2QFinancialStatements_Consolidated_IFRS|第2四半期決算短信（連結・ＩＦＲＳ）|2325||
|3QFinancialStatements_Consolidated_IFRS|第3四半期決算短信（連結・ＩＦＲＳ）|2340||
|OtherPeriodFinancialStatements_Consolidated_IFRS|その他四半期決算短信（連結・ＩＦＲＳ）|1|🔴|
|FYFinancialStatements_NonConsolidated_Foreign|決算短信（非連結・外国株）|0|🔴|
|1QFinancialStatements_NonConsolidated_Foreign|第1四半期決算短信（非連結・外国株）|0|🔴|
|2QFinancialStatements_NonConsolidated_Foreign|第2四半期決算短信（非連結・外国株）|1|🔴|
|3QFinancialStatements_NonConsolidated_Foreign|第3四半期決算短信（非連結・外国株）|0|🔴|
|OtherPeriodFinancialStatements_NonConsolidated_Foreign|その他四半期決算短信（非連結・外国株）|0|🔴|
|FYFinancialStatements_Consolidated_Foreign|決算短信（連結・外国株）|6|🔴|
|1QFinancialStatements_Consolidated_Foreign|第1四半期決算短信（連結・外国株）|7|🔴|
|2QFinancialStatements_Consolidated_Foreign|第2四半期決算短信（連結・外国株）|6|🔴|
|3QFinancialStatements_Consolidated_Foreign|第3四半期決算短信（連結・外国株）|6|🔴|
|OtherPeriodFinancialStatements_Consolidated_Foreign|その他四半期決算短信（連結・外国株）|0|🔴|
|FYFinancialStatements_Consolidated_REIT|決算短信（REIT）|1432||
|DividendForecastRevision|配当予想の修正|50|🔴|
|EarnForecastRevision|業績予想の修正|71430||
|REITDividendForecastRevision|分配予想の修正|50|🔴|
|REITEarnForecastRevision|利益予想の修正|809||

</details>

---

### 特徴量ごとに整理

各特徴量において，特に癖が見られるデータ区分であるため，丁寧に整理したいと考えている．

#### ✔ Div系における特徴量の整理

関係性としては，

`Div1Q` + `Div2Q` + `Div3Q` + `DivFY` = `DivAnn`<br>
ただし，`Div1Q` ～ `DivFY` は独立している．<br>

|特徴量|概要|
|-|-|
|Div1Q|一株あたり配当実績_第1四半期末|
|Div2Q|一株あたり配当実績_第2四半期末|
|Div3Q|一株あたり配当実績_第3四半期末|
|DivFY|一株あたり配当実績_期末|
|DivAnn|一株あたり配当実績_合計|

ここでは，以下のように運用しようと考えている．<br>

```sql
-- NO CONTENTS
```

また，DivUnitに対して，以下のSQLを発行すると次の変数が固定される．

- DocType：FYFinancialStatements_Consolidated_REIT（決算短信（REIT））
- CurPerType：FY（期末）

```sql
SELECT *
FROM fin_sum
WHERE DivUnit IS NOT NULL
```

ちなみに，欠損率については，以下の様な結果となった．<br>
以下の SQL によって得られるデータから集計している

```sql
SELECT 
  DiscDate,
  DocType, CurPerType, 
  COLUMNS(
    c ->　
      c LIKE('%Div%')
  )
FROM fin_sum
WHERE
  Div1Q IS NOT NULL OR 
  Div2Q IS NOT NULL OR 
  Div3Q IS NOT NULL OR 
  DivFY IS NOT NULL
```

|n 期配当|欠損率|使用可否|n 期配当予想|欠損率|使用可否|翌年 n 期配当予想|欠損率|使用可否|
|-|-|:-:|-|-|:-:|-|-|:-:|
|Div1Q|99%|🔴|FDiv1Q|>99%|🔴|NxFDiv1Q|>99%|🔴|
|Div2Q|3%|🟢|FDiv2Q|>99%|🔴|NxFDiv2Q|71%|🟡|
|Div3Q|>99%|🔴|FDiv3Q|>99%|🔴|NxFDiv3Q|>99%|🔴|
|DivFY|65%|🟡|FDivFY|40%|🟡|NxFDivFY|69%|🟡|
|DivAnn|65%|🟡|FDivAnn|41%|🟡|NxFDivAnn|69%|🟡|
|DivUnit|100%|🔴|FDivUnit|100%|🔴|NxFDivUnit|100%|🔴|
|DivTotalAnn|70%|🟡|FDivTotalAnn|100%|🔴|-|-|-|

Div系について，以下の様な組み合わせが考えられる．

||Div1Q|Div2Q|Div3Q|DivFY|FDiv1Q|FDiv2Q|FDiv3Q|FDivFY|NxFDiv1Q|NxFDiv2Q|NxFDiv3Q|NxFDivFY|
|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
|1Q||||||150.0||150.0|||||
|2Q||150.0||||||150.0|||||
|3Q||150.0||||||150.0|||||
|FY||150.0||150.0||||||150.0||150.0|
|1Q||||||150.0||150.0|||||
|2Q||100.0||||||100.0|||||
|3Q||100.0||||||100.0|||||
|FY||100.0||100.0||||||100.0||100.0|

のとき，次のように変換する．

---

#### ✔ yy
