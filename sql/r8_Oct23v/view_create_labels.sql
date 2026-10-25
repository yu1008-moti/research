
-- step 0.

drop view if exists act.labels.mv3;

-- step 1.

create view if not exists act.labels.mv3 as(
    select * from dev.store.NxRi order by tID, gnID
);

summarize select * from act.labels.mv3;
select * from duckdb_views() where not internal;
