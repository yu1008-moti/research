
-- step 0.

drop table if exists dev.store.NxRi;

-- step 1. 

create table dev.store.NxRi as (
with
tgt_set as (
select
    t.tID,   -- means date ID that ignore gap days
    t.elpDs, -- means elapsed days from the first date in the dataset
    n.gnID,  -- means global node ID (global: unique ID for each rows in all dates)
    n.lnID,  -- means local  node ID (local : unique ID for each rows in each date)
    n.cID,   -- means company/underlier-asset/market-index ID (specific: stock and statement can same cID, but different lnID and gnID)
    n.ntID,  -- means node-type ID (stock: 0, statement: 1, market-index: 2, future:3)
    (lag(o.C, -1) over(partition by n.cID order by t.tID)) / o.C - 1 as NxRi, -- means return of the stock
    0 as neg,
    0 as neu,
    0 as pos
from (select * from dev.feats.stocks where mkt = '0000') as o
join dev.id.date as t
on o.tradeDate = t.tradeDate
join dev.id.node as n
on o.code = n.code and o.tradeDate = n.tradeDate and n.ntID = 0
),
masked_error as (
    select *
    from tgt_set
    where 
    not isnan(NxRi)
    and not isinf(NxRi)
    and NxRi is not null
),
masked_outlier as (
    select *, 0 as T, 0 as V, 0 as E, 0 as isUse
    from (
        select
            *,
            row_number() over(order by NxRi) as rn,
        from masked_error
    )
    where 
        rn > (select count(*) from masked_error) * 0.01
        and rn <= (select count(*) from masked_error) * 0.99
        -- upper and lower 1% of the data are considered as outliers
)
select * from masked_outlier order by tID, gnID
);