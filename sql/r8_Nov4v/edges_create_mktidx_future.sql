-- ref: sql\r8_Nov4v\edges_create_recent_report.sql


-- step 0.

drop table Lv_1;
drop table Lv_2;

-- step 1.

create temp table Lv_1 as (
with 
mkt as (
    select
        o.tradeDate, 
        n.gnID as gnID, 
        n.cID as cID,
        n.ntID as ntID
    from dev.x.mktidx as o
    join dev.id.node as n
    on o.tradeDate = n.tradeDate 
    and n.code = o.code 
    and n.ntID = 2
    where o.code = '0000' -- means TOPIX
),
ftr as (
    select
        o.tradeDate, 
        n.gnID as gnID, 
        n.cID as cID,
        n.ntID as ntID
    from dev.x.futures as o
    join dev.id.node as n
    on o.tradeDate = n.tradeDate and n.code = o.code and n.ntID = 3
),
edge as (
    select
        f.tradeDate, 
        f.gnID as future_gnID, 
        f.cID  as future_cID,
        m.gnID as mktidx_gnID, 
        m.cID  as mktidx_cID,
    from mkt as m
    join ftr as f
    on m.tradeDate = f.tradeDate 
    and m.cID
),
set_tid as(
    select
        t.tID,
        o.future_gnID,
        o.future_cID,
        o.mktidx_gnID,
        o.mktidx_cID
    from edge as o
    join dev.id.date as t
    on o.tradeDate = t.tradeDate
)
select * from set_tid order by tID, future_gnID, mktidx_gnID
);

create temp table Lv_2 as(
    select
        e.tID,
        e.future_gnID,
        n1.lnID as future_lnID,
        e.future_cID,
        e.mktidx_gnID,
        n2.lnID as mktidx_lnID,
        e.mktidx_cID
    from Lv_1 as e
    join (select tID, gnID, lnID from act.tools.node_tool where ntID = 3) as n1
    on e.future_gnID = n1.gnID and e.tID = n1.tID
    join (select tID, gnID, lnID from act.tools.node_tool where ntID = 2) as n2
    on e.mktidx_gnID = n2.gnID and e.tID = n2.tID
);

-- return Lv_1;
-- create or replace table edges.mktidx_future as (select * from Lv_1 order by tradeDate, mktidx_gnID, future_gnID);

select count(*) - count(distinct (tID, future_cID, mktidx_cID)) as dup from Lv_2;
-- ┌───────┐
-- │  dup  │
-- │ int64 │
-- ├───────┤
-- │     0 │
-- └───────┘

summarize select * from Lv_2;

-- ┌─────────────┬─────────────┬────────────┬────────────┬───────────────┬───┬────────────┬────────────┬────────────┬───────┬─────────────────┐
-- │ column_name │ column_type │    min     │    max     │ approx_unique │ … │    q25     │    q50     │    q75     │ count │ null_percentage │
-- │   varchar   │   varchar   │  varchar   │  varchar   │     int64     │ … │  varchar   │  varchar   │  varchar   │ int64 │  decimal(9,2)   │
-- ├─────────────┼─────────────┼────────────┼────────────┼───────────────┼───┼────────────┼────────────┼────────────┼───────┼─────────────────┤
-- │ tradeDate   │ DATE        │ 2008-05-07 │ 2026-04-17 │          4423 │ … │ 2013-03-07 │ 2018-01-08 │ 2022-11-22 │ 23728 │            0.00 │
-- │ future_gnID │ BIGINT      │ 2530       │ 16010618   │         25117 │ … │ 3031895    │ 7492959    │ 12385674   │ 23728 │            0.00 │
-- │ future_cID  │ BIGINT      │ 6026       │ 6110       │            82 │ … │ 6047       │ 6067       │ 6086       │ 23728 │            0.00 │
-- │ mktidx_gnID │ BIGINT      │ 2494       │ 16010551   │          4539 │ … │ 3031840    │ 7492903    │ 12385617   │ 23728 │            0.00 │
-- │ mktidx_cID  │ BIGINT      │ 5969       │ 5969       │             1 │ … │ 5969       │ 5969       │ 5969       │ 23728 │            0.00 │
-- └─────────────┴─────────────┴────────────┴────────────┴───────────────┴───┴────────────┴────────────┴────────────┴───────┴─────────────────┘
