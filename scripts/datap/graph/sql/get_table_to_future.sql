-- 先物日次バー(imp.drv_ftr)を週次に集約する。
-- imp.drv_ftr には ProdCat（NK225F/TOPIXF等の商品区分）が残っていないため、
-- raw.drv_ftr から Code -> ProdCat の対応（銘柄コードごとに商品区分は不変）を引く。
WITH
code_prodcat AS (
  SELECT Code, first(ProdCat) AS ProdCat
  FROM raw.drv_ftr
  GROUP BY Code
),
day2week AS (
  SELECT
    yearweek(f.TradeDate) AS week_id,
    first(f.Code) AS Code,
    last(cp.ProdCat) AS ProdCat,
    last(f.CM) AS CM,
    -- log OHLCV（株式側の AdjO/AdjH/AdjL/AdjC/AdjVo 命名規則に合わせる）
    log(first(f.O+1)) AS AdjO,
    log(max(f.H+1)) AS AdjH,
    log(min(f.L+1)) AS AdjL,
    log(last(f.C+1)) AS AdjC,
    log(last(f.Vo+1)) AS AdjVo,
    log(last(f.Va+1)) AS AdjVa,
    log(last(f.OI+1)) AS AdjOI,
    -- その他特徴量
    last(f.DeviationRate) AS DeviationRate,
    last(f.SQRemainingDays) AS SQRemainingDays,
    max(f.NULL_TYPE_1) AS NULL_TYPE_1
  FROM imp.drv_ftr f
  JOIN code_prodcat cp ON f.Code = cp.Code
  GROUP BY yearweek(f.TradeDate), f.Code
)

SELECT *
FROM day2week
WHERE week_id > $START_WEEK_ID AND week_id < $END_WEEK_ID
ORDER BY week_id, Code
