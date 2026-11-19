
-- step 0.

drop table NxRi;

-- step 1. 

create temp table NxRi as (
with
tgt_set as (
select
    tradeDate,
    code,
    (lag(C, -1) over(partition by code order by tradeDate)) / C as CRatio,
from (select * from dev.x.stocks where mkt = '0000')
),
calcRi as (
    select 
        * exclude(CRatio),
        log(CRatio) as NxLogRi,
        CRatio - 1 as NxRi,
        0 as neg,
        0 as neu,
        0 as pos
    from tgt_set
),
masked_error as (
    select
        *,
        if(
            isnan(NxLogRi) or isinf(NxLogRi) or (NxLogRi is null),
            0,
            1
        ) as mask_NxLogRi,
        if(
            isnan(NxRi) or isinf(NxRi) or (NxRi is null),
            0,
            1
        ) as mask_NxRi
        from calcRi
),
masked_outlier as (
    select * exclude(mask_NxLogRi, mask_NxRi, rn)
    from (
        select
            *,
            row_number() over(order by NxRi) as rn,
        from masked_error
    )
    where 
        -- upper and lower 1% of the data are considered as outliers
        rn > (select count(*) from masked_error) * 0.01
        and rn <= (select count(*) from masked_error) * 0.99
        -- mask error NxLogRi and NxRi
        -- both of mask length is same.
        and mask_NxLogRi * mask_NxRi = 1
)
select * from masked_outlier order by tradeDate, code
);

select * from NxRi order by tradeDate, code;

select count(*) - count(distinct (tradeDate, code)) as dup from NxRi;

summarize select * from NxRi;
