CREATE OR REPLACE TABLE AS(SELECT 
    Date, Code,
    LOG(COLUMNS(* EXCLUDE (Date, Code)) + 1)
  FROM mbd_qtt;
)