
-- step 0.

drop view if exists act.tools.capm_tool;
drop view if exists act.tools.node_tool;
drop view if exists act.tools.date_tool;

create view if not exists act.tools.capm_tool as(
    select 
    t.tID,
    t.elpDs,
    n.gnID,
    n.lnID,
    n.cID,
    o.* exclude(tradeDate, code)
    from dev.store.capm as o
    join dev.id.node as n
    on o.code = n.code and o.tradeDate = n.tradeDate and n.ntID = 0
    join dev.id.date as t
    on o.tradeDate = t.tradeDate
);

comment on view act.tools.capm_tool is 'used JGB-10CM as risk-free-rate(=Rf). Ri and Rm are already subtracted by Rf.';

create view if not exists act.tools.node_tool as(
    select 
    t.tID,
    * exclude(tradeDate)
    from dev.id.node
    join dev.id.date as t
    on dev.id.node.tradeDate = t.tradeDate
);

comment on view act.tools.node_tool is 'used for mapping code to gnID, lnID, cID, ntID.';

create view if not exists act.tools.date_tool as(
    select 
    tID,
    * exclude(tID)
    from dev.id.date
);

comment on view act.tools.date_tool is 'used for mapping tradeDate to tID and elpDs.';

select database_name, schema_name, view_name, comment from duckdb_views() where not internal;
