# derivative options 調査

## 1. 特徴量に対する処理

### 1.1 特徴量の特性

#### 1.1.1 `IR`

`IR` は 「理論価格計算用金利」であり，オプションの理論価格を計算する際に使用される（と言語構造上考えられる）．<br>
したがって，明確に（多重）共線性を示唆している上，欠損も多いため使用しない．<br>

#### 1.1.2 `SQD`

`SQD` は 「SQ日」であり，オプションの清算価格を計算する際に使用される．<br>
欠損が 100% であるため，使用しない．<br>

#### 1.1.3 `E-OHLC`・`M-OHLC`・`A-OHLC`

`E-OHLC`・`M-OHLC`・`A-OHLC` は，ナイト・セッション・前場・日中の価格データを表す．

`E-OHLC` は，欠損が 92% と多く，復元不可能であるケースが殆どであるため使用しない．<br>
`M-OHLC` は，欠損が 4% と比較的少ないが，前場データ単体が持つ情報量は少ないと仮定し，使用しない．<br>
`A-OHLC` は，欠損がほぼ 0% であるものの，今回は一旦使用しない方向性で行く（**今後利用の可能性あり**）．<br>

---

### 1.2 共線性に対する検討と処理

#### 1.2.1 Theo と Settle の相関係数を確認する

```sql
SELECT corr(Theo, Settle)
FROM drv_opt
WHERE Theo IS NOT NULL AND Settle IS NOT NULL
```

```text
＞ 0.9934793895174816
```

であることから，`Theo` と `Settle` はほぼ同じ値であることがわかる．<br>
実際には，`Theo` はオプションの理論価格であり，`Settle` はオプションの清算価格である．<br>
つまり，比として用いることで，オプションの価格乖離を表すことができる．<br>
ただ，`Theo` と `Settle` は，0 の値を取ることがあるため，そのまま比を取るとエラーとなる．<br>
そのため，1 を加算した比の自然対数を取ることで，オプションの価格乖離を近似する変数を新たに作成する．

```sql
log((Settle+1)/(Theo+1)) AS DeviationRate
```

---

#### 1.2.2 BaseVol と IV の相関係数を確認する

```sql
SELECT corr(BaseVol, IV)
FROM drv_opt
WHERE BaseVol IS NOT NULL AND IV IS NOT NULL
```

```text
＞ 0.47710796489884116
```

であることから，`BaseVol` と `IV` は比較的相関が強い関係であることがわかる．また，IV の欠損率は 6% であり，BaseVol は 22% の欠損率であることから，`BaseVol` 代替として使用する．<br>
埋められない箇所に対しては，欠損マスク（`NULL_TYPE_1`）・ゼロ埋めを行う．（ここは要検討）

```sql
CASE WHEN IV IS NULL THEN 0 ELSE IV END AS IV,
```

---

#### 1.2.3 Strike と UnderPx の相関係数を確認する

```sql
SELECT corr(Strike, UnderPx)
FROM drv_opt
WHERE Strike IS NOT NULL AND UnderPx IS NOT NULL
```

```text
＞ 0.9877169836053681
```

であることから，`Strike` と `UnderPx` はほぼ同じ値であることがわかる．また，`Strike` の欠損率は 0% であり，`UnderPx` 変数変換あるいは `UnderPx` 代替として使用できると仮定する．<br>
ただし，`Strike` と `UnderPx` は，比を取ることでオプションの `moneyness` を表すことができるため，比を取り変数を新たに作成する．`UnderPx` は `2016-07-19` 以前のデータが欠損している．これを補完する．

```sql
log(UnderPx / Strike) AS Moneyness
```

また，対数比を用いる根拠としては<br>

- なぜ対数収益率が使われるのか【<https://note.com/cyclicgroup12/n/n49892ea21fbe>】
- 相関をもつ二つの変数の比に対する解析【<https://www.jstage.jst.go.jp/article/jappstat/40/1/40_1_53/_pdf>】

とはいえ，**妥当かどうかは一旦置いておいて，実際に効果かどうかは実証してみないと分からない** ので，今後の課題とする．<br>

---

#### 1.2.4 VoVA と Vo の相関係数を確認する

```sql
SELECT corr(VoVA, Vo)
FROM drv_opt
WHERE VoVA IS NOT NULL AND Vo IS NOT NULL
```

```text
＞ 0.6853563325749554
```

であることから，`VoVA` と `Vo` は比較的相関が強い関係であることがわかる．また，`Vo` の欠損率は 0% であり，`VoVA` 代替として使用できると仮定する．

---

#### 1.2.5 LTD と SQD の相関係数を確認する

LTD は，オプションの満期日を表す．SQD は，オプションの清算価格を計算する際に使用される．<br>
LTD は SQD の翌日であるため，SQD を利用しない理由となる．<br>
さらに，残存日数として LTD から TradeDate を引くことで，SQD の代替として使用できると仮定する．

```sql
(CAST(LTD AS Date) + 1) - TradeDate AS SQRemainingDays,
```

ちなみに，SQRemainingDays は，LTD が欠損している場合がある<br>
そのため，欠損マスク（`NULL_TYPE_2`）・ゼロ埋めを行う．（ここは要検討）

```sql
CASE WHEN SQRemainingDays IS NULL THEN 0 ELSE SQRemainingDays END AS SQRemainingDays,
```

## 1.3 SQL による特徴量の変換

以下では，実際に DUCKDB を用いて，特徴量の変換を行う．<br>
特徴量の情報に関しては，本プロジェクトで使用する期間（2008/05/07 ~ 2026/04/17）に依存する．

```sql
CREATE OR REPLACE TABLE drv_opt_tmp AS
  WITH 
  base_opt AS(
    SELECT
      CAST(SUBSTRING(CAST(Date AS STRING), 1, 10) AS DATE) AS TradeDate,
      * EXCLUDE(
        Date, LTD, CM,
        EO, EH, EL, EC, -- 92% Nothing
        MO, MH, ML, MC, -- A-OHLC include them ( 4% Nothing)
        AO, AH, AL, AC, --   OHLC include them (~0% Nothing)
        SQD, -- 100% Nothing
        Theo, BaseVol, IR, CCMFlag,   -- 22% Nothing -- NULL-TYPE-1
        Settle, UnderPx, VoOA, Strike --  6% Nothing -- NULL-TYPE-2
      ),
      log((Settle+1)/(Theo+1)) AS DeviationRate,
      log(UnderPx / Strike) AS Moneyness,
      (CAST(LTD AS Date) + 1) - TradeDate AS SQRemainingDays,
      SUBSTR(CAST(CM AS VARCHAR), 1, 7) AS CM,
      CASE WHEN DeviationRate IS NULL THEN 0 ELSE 1 END AS NULL_TYPE_1,
      CASE WHEN Moneyness IS NULL THEN 0 ELSE 1 END AS NULL_TYPE_2
    FROM drv_opt
  ),
  filled AS(
    SELECT
    * EXCLUDE(DeviationRate, Moneyness, IV, SQRemainingDays),
    CASE WHEN DeviationRate IS NULL THEN 0 ELSE DeviationRate END AS DeviationRate,
    CASE WHEN Moneyness IS NULL THEN 0 ELSE Moneyness END AS Moneyness,
    CASE WHEN IV IS NULL THEN 0 ELSE IV END AS IV,
    CASE WHEN SQRemainingDays IS NULL THEN 0 ELSE SQRemainingDays END AS SQRemainingDays,
    FROM base_opt
  )
  SELECT
    TradeDate, Code, PCDiv EmMrgnTrgDiv, ProdCat, UndSSO, 
    O, H, L, C, Vo, Va, 
    OI, Moneyness, DeviationRate, SQRemainingDays, IV, CM,
    NULL_TYPE_1, NULL_TYPE_2
  FROM filled
```
