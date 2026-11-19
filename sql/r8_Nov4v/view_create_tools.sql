
select count(*) from dev.x.futures;
select count(*) from dev.x.stocks;
select count(*) from dev.x.full_statements;
select count(*) from dev.x.mktidx;

-- step 0.

drop view if exists act.tools.capm_tool;
drop view if exists act.tools.node_tool;
drop view if exists act.tools.date_tool;


----------------------------------------------------------------------------------------------------------------------------------


create view if not exists act.tools.node_tool as(
    select
        tID,
        gnID,
        row_number() over(partition by tID order by ntID, cID) -1 as lnID,
        cID,
        ntID
    from(
        select 
            t.tID,
            n.gnID,
            n.cID,
            n.ntID,
            o.* exclude(tradeDate, code)
        from(
            select tradeDate, code, 0 as ntID from dev.x.stocks
            union all
            select tradeDate, code, 1 as ntID from dev.x.full_statements
            union all
            select tradeDate, code, 2 as ntID from dev.x.mktidx
            union all
            select tradeDate, code, 3 as ntID from dev.x.futures
        ) as o
        asof join dev.id.node as n
        on o.tradeDate >= n.tradeDate and o.code = n.code and o.ntID = n.ntID
        join dev.id.date as t
        on o.tradeDate = t.tradeDate
    )
    order by tID, ntID, cID
);

select count(*) - count(distinct (tID, cID, ntID)) = 0 as dup_type1 from act.tools.node_tool;
select count(*) - count(distinct (tID, lnID)) = 0 as dup_type2 from act.tools.node_tool;
select sum(if(ok is false, 1, 0)) as error_num from (select count(*) - (max(lnID) + 1) = 0 as ok from act.tools.node_tool group by tID);

-- ┌───────────┐
-- │ dup_type1 │
-- │  boolean  │
-- ├───────────┤
-- │ true      │
-- └───────────┘

-- ┌───────────┐
-- │ dup_type2 │
-- │  boolean  │
-- ├───────────┤
-- │ true      │
-- └───────────┘

-- ┌───────────┐
-- │ error_num │
-- │  int128   │
-- ├───────────┤
-- │         0 │
-- └───────────┘

comment on view act.tools.node_tool is 'used for mapping code to gnID, lnID, cID, ntID.';


----------------------------------------------------------------------------------------------------------------------------------



----------------------------------------------------------------------------------------------------------------------------------


create view if not exists act.tools.date_tool as(
    select 
    tID,
    * exclude(tID)
    from dev.id.date
);

select count(*) - count(distinct (tID)) = 0 as dup_type1 from act.tools.date_tool;
select count(*) - count(distinct (tradeDate)) = 0 as dup_type2 from act.tools.date_tool;

-- ┌───────────┐
-- │ dup_type1 │
-- │  boolean  │
-- ├───────────┤
-- │ true      │
-- └───────────┘

-- ┌───────────┐
-- │ dup_type2 │
-- │  boolean  │
-- ├───────────┤
-- │ true      │
-- └───────────┘

comment on view act.tools.date_tool is 'used for mapping tradeDate to tID and elpDs.';

select database_name, schema_name, view_name, comment from duckdb_views() where not internal;


----------------------------------------------------------------------------------------------------------------------------------


create view if not exists act.tools.capm_tool as(
    select 
        o.tID,
        o.gnID,
        n.lnID,
        o.cID,
        o.Ri,
        o.Rm,
        from(
            select 
            t.tID,
            n.gnID,
            n.cID,
            o.* exclude(tradeDate, code)
            from dev.tool.capm_tool as o
            join dev.id.node as n
            on o.code = n.code and o.tradeDate = n.tradeDate and n.ntID = 0
            join dev.id.date as t
            on o.tradeDate = t.tradeDate
        ) as o
        join act.tools.node_tool as n
        on o.tID = n.tID and o.gnID = n.gnID
        order by tID, gnID
);

select count(*) - count(distinct (tID, cID, gnID)) = 0 as dup_type1 from act.tools.capm_tool;
select count(*) - count(distinct (tID, lnID)) = 0 as dup_type2 from act.tools.capm_tool;

comment on view act.tools.capm_tool is 'used JGB-10CM as risk-free-rate(=Rf). Ri and Rm are already subtracted by Rf.';

