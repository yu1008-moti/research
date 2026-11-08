
-- step 0.

drop view if exists act.label.nxri;

-- step 1.

create view if not exists act.label.nxri as(
    select
        o.tID,
        o.gnID,
        n.lnID,
        o.cID,
        o.ntID,
        o.* exclude(tID, gnID, cID, ntID)
    from(
        select 
            t.tID,
            n.gnID,
            n.cID,
            n.ntID,
            o.* exclude(tradeDate, code)
        from dev.label.nxri as o
        join dev.id.date as t
        on o.tradeDate = t.tradeDate
        join dev.id.node as n
        on o.code = n.code and o.tradeDate = n.tradeDate and n.ntID = 0
    ) as o
    join act.tools.node_tool as n
    on o.tID = n.tID and o.gnID = n.gnID
    order by tID, gnID
);

select count(*) - count(distinct (tID, cID, ntID)) = 0 as dup_type1 from act.label.nxri;
select count(*) - count(distinct (tID, lnID)) = 0 as dup_type2 from act.label.nxri;

summarize select * from act.label.nxri;

COMMENT ON VIEW act.label.nxri IS 'this label means the next-day return/logged-return of stock data.';

select database_name, schema_name, view_name, comment from duckdb_views() where not internal;
