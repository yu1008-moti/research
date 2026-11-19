
-- step 0.

drop table Lv_1;

-- step 1.

create temp table Lv_1 as (
with 
stk as (
    select
        o.tradeDate, 
        n.gnID as gnID, 
        n.lnID as lnID, 
        n.cID as cID,
        n.ntID as ntID
    from dev.x.stocks as o
    join dev.id.node as n
    on o.tradeDate = n.tradeDate and n.code = o.code and n.ntID = 0
),
stm as (
    select
        o.tradeDate, 
        n.gnID as gnID, 
        n.lnID as lnID, 
        n.cID as cID,
        n.ntID as ntID
    from dev.x.statements as o
    join dev.id.node as n
    on o.tradeDate = n.tradeDate and n.code = o.code and n.ntID = 1
),
edge as (
    select
        t.tradeDate, 
        s.gnID as statement_gnID, 
        s.lnID as statement_lnID, 
        s.cID  as statement_cID,
        t.gnID as stock_gnID, 
        t.lnID as stock_lnID, 
        t.cID  as stock_cID,
    from stk as t
    asof join stm as s
    on s.tradeDate <= t.tradeDate and s.cID = t.cID
)
select * from edge order by tradeDate, stock_gnID, statement_gnID
);

-- return Lv_1;
-- create or replace table edges.recent_report as (select * from Lv_1 order by tradeDate, stock_gnID, statement_gnID);

select count(*) - count(distinct (tradeDate, statement_cID, stock_cID)) as dup from Lv_1;

-- ┌───────┐
-- │  dup  │
-- │ int64 │
-- ├───────┤
-- │     0 │
-- └───────┘

summarize select * from Lv_1;

-- ┌────────────────┬─────────────┬────────────┬────────────┬───────────────┬────────────────────────────┬────────────────────┬────────────┬────────────┬────────────┬──────────┬─────────────────┐
-- │  column_name   │ column_type │    min     │    max     │ approx_unique │            avg             │        std         │    q25     │    q50     │    q75     │  count   │ null_percentage │
-- │    varchar     │   varchar   │  varchar   │  varchar   │     int64     │          varchar           │      varchar       │  varchar   │  varchar   │  varchar   │  int64   │  decimal(9,2)   │
-- ├────────────────┼─────────────┼────────────┼────────────┼───────────────┼────────────────────────────┼────────────────────┼────────────┼────────────┼────────────┼──────────┼─────────────────┤
-- │ tradeDate      │ DATE        │ 2008-07-07 │ 2026-04-17 │          4380 │ 2018-04-10 12:14:00.856132 │ NULL               │ 2014-06-01 │ 2018-06-29 │ 2022-06-29 │ 12482415 │            0.00 │
-- │ statement_gnID │ BIGINT      │ 111446     │ 16010550   │        196590 │ 7609920.010935384          │ 4526910.368251968  │ 3661431    │ 7413665    │ 11466663   │ 12482415 │            0.00 │
-- │ statement_lnID │ BIGINT      │ 2422       │ 5164       │          2325 │ 3760.6087382930305         │ 679.0393740130628  │ 3674       │ 3986       │ 4233       │ 12482415 │            0.00 │
-- │ statement_cID  │ BIGINT      │ 0          │ 5656       │          4246 │ 3114.2361805788382         │ 1549.2734041676947 │ 1823       │ 3258       │ 4461       │ 12482415 │            0.00 │
-- │ stock_gnID     │ BIGINT      │ 109444     │ 16010548   │      13153325 │ 8024345.358143276          │ 4559623.3555828845 │ 4070039    │ 8013571    │ 11974591   │ 12482415 │            0.00 │
-- │ stock_lnID     │ BIGINT      │ 0          │ 4281       │          4086 │ 1961.2661517022148         │ 1087.9829175545622 │ 1051       │ 1901       │ 2842       │ 12482415 │            0.00 │
-- │ stock_cID      │ BIGINT      │ 0          │ 5656       │          4246 │ 3114.2361805788382         │ 1549.2734041676947 │ 1823       │ 3258       │ 4461       │ 12482415 │            0.00 │
-- └────────────────┴─────────────┴────────────┴────────────┴───────────────┴────────────────────────────┴────────────────────┴────────────┴────────────┴────────────┴──────────┴─────────────────┘