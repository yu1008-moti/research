
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
    from feats.stocks as o
    join id.node as n
    on o.tradeDate = n.tradeDate and n.code = o.code and n.ntID = 0
),
stm as (
    select
        o.tradeDate, 
        n.gnID as gnID, 
        n.lnID as lnID, 
        n.cID as cID,
        n.ntID as ntID
    from feats.statements as o
    join id.node as n
    on o.tradeDate = n.tradeDate and n.code = o.code and n.ntID = 1
),
edge as (
    select
        s.tradeDate, 
        s.gnID as statement_gnID, 
        s.lnID as statement_lnID, 
        s.cID  as statement_cID,
        t.gnID as stock_gnID, 
        t.lnID as stock_lnID, 
        t.cID  as stock_cID,
        s.ntID as statement_ntID,
        t.ntID as stock_ntID,
        1      as attr
    from stk as t
    asof join stm as s
    on s.tradeDate <= t.tradeDate and s.cID = t.cID
)
select * from edge order by tradeDate, stock_gnID, statement_gnID
);

-- return Lv_1;
-- create or replace table edges.recent_report as (select * from Lv_1 order by tradeDate, stock_gnID, statement_gnID);