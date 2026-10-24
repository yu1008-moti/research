
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
    from feats.mktidx as o
    join id.node as n
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
    from feats.futures as o
    join id.node as n
    on o.tradeDate = n.tradeDate and n.code = o.code and n.ntID = 3
),
edge as (
    select
        f.tradeDate, 
        f.gnID as future_gnID, 
        f.lnID as future_lnID, 
        f.cID  as future_cID,
        f.ntID as future_ntID,
        m.gnID as mktidx_gnID, 
        m.lnID as mktidx_lnID, 
        m.cID  as mktidx_cID,
        m.ntID as mktidx_ntID,
        1      as attr
    from mkt as m
    join ftr as f
    on m.tradeDate = f.tradeDate 
    and m.cID
)
select * from edge order by tradeDate, future_gnID, mktidx_gnID
);

-- return Lv_1;
-- create or replace table edges.recent_report as (select * from Lv_1 order by tradeDate, stock_gnID, statement_gnID);