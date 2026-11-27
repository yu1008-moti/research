
-- step 0.

drop view if exists act.label.nxri;

-- step 1.

create view if not exists act.label.nxri as(
    with
    tmp as(
        select
            o.tID,
            o.gnID,
            n.lnID,
            o.cID,
            o.ntID,
            o.* exclude(tID, gnID, cID, ntID),
            m.idxNxRi,
            m.idxNxLogRi
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
        join (
            select
                tID,
                (lag(C, -1) over(order by tID))/C -1 as idxNxRi,
                log((lag(C, -1) over(order by tID))/C +1) as idxNxLogRi
            from act.nodes.mktidx
            where cID=5969
        ) as m
        on o.tID = m.tID
    )
    select
        t.tID, t.gnID, t.lnID, t.cID, t.ntID,
        t.NxRi, t.NxLogRi,
        t.idxNxRi, t.idxNxLogRi,
        med.XSecRiMed, med.XSecLogRiMed,
        t.pos, t.neu, t.neg
    from tmp as t
    join (
        select
            tID, median(NxRi) as XSecRiMed, log(median(NxRi) +1) as XSecLogRiMed
        from tmp
        group by tID
    ) as med
    on t.tID = med.tID
    order by tID, gnID
);

select count(*) - count(distinct (tID, cID, ntID)) = 0 as dup_type1 from act.label.nxri;
select count(*) - count(distinct (tID, lnID)) = 0 as dup_type2 from act.label.nxri;

summarize select * from act.label.nxri;

COMMENT ON VIEW act.label.nxri IS 'this label means the next-day return/logged-return of stock data.';

select database_name, schema_name, view_name, comment from duckdb_views() where not internal;
