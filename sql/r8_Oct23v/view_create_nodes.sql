
-- step 0.
drop view if exists stocks;
drop view if exists statements;
drop view if exists mktidx;
drop view if exists futures;

-- step 1.

create view if not exists act.nodes.stocks as(
    select
        t.tID,   -- means date ID that ignore gap days
        t.elpDs, -- means elapsed days from the first date in the dataset
        n.gnID,  -- means global node ID (global: unique ID for each rows in all dates)
        n.lnID,  -- means local  node ID (local : unique ID for each rows in each date)
        n.cID,   -- means company/underlier-asset/market-index ID (specific: stock and statement can same cID, but different lnID and gnID)
        n.ntID,  -- means node-type ID (stock: 0, statement: 1, market-index: 2, future:3)
        o.* exclude(tradeDate, code, s33, s17, mkt) 
    from dev.feats.stocks as o
    join dev.id.node as n 
    on o.code = n.code and o.tradeDate = n.tradeDate and n.ntID = 0
    join dev.id.date as t
    on o.tradeDate = t.tradeDate
    order by t.tID, n.gnID
);

comment on view act.nodes.stocks is 'this node means the stock data.';

create view if not exists act.nodes.statements as (
    select
        t.tID,   -- means date ID that ignore gap days
        t.elpDs, -- means elapsed days from the first date in the dataset
        n.gnID,  -- means global node ID (global: unique ID for each rows in all dates)
        n.lnID,  -- means local  node ID (local : unique ID for each rows in each date)
        n.cID,   -- means company/underlier-asset/market-index ID (specific: stock and statement can same cID, but different lnID and gnID)
        n.ntID,  -- means node-type ID (stock: 0, statement: 1, market-index: 2, future:3)
        o.* exclude(tradeDate, code) 
    from dev.feats.statements as o
    join dev.id.node as n 
    on o.code = n.code and o.tradeDate = n.tradeDate and n.ntID = 1
    join dev.id.date as t
    on o.tradeDate = t.tradeDate
    order by t.tID, n.gnID
);

comment on view act.nodes.statements is 'this node means the statement data.';

create view if not exists act.nodes.mktidx as (
    select
        t.tID,   -- means date ID that ignore gap days
        t.elpDs, -- means elapsed days from the first date in the dataset
        n.gnID,  -- means global node ID (global: unique ID for each rows in all dates)
        n.lnID,  -- means local  node ID (local : unique ID for each rows in each date)
        n.cID,   -- means company/underlier-asset/market-index ID (specific: stock and statement can same cID, but different lnID and gnID)
        n.ntID,  -- means node-type ID (stock: 0, statement: 1, market-index: 2, future:3)
        o.* exclude(tradeDate, code) 
    from dev.feats.mktidx as o
    join dev.id.node as n 
    on o.code = n.code and o.tradeDate = n.tradeDate and n.ntID = 2
    join dev.id.date as t
    on o.tradeDate = t.tradeDate
    order by t.tID, n.gnID
);

comment on view act.nodes.mktidx is 'this node means the market-index data.';

create view if not exists act.nodes.futures as (
    select
        t.tID,   -- means date ID that ignore gap days
        t.elpDs, -- means elapsed days from the first date in the dataset
        n.gnID,  -- means global node ID (global: unique ID for each rows in all dates)
        n.lnID,  -- means local  node ID (local : unique ID for each rows in each date)
        n.cID,   -- means company/underlier-asset/market-index ID (specific: stock and statement can same cID, but different lnID and gnID)
        n.ntID,  -- means node-type ID (stock: 0, statement: 1, market-index: 2, future:3)
        o.* exclude(tradeDate, code) 
    from dev.feats.futures as o
    join dev.id.node as n 
    on o.code = n.code and o.tradeDate = n.tradeDate and n.ntID = 3
    join dev.id.date as t
    on o.tradeDate = t.tradeDate
    order by t.tID, n.gnID
);

comment on view act.nodes.futures is 'this node means the future data.';

select database_name, schema_name, view_name, comment from duckdb_views() where not internal;
