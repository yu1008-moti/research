
-- step 0.

drop table NxRi;

-- step 1. 

create temp table NxRi as (
with
tgt_set as (
    select
        tradeDate, code,
        (lag(C, -1) over(partition by code order by tradeDate)) / C as CRatio,
    from (select * from dev.x.stocks where mkt in ['0000', '0500', '7000'])
),
calcRi as (
    select
        * exclude(CRatio),
        log(CRatio) as NxLogRi,
        CRatio - 1 as NxRi,
        0 as neg, 0 as neu, 0 as pos
    from tgt_set
),
masked_error as (
    select
        *,
        if(isnan(NxLogRi) or isinf(NxLogRi) or (NxLogRi is null), 1, 0) as mask_NxLogRi,
        if(isnan(NxRi) or isinf(NxRi) or (NxRi is null), 1, 0) as mask_NxRi
    from calcRi
)
select * exclude(mask_NxLogRi, mask_NxRi)
from masked_error 
where mask_NxLogRi = 0 and mask_NxRi = 0
order by tradeDate, code
);

select * from NxRi order by tradeDate, code;

select count(*) - count(distinct (tradeDate, code)) as dup from NxRi;

summarize select * from NxRi;
