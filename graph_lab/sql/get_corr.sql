WITH target AS (
  SELECT '2009-04-01'::DATE AS trade_date
),
recent AS (
  SELECT
    Code, TradeDate, DAdjC,
    ROW_NUMBER() OVER (PARTITION BY Code ORDER BY TradeDate DESC) AS rn_desc
  FROM imp.eqt_main
  WHERE TradeDate <= (SELECT trade_date FROM target)
  QUALIFY rn_desc <= 75
),
per_code AS (
  SELECT
    Code,
    COUNT(*) AS n,
    LIST(DAdjC ORDER BY TradeDate) AS px
  FROM recent
  GROUP BY Code
  HAVING MAX(TradeDate) = (SELECT trade_date FROM target)  -- 対象日に実際に取引がある銘柄のみ
),
pairs AS (
  SELECT
    a.Code AS t1_Code,
    b.Code AS t2_Code,
    LEAST(a.n, b.n) AS k,
    list_slice(a.px, -LEAST(a.n, b.n), -1) AS xa,
    list_slice(b.px, -LEAST(a.n, b.n), -1) AS xb
  FROM per_code a
  -- JOIN per_code b ON a.Code <= b.Code /* with self-loop */
  JOIN per_code b ON a.Code < b.Code /* without self-loop */
),
demeaned AS (                       -- ★ここが修正点：平均を引いてから内積を取る
  SELECT
    t1_Code, t2_Code, k,
    list_transform(xa, v -> v - list_avg(xa)) AS dxa,
    list_transform(xb, v -> v - list_avg(xb)) AS dxb
  FROM pairs
),
raw_corr AS(
  SELECT
    (SELECT trade_date FROM target) AS TradeDate,
    t1_Code, t2_Code, k,
    list_dot_product(dxa, dxb)
      / NULLIF(
          SQRT(
            GREATEST(list_dot_product(dxa, dxa), 0) *
            GREATEST(list_dot_product(dxb, dxb), 0)
          ), 0
        ) AS c
  FROM demeaned
),

binarize_corr AS(
  SELECT
    TradeDate AS snapshot_id, 
    t1_Code AS src_node_id, 
    t2_Code AS dst_node_id, 
    'corr' AS edge_type,
    IF(ABS(c) > 0.9, 1, 0) AS _c
  FROM raw_corr
  WHERE _c = 1
)

SELECT
  snapshot_id,
  src_node_id,
  dst_node_id,
  edge_type
FROM binarize_corr