SELECT
  Code, firstTradeDate, EndTradeDate, isETF
FROM(
  SELECT 
    Code, 
    if(first(yearweek(TradeDate))<$START_YEAR_WEEK, $START_YEAR_WEEK, first(yearweek(TradeDate))) AS firstTradeDate, 
    last(yearweek(TradeDate)) AS EndTradeDate,
    if(last(S33) = '9999', 'ETF', '-') AS isETF
  FROM (
    SELECT *
    FROM synthesis.imp.eqt_main
    ORDER BY Code, TradeDate
    )
  GROUP BY Code
)
ORDER BY Code