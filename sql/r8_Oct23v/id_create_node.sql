
-- step 0.

drop table Lv_0;
drop table Lv_1;


-- step 1.

-- define ntID
-- 0: stocks
-- 1: statements
-- 2: mktidx
-- 3: futures

create temp table Lv_0 as (
    select tradeDate, code, 0 as ntID from feats.stocks
    union all
    select tradeDate, code, 1 as ntID from feats.statements
    union all
    select tradeDate, code, 2 as ntID from feats.mktidx
    union all
    select tradeDate, code, 3 as ntID from feats.futures
);

-- step 2.

-- 2.1. get Global-id & Local-id

create temp table Lv_1 as (
select
    tradeDate, code, ntID,
    row_number() over() as gnID,
    row_number() over(partition by tradeDate order by ntID, code) as lnID,
    dense_rank() over(order by code) as cID
from Lv_0
order by tradeDate, ntID, code
);

-- return Lv_1;
