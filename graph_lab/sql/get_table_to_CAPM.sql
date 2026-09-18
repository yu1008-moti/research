WITH 
day2week AS(
  SELECT 
    yearweek(TradeDate) AS week_id, 
    first(Code) AS Code,
    -- flags
    max(IPO) AS isIPO,
    max(UpL) AS isUpL,
    max(LoL) AS isLoL,
    -- log OHLCV
    log(first(DAdjO+1)) AS AdjO,
    log(max(DAdjH+1)) AS AdjH,
    log(min(DAdjL+1)) AS AdjL,
    log(last(DAdjC+1)) AS AdjC,
    log(last(AdjVo+1)) AS AdjVo,
    -- other features
    last(DAdjC+1) AS DAdjC,
    last(S33) AS S33,
    last(S17) AS S17,
    last(Mkt) AS Mkt,
    last(Section_id) AS Section_id,
    last(Mrgn) AS Mrgn
  FROM imp.eqt_main
  GROUP BY yearweek(TradeDate), Code
),
add_ReturnValue AS(
  SELECT 
    *, 
    lag(DAdjC, 1) OVER w AS lagged_DAdjC, 
    (DAdjC - lagged_DAdjC)/lagged_DAdjC AS r_i
  FROM day2week
  WINDOW w AS(
    PARTITION BY Code
    ORDER BY week_id
  )
),
weekly_eqt AS(
  SELECT
    week_id, Code,
    isIPO, isUpL, isLoL,
    AdjO, AdjH, AdjL, AdjC, AdjVo,
    if(r_i IS NULL, 0, r_i) AS r_i, 
    S33, S17, Mkt, Section_id, Mrgn
  FROM add_ReturnValue
  WHERE 
    -- Code = '13010' AND
    201000 < week_id AND 202600 > week_id
  ORDER BY week_id, Code
),
topix AS(
  SELECT 
    first(yearweek(TradeDate)) AS week_id,
    last(C) AS TOPIX_Close,
  FROM imp.idx_prc
  WHERE 
    201000 < yearweek(TradeDate) AND 
    202600 > yearweek(TradeDate) AND
    IdxNm = 'TOPIX'  
  GROUP BY yearweek(TradeDate), Code
  ORDER BY week_id
),
call_rate AS(
  SELECT
    first(week_id) AS week_id, 
    mean(CallRate) AS r_f
  FROM (
    SELECT
      yearweek(TradeDate) AS week_id,
      CAST(
        if(CALL_RATE = 'NA', NULL, CALL_RATE) 
        AS DOUBLE
      ) AS CallRate
    FROM store_others.call_rate
  )
  WHERE 
    201000 < week_id AND 202600 > week_id
  GROUP BY week_id
),
join_topix_callrate AS(
  SELECT
    t.week_id,
    LAG(t.TOPIX_Close, 1) OVER w AS lagged_TOPIX_Close,
    (t.TOPIX_Close-lagged_TOPIX_Close)/lagged_TOPIX_Close AS r_m,
    c.r_f AS r_f
  FROM topix t
  JOIN call_rate c
  ON t.week_id = c.week_id
  WINDOW w AS(
    ORDER BY t.week_id
  )
  ORDER BY week_id
)
SELECT
  w.week_id AS week_id, w.Code AS Code, 
  w.isIPO AS isIPO, w.isUpL AS isUpL, w.isLoL AS isLoL,
  w.AdjO AS AdjO, w.AdjH AS AdjH, w.AdjL AS AdjL, w.AdjC AS AdjC, w.AdjVo AS AdjVo,
  w.S33 AS S33, w.S17 AS S17, w.Section_id AS Section_id,
  w.Mkt AS Mkt, w.Mrgn AS Mrgn,
  w.r_i AS r_i,
  j.r_m AS r_m,
  j.r_f AS r_f
FROM weekly_eqt w
JOIN join_topix_callrate j
ON w.week_id = j.week_id
WHERE $YEAR_START < w.week_id AND w.week_id < $YEAR_END
ORDER BY week_id, Code