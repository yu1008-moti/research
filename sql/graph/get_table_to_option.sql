-- オプション日次バー(imp.drv_opt_tmp)を週次に集約する。
-- UndSSO は原資産の個別株コード（4桁）。株価指数・債券オプション(NK225E/TOPIXE/JGBLFE)は
-- UndSSO='-' となるため NULL に変換し、株式コードが存在する銘柄オプション(EQOP)のみ
-- eqt_main.Code (5桁, 末尾0埋め) と同じ表記に揃える。
WITH
day2week AS (
  SELECT
    yearweek(TradeDate) AS week_id,
    first(Code) AS Code,
    case when cast(substring(first(Code), 2, 1) as integer) % 2 = 0 then 1 else 0 end as isPUT,
    case when cast(substring(first(Code), 2, 1) as integer) < 3     then 1 else 0 end as isFUTURE,
    last(ProdCat) AS ProdCat,
    CASE WHEN last(UndSSO) = '-' THEN '00000' ELSE last(UndSSO) || '0' END AS UndSSO,
    last(CM) AS CM,
    SUBSTRING(last(CM), 1, 4) AS CM_year,
    SUBSTRING(last(CM), 6, 2) AS CM_month,
    -- log OHLCV（株式側の AdjO/AdjH/AdjL/AdjC/AdjVo 命名規則に合わせる）
    log(first(O+1)) AS AdjO,
    log(max(H+1)) AS AdjH,
    log(min(L+1)) AS AdjL,
    log(last(C+1)) AS AdjC,
    log(last(Vo+1)) AS AdjVo,
    log(last(Va+1)) AS AdjVa,
    log(last(OI+1)) AS AdjOI,
    -- その他特徴量
    last(Moneyness) AS Moneyness,
    last(DeviationRate) AS DeviationRate,
    last(SQRemainingDays) AS SQRemainingDays,
    last(IV) AS IV,
    max(NULL_TYPE_1) AS NULL_TYPE_1,
    max(NULL_TYPE_2) AS NULL_TYPE_2
  FROM imp.drv_opt_tmp
  GROUP BY yearweek(TradeDate), Code
)

SELECT 
  week_id,
  Code,
  ProdCat,
  UndSSO,
  isPUT,
  isFUTURE,
  CM_year,
  CM_month,
  AdjO,
  AdjH,
  AdjL,
  AdjC,
  AdjVo,
  AdjVa,
  AdjOI,
  Moneyness,
  DeviationRate,
  SQRemainingDays,
  IV,
  NULL_TYPE_1,
  NULL_TYPE_2
FROM day2week
--WHERE week_id > 200819 AND week_id < 202616
where isFUTURE = 1
ORDER BY week_id, Code
