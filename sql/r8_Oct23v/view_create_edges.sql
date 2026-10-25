
-- step 0.

drop view if exists act.edges.recent_report;
drop view if exists act.edges.made_up_s33;
drop view if exists act.edges.made_up_s17;
drop view if exists act.edges.made_up_mkt;
drop view if exists act.edges.made_up_topix;
drop view if exists act.edges.mktidx_future;

-- step 1.

-- centralized views for edges

create view if not exists act.edges.recent_report as(
    select 
    t.tID,
    o.* exclude(tradeDate)
    from dev.edges.recent_report as o
    join dev.id.date as t
    on o.tradeDate = t.tradeDate
);

comment on view act.edges.recent_report is 'this edge means the relationship between stock(target) and statement(souruce).';

create view if not exists act.edges.made_up_s33 as(
    select 
    t.tID,
    o.* exclude(tradeDate)
    from dev.edges.made_up_s33 as o
    join dev.id.date as t
    on o.tradeDate = t.tradeDate
);

comment on view act.edges.made_up_s33 is 'this edge means the relationship between stock(target) and mktidx(souruce). this mktidx means only s33 holds.';

create view if not exists act.edges.made_up_s17 as(
    select 
    t.tID,
    o.* exclude(tradeDate)
    from dev.edges.made_up_s17 as o
    join dev.id.date as t
    on o.tradeDate = t.tradeDate
);

comment on view act.edges.made_up_s17 is 'this edge means the relationship between stock(target) and mktidx(souruce). this mktidx means only s17 holds.';

create view if not exists act.edges.made_up_mkt as(
    select 
    t.tID,
    o.* exclude(tradeDate)
    from dev.edges.made_up_mkt as o
    join dev.id.date as t
    on o.tradeDate = t.tradeDate
);

comment on view act.edges.made_up_mkt is 'this edge means the relationship between stock(target) and mktidx(souruce). this mktidx means only prime / standard / growth / jasdaq / tosho1 / tosho2 .';

create view if not exists act.edges.made_up_topix as(
    select 
    t.tID,
    o.* exclude(tradeDate)
    from dev.edges.made_up_topix as o
    join dev.id.date as t
    on o.tradeDate = t.tradeDate
);

comment on view act.edges.made_up_topix is 'this edge means the relationship between stock(target) and mktidx(souruce). this mktidx means only topix.';

create view if not exists act.edges.mktidx_future as(
    select 
    t.tID,
    o.* exclude(tradeDate)
    from dev.edges.mktidx_future as o
    join dev.id.date as t
    on o.tradeDate = t.tradeDate
);

comment on view act.edges.mktidx_future is 'this edge means the relationship between mktidx(target) and future(souruce). this mktidx means only topix, future means only topixf.';
