SELECT 
  yearweek(DiscDate) AS week_id,
  * EXCLUDE(DiscDate)
FROM imp.fin_sum
WHERE Code IN $REGISTERED_CODES
ORDER BY week_id, Code