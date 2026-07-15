# 投資部門別 調査

## 特徴量の整理

### StDate と EnDate の幅

「`StDate` と `EnDate` の幅」は，`StDate` から `EnDate` までの期間を表す．<br>

|Range|Count|
|-|:-:|
|0|23|
|1|63|
|2|61|
|3|492|
|4|3063|

公式によると，月間だとか年間だとか，いろいろ期間が記録されているとのことらしいが，<br>
あくまで最大４日間，つまり １週間の期間のみ記録されている．<br>

```sql
SELECT DISTINCT EnDate - StDate AS DayRange, COUNT(*) AS Count
FROM (
  SELECT
    CAST(StDate  AS DATE) AS StDate,
    CAST(EnDate  AS DATE) AS EnDate
  FROM eqt_inv
)
GROUP BY EnDate - StDate
ORDER BY DayRange
```

---

### Section 名称と Mkt コードの対応表

`東証及び名証` の `Section` は，`Mkt` コードに対応しない．<br>
他の `Section` は，`Mkt` コードに対応できる．

|Section|count|Section 名称|Mkt|Mkt 名称|
|-|:-:|-|-|-|
|TSE1st|743|市場一部|0101|東証一部|
|TSE2nd|743|市場二部|0102|東証二部|
|TSEMothers|175|マザーズ|0104|マザーズ|
|TSEJASDAQ|454|ジャスダック|0106<br>0107|JASDAQ スタンダード<br>JASDAQ グロース|
|TSEPrime|212|プライム|0111|プライム|
|TSEStandard|210|スタンダード|0112|スタンダード|
|TSEGrowth|210|グロース|0107|グロース|
|TokyoNagoya|955|東証および名証|-|-|

明証データは必要ないため使用せず，残りの `Section` のみを使用する．<br>
ちなみに以下のコードで確認できる

```sql
SELECT DISTINCT(Section), COUNT(*)
FROM eqt_inv
GROUP BY Section
```

`Section` と `Mkt` を対応付けるために，‘`Section_id` を作成する．<br>

|Section|Section_id|
|-|:-:|
|TSE1st|1|
|TSE2nd|2|
|TSEMothers|3|
|TSEJASDAQ|4|
|TSEPrime|5|
|TSEStandard|6|
|TSEGrowth|7|
|その他|0|

---

### 公開日の曜日整理

全ての `PubDate` は平日に公開されており，その中でも明らかに木曜日に偏っている．

|dayname(PubDate)|count|
|-|:-:|
|Monday|63|
|Tuesday|96|
|Friday|651|
|Wednesday|35|
|Thursday|2857|

その日の情報として用いることができると判断できる．<br>
ちなみに以下のコードで確認できる

```sql
SELECT DISTINCT dayname(PubDate), COUNT(*)
FROM eqt_inv
GROUP BY dayname(PubDate)
```

---

### 特徴量の詳細（一部非表示）

#### 主キー項目

|変数名|説明|処理|
|-|-|:-|
|PubDate|公表日|-|
|StDate|開始日|-|
|EnDate|終了日|-|
|Section|市場名|`Section_id` へ写像|

#### 主要項目 - 自己計

|変数名|説明|処理|
|-|-|:-|
|PropSell|自己計_売|$\text{PropBSRatio} = \ln\left(\dfrac{\text{PropSell} +1}{\text{PropBuy} +1}\right)$|
|PropBuy|自己計_買|$\text{PropBSRatio}$ に組込み|
|PropTot|自己計_合計|$\text{TotRatio}$ に組込み|

#### 主要項目 - 委託計

|変数名|説明|処理|
|-|-|:-|
|BrkSell|委託計_売|$\text{BrkBSRatio} = \ln\left(\dfrac{\text{BrkSell} +1}{\text{BrkBuy} +1}\right)$|
|BrkBuy|委託計_買|$\text{BrkBSRatio}$ に組込み|
|BrkTot|委託計_合計|$\text{TotRatio}$ に組込み|

#### 主要項目 - 総計

|変数名|説明|処理|
|-|-|:-|
|TotSell|総計_売|$\text{TotBSRatio} = \ln\left(\dfrac{\text{TotSell} +1}{\text{TotBuy} +1}\right)$|
|TotBuy|総計_買|$\text{TotBSRatio}$ に組込み|
|TotTot|総計_合計|$\text{TotRatio} = \ln\left(\dfrac{\text{PropTot+1}}{\text{BrkTot+1}}\right)$|

#### 委託内訳 - 法人（新設）

|変数名|説明|処理|
|-|-|:-|
|InsSell|法人_売|$\text{InsSell} = \text{InvSell}+\text{BusCoSell} + \text{OthCoSell} + \text{FinInsSell}$<br>$\text{InsBSRatio} = \ln\left(\dfrac{\text{InsSell} +1}{\text{InsBuy} +1}\right)$|
|InsBuy|法人_買|$\text{InsBuy} = \text{InvBuy}+\text{BusCoBuy} + \text{OthCoBuy} + \text{FinInsBuy}$<br>$\text{InsBSRatio}$ に組込み|
|InsTot|法人_合計|$\text{InsTot} = \text{InvTot}+\text{BusCoTot} + \text{OthCoTot} + \text{FinInsTot}$<br>$\text{InsWeight} = \ln\left(\dfrac{\text{InsTot+1}}{\text{BrkTot+1}}\right)$|

#### 委託内訳 - 個人

|変数名|説明|処理|
|-|-|:-|
|IndSell|個人_売|$\text{IndBSRatio} = \ln\left(\dfrac{\text{IndSell} +1}{\text{IndBuy} +1}\right)$|
|IndBuy|個人_買|$\text{IndBSRatio}$ に組込み|
|IndTot|個人_合計|$\text{IndWeight} = \ln\left(\dfrac{\text{IndTot+1}}{\text{BrkTot+1}}\right)$|

#### 委託内訳 - 海外投資家

|変数名|説明|処理|
|-|-|-|
|FrgnSell|海外投資家_売|$\text{FrgnBSRatio} = \ln\left(\dfrac{\text{FrgnSell} +1}{\text{FrgnBuy} +1}\right)$|
|FrgnBuy|海外投資家_買|$\text{FrgnBSRatio}$ に組込み|
|FrgnTot|海外投資家_合計|$\text{FrgnWeight} = \ln\left(\dfrac{\text{FrgnTot+1}}{\text{BrkTot+1}}\right)$|

#### 委託内訳 - 証券会社

|変数名|説明|処理|
|-|-|:-|
|SecCoSell|証券会社_売|$\text{SecCoBSRatio} = \ln\left(\dfrac{\text{SecCoSell} +1}{\text{SecCoBuy} +1}\right)$|
|SecCoBuy|証券会社_買|$\text{SecCoBSRatio}$ に組込み|
|SecCoTot|証券会社_合計|$\text{SecCoWeight} = \ln\left(\dfrac{\text{SecCoTot+1}}{\text{BrkTot+1}}\right)$|

#### 法人内訳 - 投資信託

|変数名|説明|処理|
|-|-|:-|
|InvTrSell|投資信託_売|$\text{InvTrBSRatio} = \ln\left(\dfrac{\text{InvTrSell} +1}{\text{InvTrBuy} +1}\right)$|
|InvTrBuy|投資信託_買|$\text{InvTrBSRatio}$ に組込み|
|InvTrTot|投資信託_合計|$\text{InvTrWeight} = \ln\left(\dfrac{\text{InvTrTot+1}}{\text{BrkTot+1}}\right)$|

#### 法人内訳 - 事業法人

|変数名|説明|処理|
|-|-|:-|
|BusCoSell|事業法人_売|$\text{BusCoBSRatio} = \ln\left(\dfrac{\text{BusCoSell} +1}{\text{BusCoBuy} +1}\right)$|
|BusCoBuy|事業法人_買|$\text{BusCoBSRatio}$ に組込み|
|BusCoTot|事業法人_合計|$\text{BusCoWeight} = \ln\left(\dfrac{\text{BusCoTot+1}}{\text{BrkTot+1}}\right)$|

#### 法人内訳 - その他法人

|変数名|説明|処理|
|-|-|:-|
|OthCoSell|その他法人_売|$\text{OthCoBSRatio} = \ln\left(\dfrac{\text{OthCoSell} +1}{\text{OthCoBuy} +1}\right)$|
|OthCoBuy|その他法人_買|$\text{OthCoBSRatio}$ に組込み|
|OthCoTot|その他法人_合計|$\text{OthCoWeight} = \ln\left(\dfrac{\text{OthCoTot+1}}{\text{BrkTot+1}}\right)$|

#### 法人内訳 - 金融機関（新設）

|変数名|説明|処理|
|-|-|:-|
|FinInsSell|法人_売|$\text{FinInsSell} = \text{InsCoSell}+\text{BankSell} + \text{TrstBnkSell} + \text{OthFinSell}$<br>$\text{FinInsBSRatio} = \ln\left(\dfrac{\text{FinInsSell} +1}{\text{FinInsBuy} +1}\right)$|
|FinInsBuy|法人_買|$\text{FinInsBuy} = \text{InsCoBuy}+\text{BankBuy} + \text{TrstBnkBuy} + \text{OthFinBuy}$<br>$\text{FinInsBSRatio}$ に組込み|
|FinInsTot|法人_合計|$\text{FinInsTot} = \text{InsCoTot}+\text{BankTot} + \text{TrstBnkTot} + \text{OthFinTot}$<br>$\text{FinInsWeight} = \ln\left(\dfrac{\text{FinInsTot+1}}{\text{BrkTot+1}}\right)$|

#### 金融機関 - 生保・損保

|変数名|説明|処理|
|-|-|:-|
|InsCoSell|生保・損保_売|$\text{InsCoBSRatio} = \ln\left(\dfrac{\text{InsCoSell} +1}{\text{InsCoBuy} +1}\right)$|
|InsCoBuy|生保・損保_買|$\text{InsCoBSRatio}$ に組込み|
|InsCoTot|生保・損保_合計|$\text{InsCoWeight} = \ln\left(\dfrac{\text{InsCoTot+1}}{\text{BrkTot+1}}\right)$|

#### 金融機関 - 都銀・地銀等

|変数名|説明|処理|
|-|-|:-|
|BankSell|都銀・地銀等_売|$\text{BankBSRatio} = \ln\left(\dfrac{\text{BankSell} +1}{\text{BankBuy} +1}\right)$|
|BankBuy|都銀・地銀等_買|$\text{BankBSRatio}$ に組込み|
|BankTot|都銀・地銀等_合計|$\text{BankWeight} = \ln\left(\dfrac{\text{BankTot+1}}{\text{BrkTot+1}}\right)$|

#### 金融機関 - 信託銀行

|変数名|説明|処理|
|-|-|:-|
|TrstBnkSell|信託銀行_売|$\text{TrstBnkBSRatio} = \ln\left(\dfrac{\text{TrstBnkSell} +1}{\text{TrstBnkBuy} +1}\right)$|
|TrstBnkBuy|信託銀行_買|$\text{TrstBnkBSRatio}$ に組込み|
|TrstBnkTot|信託銀行_合計|$\text{TrstBnkWeight} = \ln\left(\dfrac{\text{TrstBnkTot+1}}{\text{BrkTot+1}}\right)$|

#### 金融機関 - その他金融機関

|変数名|説明|処理|
|-|-|:-|
|OthFinSell|その他金融機関_売|$\text{OthFinBSRatio} = \ln\left(\dfrac{\text{OthFinSell} +1}{\text{OthFinBuy} +1}\right)$|
|OthFinBuy|その他金融機関_買|$\text{OthFinBSRatio}$ に組込み|
|OthFinTot|その他金融機関_合計|$\text{OthFinWeight} = \ln\left(\dfrac{\text{OthFinTot+1}}{\text{BrkTot+1}}\right)$|

---

### SQLによる特徴量の整理

```sql
WITH spare_feature AS(
  SELECT
    PubDate, Section,
  
    InsCoSell  + BankSell  + TrstBnkSell  + OthFinSell AS FinInsSell,
    InsCoBuy   + BankBuy   + TrstBnkBuy   + OthFinBuy  AS FinInsBuy,
    InsCoTot   + BankTot   + TrstBnkTot   + OthFinTot  AS FinInsTot,
    
    InvTrSell  + BusCoSell + OthCoSell    + FinInsSell AS InsSell,
    InvTrBuy   + BusCoBuy  + OthCoBuy     + FinInsBuy  AS InsBuy,
    InvTrTot   + BusCoTot  + OthCoTot     + FinInsTot  AS InsTot
  FROM eqt_inv
  WHERE
    PubDate >= '2008-05-07 00:00:00' AND
    Section != 'TokyoNagoya'
)
  
SELECT 
  CAST(s.PubDate AS DATE) AS PubDate,
  CASE
    WHEN s.Section = 'TSE1st'      THEN 1 
    WHEN s.Section = 'TSE2nd'      THEN 2
    WHEN s.Section = 'TSEMothers'  THEN 3 
    WHEN s.Section = 'TSEJASDAQ'   THEN 4
    WHEN s.Section = 'TSEPrime'    THEN 5 
    WHEN s.Section = 'TSEStandard' THEN 6 
    WHEN s.Section = 'TSEGrowth'   THEN 7
  ELSE 0
  END AS Section_id,
  
  log((o.PropSell   +1) /    (o.PropBuy+1)) AS PropBSRatio,
  log((o.BrkSell    +1) /    (o.BrkBuy +1)) AS BrkBSRatio,
  log((o.TotSell    +1) /    (o.TotBuy +1)) AS TotBSRatio,
  log((o.PropTot    +1) /    (o.BrkTot +1)) AS TotRatio,
  
  log((s.InsSell    +1) /    (s.InsBuy +1)) AS InsBSRatio,
  log( s.InsTot     +1  /     o.BrkTot +1 ) AS InsWeight,
  
  log((o.IndSell    +1) /    (o.IndBuy +1)) AS IndBSRatio,
  log( o.IndTot     +1  /     o.BrkTot +1 ) AS IndWeight,
  
  log((o.FrgnSell   +1) /    (o.FrgnBuy+1)) AS FrgnBSRatio,
  log( o.FrgnTot    +1  /     o.BrkTot +1 ) AS FrgnWeight,
  
  log((o.SecCoSell  +1) /  (o.SecCoBuy +1)) AS SecCoBSRatio,
  log( o.SecCoTot   +1  /   o.BrkTot   +1 ) AS SecCoWeight,
  
  log((o.InvTrSell  +1) /  (o.InvTrBuy +1)) AS InvTrBSRatio,
  log( o.InvTrTot   +1  /   o.BrkTot   +1 ) AS InvTrWeight,
  
  log((o.BusCoSell  +1) /  (o.BusCoBuy +1)) AS BusCoBSRatio,
  log( o.BusCoTot   +1  /   o.BrkTot   +1 ) AS BusCoWeight,
  
  log((o.OthCoSell  +1) /  (o.BusCoBuy +1)) AS OthCoBSRatio,
  log( o.OthCoTot   +1  /   o.BrkTot   +1 ) AS OthCoWeight,
  
  log((s.FinInsSell +1) / (s.FinInsBuy +1)) AS FinInsBSRatio,
  log( s.FinInsTot  +1  /  o.BrkTot    +1 ) AS FinInsWeight,
  
  log((o.InsCoSell  +1) /  (o.InsCoBuy +1)) AS InsCoBSRatio,
  log( o.InsCoTot   +1  /   o.BrkTot   +1 ) AS InsCoWeight,
  
  log((o.BankSell   +1) /   (o.BankBuy +1)) AS BankBSRatio,
  log( o.BankTot    +1  /    o.BrkTot  +1 ) AS BankWeight,
  
  log((o.TrstBnkSell+1) / (o.TrstBnkBuy+1)) AS TrstBnkBSRatio,
  log( o.TrstBnkTot +1  /  o.BrkTot    +1 ) AS TrstBnkWeight,

  -- To avoid multi-coliner
  -- log(o.OthFinSell+1)/(o.OthFinBuy+1) AS OthFinBSRatio,
  -- o.OthFinTot/o.BrkTot AS OthFinWeight
  
FROM eqt_inv o
JOIN spare_feature s
ON 
  o.PubDate = s.PubDate AND 
  o.Section = s.Section
```

### 参考資料

- <https://www.jpx.co.jp/markets/statistics-equities/investor-type/tvdivq0000001sgp-att/stock_20241105.pdf>
