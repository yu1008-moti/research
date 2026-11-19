
-- step 0.

drop view if exists act.label.nxri;

-- step 1.

create view if not exists act.label.nxri as(
    select 
        t.tID,
        n.gnID,
        n.lnID,
        n.cID,
        n.ntID,
        o.* exclude(tradeDate, code)
    from dev.y.nxri as o
    join dev.id.date as t
    on o.tradeDate = t.tradeDate
    join dev.id.node as n
    on o.code = n.code and o.tradeDate = n.tradeDate and n.ntID = 0
    order by tID, gnID
);

summarize select * from act.label.nxri;

COMMENT ON VIEW act.label.nxri IS 'this label means the next-day return/logged-return of stock data.';

select database_name, schema_name, view_name, comment from duckdb_views() where not internal;
