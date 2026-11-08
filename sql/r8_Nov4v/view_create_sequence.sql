
drop view if exists act.seq.node;

-- stocks seq

create view act.seq.node as(
-- create or replace table test_seq as(
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
            n.ntID,
            o.seq
        from stack as o
        join dev.id.node as n
        on o.gnID = n.gnID
        join dev.id.date as t
        on n.tradeDate = t.tradeDate
    )
    select * from withtID order by gnID
);

-- select count(distinct gnID) from test_seq;
-- select count(*) - count(distinct (gnID)) as dup from test_seq;

select count(distinct gnID) from act.seq.node; 
select count(distinct (tID, cID, ntID)) from act.tools.node_tool;
select count(*) - count(distinct (gnID)) as dup from act.seq.node;

COMMENT ON VIEW act.seq.node IS 'this seq means the gnID seq for all nodes.';

select database_name, schema_name, view_name, comment from duckdb_views() where not internal;
