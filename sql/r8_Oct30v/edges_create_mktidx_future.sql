
-- step 0.

drop table Lv_1;

-- step 1.

create temp table Lv_1 as (
with 
mkt as (
    select
        o.tradeDate, 
        n.gnID as gnID, 
        n.lnID as lnID, 
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
        n.lnID as lnID, 
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
        f.lnID as future_lnID, 
        f.cID  as future_cID,
        m.gnID as mktidx_gnID, 
        m.lnID as mktidx_lnID, 
        m.cID  as mktidx_cID,
    from mkt as m
    join ftr as f
    on m.tradeDate = f.tradeDate 
    and m.cID
)
select * from edge order by tradeDate, future_gnID, mktidx_gnID
);

-- return Lv_1;
-- create or replace table edges.mktidx_future as (select * from Lv_1 order by tradeDate, mktidx_gnID, future_gnID);

select count(*) - count(distinct (tradeDate, future_cID, mktidx_cID)) as dup from Lv_1;
-- ┌───────┐
-- │  dup  │
-- │ int64 │
-- ├───────┤
-- │     0 │
-- └───────┘

summarize select * from Lv_1;
-- ┌─────────────┬─────────────┬────────────┬────────────┬───────────────┬────────────────────────────┬────────────────────┬────────────┬────────────┬────────────┬───────┬─────────────────┐
-- │ column_name │ column_type │    min     │    max     │ approx_unique │            avg             │        std         │    q25     │    q50     │    q75     │ count │ null_percentage │
-- │   varchar   │   varchar   │  varchar   │  varchar   │     int64     │          varchar           │      varchar       │  varchar   │  varchar   │  varchar   │ int64 │  decimal(9,2)   │
-- ├─────────────┼─────────────┼────────────┼────────────┼───────────────┼────────────────────────────┼────────────────────┼────────────┼────────────┼────────────┼───────┼─────────────────┤
-- │ tradeDate   │ DATE        │ 2008-05-07 │ 2026-04-17 │          4423 │ 2017-12-11 13:03:50.613621 │ NULL               │ 2013-03-07 │ 2018-01-08 │ 2022-11-22 │ 23728 │            0.00 │
-- │ future_gnID │ BIGINT      │ 2530       │ 16010618   │         25117 │ 7802366.602789952          │ 5061656.785331244  │ 3031895    │ 7492959    │ 12385674   │ 23728 │            0.00 │
-- │ future_lnID │ BIGINT      │ 2475       │ 5221       │          1548 │ 3696.5918324342547         │ 723.593871376771   │ 2715       │ 3981       │ 4261       │ 23728 │            0.00 │
-- │ future_cID  │ BIGINT      │ 6026       │ 6110       │            82 │ 6067.0590020229265         │ 22.803504248443154 │ 6047       │ 6067       │ 6086       │ 23728 │            0.00 │
-- │ mktidx_gnID │ BIGINT      │ 2494       │ 16010551   │          4539 │ 7802310.791385705          │ 5061654.409212887  │ 3031840    │ 7492903    │ 12385617   │ 23728 │            0.00 │
-- │ mktidx_lnID │ BIGINT      │ 2422       │ 5165       │          1046 │ 3640.780428186109          │ 721.4766724923264  │ 2669       │ 3925       │ 4204       │ 23728 │            0.00 │
-- │ mktidx_cID  │ BIGINT      │ 5969       │ 5969       │             1 │ 5969.0                     │ 0.0                │ 5969       │ 5969       │ 5969       │ 23728 │            0.00 │
-- └─────────────┴─────────────┴────────────┴────────────┴───────────────┴────────────────────────────┴────────────────────┴────────────┴────────────┴────────────┴───────┴─────────────────┘