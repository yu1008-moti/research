
drop view if exists act.sequence.node;

-- stocks sequence

create view act.sequence.node as(
with
    stack as(
        select *
        from(
            (select * from dev.seq.stocks order by gnID)
            union all
            (select * from dev.seq.statements order by gnID)
            union all
            (select * from dev.seq.mktidx order by gnID)
            union all
            (select * from dev.seq.futures order by gnID)
        )
    ),
    withtID as(
        select
            o.gnID,
            t.tID,
            o.seq
        from stack as o
        join dev.id.node as n
        on o.gnID = n.gnID
        join dev.id.date as t
        on n.tradeDate = t.tradeDate
    )
    select * from withtID order by gnID
);

select count(distinct gnID) from act.sequence.node; 
select count(distinct (tID, cID, ntID)) from act.tools.node_tool;
select count(*) - count(distinct (gnID)) as dup from act.sequence.node;

COMMENT ON VIEW act.sequence.node IS 'this sequence means the gnID sequence for all nodes.';

select database_name, schema_name, view_name, comment from duckdb_views() where not internal;
