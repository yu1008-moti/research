-- オプション日次バー(imp.drv_opt_tmp)を週次に集約する。
-- UndSSO は原資産の個別株コード（4桁）。株価指数・債券オプション(NK225E/TOPIXE/JGBLFE)は
-- UndSSO='-' となるため NULL に変換し、株式コードが存在する銘柄オプション(EQOP)のみ
-- eqt_main.Code (5桁, 末尾0埋め) と同じ表記に揃える。
WITH
day2week AS (
  SELECT
    yearweek(TradeDate) AS week_id,
    first(Code) AS Code,
    last(ProdCat) AS ProdCat,
    CASE WHEN last(UndSSO) = '-' THEN NULL ELSE last(UndSSO) || '0' END AS UndSSO,
    last(CM) AS CM,
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

SELECT *
FROM day2week
WHERE week_id > $START_WEEK_ID AND week_id < $END_WEEK_ID
ORDER BY week_id, Code
