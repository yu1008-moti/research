--- CREATE OR REPLACE TABLE eqt_main_tmp AS
  WITH 
  base AS(
    SELECT
      TradeDate,
      Code,
      AdjC_f,
      COALESCE(AAdjC, AdjC_f, MAdjC) AS AAdjC_f,
      COALESCE(MAdjC, LAG(AAdjC_f) OVER w) AS MAdjC_f,
      CASE WHEN MAdjC_f IS NULL THEN 1 ELSE 0 END AS IPO
    FROM (
        SELECT
            CAST(Date AS DATE) AS TradeDate,
            Code,
            LAST_VALUE(AdjC IGNORE NULLS) OVER w AS AdjC_f,
            AAdjC,
            MAdjC
        FROM eqt_main
        WHERE TradeDate != '2020-10-01'
           OR SUBSTRING(Code, 5, 1) NOT IN ('1', '2', '9')
        WINDOW w AS (PARTITION BY Code ORDER BY TradeDate)
    )
    WINDOW w AS (PARTITION BY Code ORDER BY TradeDate)
    ORDER BY Code, TradeDate
  ),
  
  base_v2 AS(
  SELECT 
    TradeDate, Code,
    COALESCE( AdjC_f, 0) AS DAdjC,
    COALESCE(AAdjC_f, 0) AS AAdjC,
    COALESCE(MAdjC_f, 0) AS MAdjC,
    IPO
  FROM base
  ),

  eqt_main_o AS(
    SELECT
      CAST(Date AS DATE) AS TradeDate, Code,
      AdjO AS DAdjO, 
      AdjH AS DAdjH, 
      AdjL AS DAdjL, 
      AdjC AS DAdjC, UL AS UpL, LL AS LoL,
      MAdjO, MAdjH, MAdjL, MAdjC, MUL AS MUpL, MLL AS MLoL,
      AAdjO, AAdjH, AAdjL, AAdjC, AUL AS AUpL, CAST("ALL" AS INTEGER) AS ALoL,
      S33 AS _S33, 
      S17 AS _S17, 
      Mkt AS _Mkt, 
      Mrgn
    FROM eqt_main
  )

  SELECT 
    t.TradeDate, 
    t.Code,
    t.IPO,
  
    COALESCE(o.DAdjO, t.DAdjC) AS DAdjO, 
    COALESCE(o.DAdjH, t.DAdjC) AS DAdjH, 
    COALESCE(o.DAdjL, t.DAdjC) AS DAdjL, 
    t.DAdjC AS DAdjC, 
    o.UpL, o.LoL,
   
    COALESCE(o.MAdjO, t.MAdjC) AS MAdjO, 
    COALESCE(o.MAdjH, t.MAdjC) AS MAdjH, 
    COALESCE(o.MAdjL, t.MAdjC) AS MAdjL, 
    t.MAdjC AS MAdjC,
    o.MUpL, o.MLoL,
  
    COALESCE(o.AAdjO, t.AAdjC) AS AAdjO,
    COALESCE(o.AAdjH, t.AAdjC) AS AAdjH,
    COALESCE(o.AAdjL, t.AAdjC) AS AAdjL,
    t.AAdjC AS AAdjC,
    o.AUpL, o.ALoL,
  
    CASE 
      WHEN o._S33 = 0050 THEN '0040'
      WHEN o._S33 = 1050 THEN '0041'
      WHEN o._S33 = 2050 THEN '0042'
      WHEN o._S33 = 3050 THEN '0043'
      WHEN o._S33 = 3100 THEN '0044'
      WHEN o._S33 = 3150 THEN '0045'
      WHEN o._S33 = 3200 THEN '0046'
      WHEN o._S33 = 3250 THEN '0047'
      WHEN o._S33 = 3300 THEN '0048'
      WHEN o._S33 = 3350 THEN '0049'
      WHEN o._S33 = 3400 THEN '004A'
      WHEN o._S33 = 3450 THEN '004B'
      WHEN o._S33 = 3500 THEN '004C'
      WHEN o._S33 = 3550 THEN '004D'
      WHEN o._S33 = 3600 THEN '004E'
      WHEN o._S33 = 3650 THEN '004F'
      WHEN o._S33 = 3700 THEN '0050'
      WHEN o._S33 = 3750 THEN '0051'
      WHEN o._S33 = 3800 THEN '0052'
      WHEN o._S33 = 4050 THEN '0053'
      WHEN o._S33 = 5050 THEN '0054'
      WHEN o._S33 = 5100 THEN '0055'
      WHEN o._S33 = 5150 THEN '0056'
      WHEN o._S33 = 5200 THEN '0057'
      WHEN o._S33 = 5250 THEN '0058'
      WHEN o._S33 = 6050 THEN '0059'
      WHEN o._S33 = 6100 THEN '005A'
      WHEN o._S33 = 7050 THEN '005B'
      WHEN o._S33 = 7100 THEN '005C'
      WHEN o._S33 = 7150 THEN '005D'
      WHEN o._S33 = 7200 THEN '005E'
      WHEN o._S33 = 8050 THEN '005F'
      WHEN o._S33 = 9050 THEN '0060'
      WHEN o._S33 = 9999 THEN '9999'
    ELSE '-'
    END AS S33, 
    
    CASE 
			WHEN o._S17 = 1  THEN '0080' 
			WHEN o._S17 = 2  THEN '0081'
			WHEN o._S17 = 3  THEN '0082'
			WHEN o._S17 = 4  THEN '0083'
			WHEN o._S17 = 5  THEN '0084'
			WHEN o._S17 = 6  THEN '0085'
			WHEN o._S17 = 7  THEN '0086'
			WHEN o._S17 = 8  THEN '0087'
			WHEN o._S17 = 9  THEN '0088'
			WHEN o._S17 = 10 THEN '0089'
			WHEN o._S17 = 11 THEN '008A'
			WHEN o._S17 = 12 THEN '008B'
			WHEN o._S17 = 13 THEN '008C'
			WHEN o._S17 = 14 THEN '008D'
			WHEN o._S17 = 15 THEN '008E'
			WHEN o._S17 = 16 THEN '008F'
			WHEN o._S17 = 17 THEN '0090'
			WHEN o._S17 = 99 THEN '9999'
      ELSE '-'
    END AS S17, 
    
    CASE
      WHEN o._Mkt = 111 AND ('2022/06/27' <= t.TradeDate AND t.TradeDate < '2026/04/17') THEN '0500' -- プライム
      WHEN o._Mkt = 111 AND ('2022/04/04' <= t.TradeDate AND t.TradeDate < '2022/06/27') THEN '7000' -- 〃
      WHEN o._Mkt = 112 AND ('2022/06/27' <= t.TradeDate AND t.TradeDate < '2026/04/17') THEN '0501' -- スタンダード
      WHEN o._Mkt = 112 AND ('2022/04/04' <= t.TradeDate AND t.TradeDate < '2022/06/27') THEN '7001' -- 〃
      WHEN o._Mkt = 113 AND ('2022/06/27' <= t.TradeDate AND t.TradeDate < '2026/04/17') THEN '0502' -- グロース
      WHEN o._Mkt = 113 AND ('2022/04/04' <= t.TradeDate AND t.TradeDate < '2022/06/27') THEN '7002' -- 〃
      WHEN o._Mkt = 104                                                                  THEN '0070' -- マザーズ
      WHEN o._Mkt = 101                                                                  THEN '0000' -- 東証一部
      WHEN o._Mkt = 102                                                                  THEN '0001' -- 東証二部
      WHEN o._Mkt = 106                                                                  THEN '0091' -- JASDAQ
      WHEN o._Mkt = 107                                                                  THEN '0091' -- JASDAQ
      WHEN o._Mkt = 109                                                                  THEN '9999' -- 該当しない
    ELSE '-'
    END AS Mkt, 
    
    o.Mrgn
    
  FROM base_v2 t
  LEFT JOIN eqt_main_o o
  ON 
    t.TradeDate = o.TradeDate AND
    t.Code = o.Code
  WHERE o._Mkt != 0105 -- TOKYO PRO MARKET は対象外とする
  ORDER BY TradeDate, Code