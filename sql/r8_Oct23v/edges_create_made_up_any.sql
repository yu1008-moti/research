
-- step 0.

drop table Lv_1_s33;
drop table Lv_1_s17;
drop table Lv_1_topix;
drop table Lv_1_mkt;

-- step 1.

-- step 1.1 mkt-s33

create temp table Lv_1_s33 as (
with 
stk as (
    select
        o.tradeDate, o.s33,
        n.gnID as gnID, 
        n.lnID as lnID, 
        n.cID as cID,
        n.ntID as ntID
    from feats.stocks as o
    join id.node as n
    on o.tradeDate = n.tradeDate and n.code = o.code and n.ntID = 0
),
mkt as (
    select
        o.tradeDate, n.code,
        n.gnID as gnID, 
        n.lnID as lnID, 
        n.cID as cID,
        n.ntID as ntID
    from feats.mktidx as o
    join id.node as n
    on o.tradeDate = n.tradeDate 
    and n.code = o.code 
    and n.ntID = 2 
    and n.code in (
        '0040', '0041', '0042', '0043',
        '0044', '0045', '0046', '0047',
        '0048', '0049', '004A', '004B',
        '004C', '004D', '004E', '004F',
        '0050', '0051', '0052', '0053',
        '0054', '0055', '0056', '0057',
        '0058', '0059', '005A', '005B',
        '005C', '005D', '005E', '005F',
        '0060', 
    )
),
edge as (
    select
        t.tradeDate, 
        m.gnID as mktidx_gnID, 
        m.lnID as mktidx_lnID, 
        m.cID  as mktidx_cID,
        m.ntID as mktidx_ntID,
        t.gnID as stock_gnID, 
        t.lnID as stock_lnID, 
        t.cID  as stock_cID,
        t.ntID as stock_ntID,
        1      as attr,
        3      as etID
    from stk as t
    join mkt as m
    on m.tradeDate = t.tradeDate
    and m.code = t.s33
)
select * from edge order by tradeDate, stock_gnID, mktidx_gnID
);

-- step 1.2 mkt-s17

-- return Lv_1_s33;
-- create or replace table edges.made_up_s33 as (select * from Lv_1_s33 order by tradeDate, stock_gnID, mktidx_gnID);

create temp table Lv_1_s17 as (
with
stk as (
    select
        o.tradeDate, o.s17,
        n.gnID as gnID, 
        n.lnID as lnID, 
        n.cID as cID,
        n.ntID as ntID
    from feats.stocks as o
    join id.node as n
    on o.tradeDate = n.tradeDate and n.code = o.code and n.ntID = 0
),
mkt as (
    select
        o.tradeDate, n.code,
        n.gnID as gnID, 
        n.lnID as lnID, 
        n.cID as cID,
        n.ntID as ntID
    from feats.mktidx as o
    join id.node as n
    on o.tradeDate = n.tradeDate 
    and n.code = o.code 
    and n.ntID = 2 
    and n.code in (
        '0080', '0081', '0082', '0083',
        '0084', '0085', '0086', '0087',
        '0088', '0089', '008A', '008B',
        '008C', '008D', '008E', '008F',
        '0090'
    )
),
edge as (
    select
        t.tradeDate, 
        m.gnID as mktidx_gnID, 
        m.lnID as mktidx_lnID, 
        m.cID  as mktidx_cID,
        m.ntID as mktidx_ntID,
        t.gnID as stock_gnID, 
        t.lnID as stock_lnID, 
        t.cID  as stock_cID,
        t.ntID as stock_ntID,
        1      as attr,
        4      as etID
    from stk as t
    join mkt as m
    on m.tradeDate = t.tradeDate
    and m.code = t.s17
)
select * from edge order by tradeDate, stock_gnID, mktidx_gnID
);

-- return Lv_1_s17;
-- create or replace table edges.made_up_s17 as (select * from Lv_1_s17 order by tradeDate, stock_gnID, mktidx_gnID);

-- step 1.3 mkt-topix

create temp table Lv_1_topix as (
with
stk as (
    select
        o.tradeDate, o.mkt,
        n.gnID as gnID, 
        n.lnID as lnID, 
        n.cID as cID,
        n.ntID as ntID
    from feats.stocks as o
    join id.node as n
    on o.tradeDate = n.tradeDate and n.code = o.code and n.ntID = 0
),
mkt as (
    select
        o.tradeDate, n.code,
        n.gnID as gnID, 
        n.lnID as lnID, 
        n.cID as cID,
        n.ntID as ntID
    from feats.mktidx as o
    join id.node as n
    on o.tradeDate = n.tradeDate 
    and n.code = o.code 
    and n.ntID = 2 
    and n.code in (
        '0000'
    )
),
edge as (
    select
        t.tradeDate, 
        m.gnID as mktidx_gnID, 
        m.lnID as mktidx_lnID, 
        m.cID  as mktidx_cID,
        m.ntID as mktidx_ntID,
        t.gnID as stock_gnID, 
        t.lnID as stock_lnID, 
        t.cID  as stock_cID,
        t.ntID as stock_ntID,
        1      as attr,
        2      as etID
    from stk as t
    join mkt as m
    on m.tradeDate = t.tradeDate
    and m.code = t.mkt
)
select * from edge order by tradeDate, stock_gnID, mktidx_gnID
);

-- return Lv_1_topix;
-- create or replace table edges.made_up_topix as (select * from Lv_1_topix order by tradeDate, stock_gnID, mktidx_gnID);

-- step 1.4 mkt-mkt(section-id)

create temp table Lv_1_mkt as (
with
stk as (
    select
        o.tradeDate, o.mkt,
        n.gnID as gnID, 
        n.lnID as lnID, 
        n.cID as cID,
        n.ntID as ntID
    from feats.stocks as o
    join id.node as n
    on o.tradeDate = n.tradeDate and n.code = o.code and n.ntID = 0
),
mkt as (
    select
        o.tradeDate, n.code,
        n.gnID as gnID, 
        n.lnID as lnID, 
        n.cID as cID,
        n.ntID as ntID
    from feats.mktidx as o
    join id.node as n
    on o.tradeDate = n.tradeDate 
    and n.code = o.code 
    and n.ntID = 2 
    and n.code in (
        '0000', '0001', '0070', '0091',  -- TOPIX, 東証二部, マザーズ, JASDAQ
        '0500', '0501', '0502'           -- Prime, Standard, Growth
    )
),
edge as (
    select
        t.tradeDate, 
        m.gnID as mktidx_gnID, 
        m.lnID as mktidx_lnID, 
        m.cID  as mktidx_cID,
        m.ntID as mktidx_ntID,
        t.gnID as stock_gnID, 
        t.lnID as stock_lnID, 
        t.cID  as stock_cID,
        t.ntID as stock_ntID,
        1      as attr,
        1      as etID
    from stk as t
    join mkt as m
    on m.tradeDate = t.tradeDate
    and m.code = t.mkt
)
select * from edge order by tradeDate, stock_gnID, mktidx_gnID
);

-- return Lv_1_mkt;
-- create or replace table edges.made_up_mkt as (select * from Lv_1_mkt order by tradeDate, stock_gnID, mktidx_gnID);