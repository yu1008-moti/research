SELECT 
  yearweek(DiscDate) AS week_id,
  * EXCLUDE(DiscDate)
FROM imp.fin_sum
-- WHERE Code IN $REGISTERED_CODES
WHERE week_id > $START_WEEK_ID AND week_id < $END_WEEK_ID
ORDER BY week_id, Code