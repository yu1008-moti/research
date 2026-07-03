
-- Now 
CREATE OR REPLACE TABLE drv_opt_tmp AS
  WITH 
  base_opt AS(
    SELECT
      CAST(SUBSTRING(CAST(Date AS STRING), 1, 10) AS DATE) AS TradeDate,
      * EXCLUDE(
        Date, LTD, CM,
        EO, EH, EL, EC, -- 92% Nothing
        MO, MH, ML, MC, -- A-OHLC include them (4% Nothing)
        AO, AH, AL, AC, -- OHLC include them (~0% Nothing)
        SQD, -- 100% Nothing
        Theo, BaseVol, IR, CCMFlag, -- 22% Nothing  -- NULL-TYPE-1
        Settle, UnderPx, VoOA, Strike -- 6% Nothing -- NULL-TYPE-2
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