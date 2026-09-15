CREATE OR REPLACE TABLE drv_ftr_tmp AS
-- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
-- First, create a temporary table to fill the missing values of DeviationRate and SQRemainingDays
-- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --

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