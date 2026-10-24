
-- step 0.

drop view if exists recent_report;
drop view if exists made_up_s33;
drop view if exists made_up_s17;
drop view if exists made_up_mkt;
drop view if exists made_up_topix;
drop view if exists mktidx_future;

-- step 1.

-- centralized views for edges

create view if not exists act.edges.recent_report as(
    select * from dev.edges.recent_report
);

comment on view act.edges.recent_report is 'this edge means the relationship between stock(target) and statement(souruce).';

create view if not exists act.edges.made_up_s33 as(
    select * from dev.edges.made_up_s33
);

comment on view act.edges.made_up_s33 is 'this edge means the relationship between stock(target) and mktidx(souruce). this mktidx means only s33 holds.';

create view if not exists act.edges.made_up_s17 as(
    select * from dev.edges.made_up_s17
);

comment on view act.edges.made_up_s17 is 'this edge means the relationship between stock(target) and mktidx(souruce). this mktidx means only s17 holds.';

create view if not exists act.edges.made_up_mkt as(
    select * from dev.edges.made_up_mkt
);

comment on view act.edges.made_up_mkt is 'this edge means the relationship between stock(target) and mktidx(souruce). this mktidx means only prime / standard / growth / jasdaq / tosho1 / tosho2 .';

create view if not exists act.edges.made_up_topix as(
    select * from dev.edges.made_up_topix
);

comment on view act.edges.made_up_topix is 'this edge means the relationship between stock(target) and mktidx(souruce). this mktidx means only topix.';

create view if not exists act.edges.mktidx_future as(
    select * from dev.edges.mktidx_future
);

comment on view act.edges.mktidx_future is 'this edge means the relationship between mktidx(target) and future(souruce). this mktidx means only topix, future means only topixf.';
