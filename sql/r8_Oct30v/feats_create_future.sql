
-- step 0.

drop table Lv_0;
drop table Lv_1;
drop table Lv_2;

create temp table Lv_0 as (
    select *
    from syn.raw.drv_ftr
    where ProdCat = 'TOPIXF'
);

-- step 1.

create temp table Lv_1 as (
select 
    cast(Date as date) as tradeDate,
    Code as code,
    O, H, L, C, Vo as V, OI, CM
from Lv_0
);

-- -- step 2.

-- -- improve code <before → 1:n>

create temp table Lv_2 as (
    select
        tradeDate,
        substring(CM, 2, 3) || substring(CM, 6, 2) as code,
        * exclude(tradeDate, CM, code)
    from Lv_1
);

-- step 3.

create temp table Lv_3 as (
    select *
    from Lv_2
    qualify row_number() over(partition by tradeDate, code order by tradeDate desc) = 1
);


select * from Lv_3 order by code, tradeDate;

select count(*) - count(distinct (tradeDate, code)) as dup from Lv_3;
