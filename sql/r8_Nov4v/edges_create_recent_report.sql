
-- step 0.

drop table Lv_1;
drop table Lv_2;

-- step 1.

create temp table Lv_1 as (
with 
stk as (
    select
        o.tradeDate, 
        n.gnID as gnID, 
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
        s.cID  as statement_cID,
        t.gnID as stock_gnID,
        t.cID  as stock_cID,
    from stk as t
    asof join stm as s
    on s.tradeDate <= t.tradeDate and s.cID = t.cID
),
set_tid as(
    select
        t.tID,
        o.statement_gnID,
        o.statement_cID,
        o.stock_gnID,
        o.stock_cID
    from edge as o
    join dev.id.date as t
    on o.tradeDate = t.tradeDate
)
select * from set_tid order by tID, stock_gnID, statement_gnID
);

create temp table Lv_2 as(
    select
        e.tID,
        e.statement_gnID,
        n1.lnID as statement_lnID,
        e.statement_cID,
        e.stock_gnID,
        n2.lnID as stock_lnID,
        e.stock_cID
    from Lv_1 as e
    join (select tID, gnID, lnID from act.tools.node_tool where ntID = 1) as n1
    on e.statement_gnID = n1.gnID and e.tID = n1.tID
    join (select tID, gnID, lnID from act.tools.node_tool where ntID = 0) as n2
    on e.stock_gnID = n2.gnID and e.tID = n2.tID
);

-- return Lv_1;
-- create or replace table edges.recent_report as (select * from Lv_1 order by tradeDate, stock_gnID, statement_gnID);

select count(*) - count(distinct (tID, statement_lnID, stock_lnID)) as dup from Lv_2;

-- ┌───────┐
-- │  dup  │
-- │ int64 │
-- ├───────┤
-- │     0 │
-- └───────┘

summarize select * from Lv_2;

-- ┌────────────────┬─────────────┬────────────┬────────────┬───────────────┬───┬────────────┬────────────┬────────────┬──────────┬─────────────────┐
-- │  column_name   │ column_type │    min     │    max     │ approx_unique │ … │    q25     │    q50     │    q75     │  count   │ null_percentage │
-- │    varchar     │   varchar   │  varchar   │  varchar   │     int64     │ … │  varchar   │  varchar   │  varchar   │  int64   │  decimal(9,2)   │
-- ├────────────────┼─────────────┼────────────┼────────────┼───────────────┼───┼────────────┼────────────┼────────────┼──────────┼─────────────────┤
-- │ tradeDate      │ DATE        │ 2008-07-07 │ 2026-04-17 │          4380 │ … │ 2014-06-09 │ 2018-07-15 │ 2022-06-20 │ 12482415 │            0.00 │
-- │ statement_gnID │ BIGINT      │ 111446     │ 16010550   │        196590 │ … │ 3671965    │ 7421279    │ 11440355   │ 12482415 │            0.00 │
-- │ statement_cID  │ BIGINT      │ 0          │ 5656       │          4246 │ … │ 1817       │ 3259       │ 4462       │ 12482415 │            0.00 │
-- │ stock_gnID     │ BIGINT      │ 109444     │ 16010548   │      13153325 │ … │ 4065085    │ 7995501    │ 11920472   │ 12482415 │            0.00 │
-- │ stock_cID      │ BIGINT      │ 0          │ 5656       │          4246 │ … │ 1817       │ 3259       │ 4462       │ 12482415 │            0.00 │
-- └────────────────┴─────────────┴────────────┴────────────┴───────────────┴───┴────────────┴────────────┴────────────┴──────────┴─────────────────┘
