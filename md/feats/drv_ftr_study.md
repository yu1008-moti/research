# derivative futures  調査

j-quants から取得した先物データについて調査する．<br>
取得した期間は，2008/05/07 〜 2026/04/17 である．<br>

## 1. 特徴量に対する処理

主に，特徴量ごとの特性を理解し，具体的な根拠を示した上で操作を提案する．

### 1.1 特徴量の特性

特徴ごとに，様々な特性があるため，特徴量の特性を理解した上で，適切な処理を行う必要がある．

---

#### 1.1.1 Code

まずは，Code の各桁が何を表しているのかを表示する．

|①|②|③|④|⑤|
|:-:|:-:|:-:|:-:|:-:|
|特殊取引|プット／コール現先区分|限月|権利行使価格等|対象指数等|
|1（**確定**）|6（**確定**）|10年サイクルの１桁 + 限月の月２桁|00（**確定**）|2桁|

各先物の Code において ①・②・④ は全て同一であるため不要<br>
最終的に，「価格データ」という括りで一括して管理したいと考えている．<br>
そのため，Code に関して一貫したルールで管理する必要がある．<br>

ちなみに，「一貫したルール」について，具体的な内容は全く決まっていない．

---

#### 1.1.2 ProdCat

続いては，商品区分についてである．<br>
j-quants から取得した先物データにおいて，商品区分は以下の通りである．

|コード|2桁|出現数|概要|収録期間|使用可否|根拠|
|:-|:-:|:-:|:-|:-|:-:|:-|
|JGBLF|01|13191|長期国債先物|2008/5/7〜|||
|TOPIXF|05|23753|TOPIX先物|2008/5/7〜|||
|TOPIXMF|06|13107|ミニTOPIX先物|2008/6/16〜|||
|MOTF|11|11935|マザーズ先物|2016/7/19〜|||
|NKVIF|15|27712|日経平均VI先物|2012/2/27〜|||
|NKYDF|17|31781|日経平均・配当指数先物|2010/7/26〜|||
|NK225F|18|58321|日経225先物|2008/5/7〜|||
|NK225MF|19|54304|日経225mini先物|2008/5/7〜|||
|JN400F|22|13945|JPX日経インデックス400先物|2014/11/25〜|||
|NK225MCF|23|2832|日経225マイクロ先物|2023/5/29〜|||
|REITF|69|13107|東証REIT指数先物|2008/6/16〜|||
|DJIAF|73|13612|NYダウ先物|2012/5/28〜|||
|TOA3MF|91|14160|TONA3ヶ月金利先物|2023/5/29〜|||
|CNHJPYF|C1|25|中国オフショア人民元/日本円先物|2026/4/13〜|△|データ数が極小|
|EURJPYF|C2|25|ユーロ/日本円先物|2026/4/13〜|△|データ数が極小|
|USDJPYF|C3|25|米ドル/日本円先物|2026/4/13〜|△|データ数が極小|

ちなみに，株価マスタに新たに「ProdCat」が追加されたらしい．<br>
今後，株価マスタの DB を新たに再構築し，ProdCat を利用する．<br>

### 1.2 特徴量の操作

以下は，実際に先物データに対して行う具体的な特徴量の操作である．<br>
若干複雑かつ冗長な操作が必要である．（主に，`SQRemainingDays` に対して）

SQL の言語スキルが足りない点については，今後の課題として改善していく必要がある．<br>

```sql
-- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
-- First, create a temporary table to fill the missing values of DeviationRate and SQRemainingDays
-- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
CREATE OR REPLACE TABLE drv_ftr_tmp AS
  WITH
  base_ftr AS (
    SELECT
      CAST(SUBSTRING(CAST(Date AS STRING), 1, 10) AS DATE) AS TradeDate,
      * EXCLUDE(
        MO, MH, ML, MC, 
        AO, AH, AL, AC,
        EO, EH, EL, EC,
        VoOA, Settle,
        SQD, LTD, CM,
        CCMFlag
      ),
      log((Settle+1)/(C+1)) AS DeviationRate,
      (CAST(LTD AS Date) + 1) - TradeDate AS SQRemainingDays,
      SUBSTR(CAST(CM AS VARCHAR), 1, 7) AS CM,
      CASE WHEN DeviationRate IS NULL THEN 0 ELSE 1 END AS NULL_TYPE_1, -- missing-value mask
    FROM drv_ftr
  ),

-- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
-- Second, fill the missing values of SQRemainingDays
-- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --

  
  base_v1 AS(
    SELECT 
      TradeDate, Code, CM, SQRemainingDays, EmMrgnTrgDiv,
      CASE WHEN 1=1 THEN NULL END AS SQRemainingDays_NULLS,
      row_number() OVER w AS rn,
      COALESCE(
        LAG(TradeDate, -1) OVER w,
        TradeDate
      ) AS Lag_TradeDate,
    FROM base_ftr
    -- WHERE Code = '163090001' AND CM = '2008-09' -- for test
    WINDOW w AS(
      PARTITION BY Code, CM
      ORDER BY TradeDate
    )
  ),
  
  base_v2 AS(
    SELECT 
      * EXCLUDE(SQRemainingDays_NULLS),
      CASE WHEN
        rn = MAX(rn) OVER w THEN true ELSE false
      END AS isMax,
      CASE WHEN 
        isMax = true AND SQRemainingDays_NULLS IS NULL THEN 1
        ELSE Lag_TradeDate - TradeDate
      END AS SQRemainingDays_NULLS
    FROM base_v1
    WINDOW w AS(
      PARTITION BY Code, CM
    )
    ORDER BY TradeDate DESC
  ),
  
  base_v3 AS(
    SELECT
      * EXCLUDE(rn, isMax, SQRemainingDays_NULLS, Lag_TradeDate, SQRemainingDays),
      SUM(SQRemainingDays_NULLS) OVER w AS SQRemainingDays
    FROM base_v2
    WINDOW w AS(
      PARTITION BY Code, CM
      ORDER BY TradeDate DESC
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )
    ORDER BY TradeDate
  ),

-- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
-- Third, fill the missing values of DeviationRate
-- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
  
  filled AS(
    SELECT
      * EXCLUDE(DeviationRate,SQRemainingDays),
      CASE WHEN DeviationRate IS NULL THEN 0 ELSE DeviationRate END AS DeviationRate,
      b.SQRemainingDays
    FROM base_ftr a
    JOIN base_v3  b
    ON 
      a.TradeDate = b.TradeDate AND 
      a.Code = b.Code AND
      a.EmMrgnTrgDiv = b.EmMrgnTrgDiv AND
      a.CM = b.CM
  )
  
  SELECT
    TradeDate, Code, EmMrgnTrgDiv, 
    O, H, L, C, Vo, Va, 
    OI, DeviationRate, SQRemainingDays, CM,
    NULL_TYPE_1, 
  FROM filled
```
