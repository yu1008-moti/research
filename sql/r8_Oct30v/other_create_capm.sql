

-- step 0.

drop table if exists jgb10;
drop table if exists capm;

-- step 1.

-- get jgb10 data from csv file

create temp table jgb10 as(
with
Lv_0 as (
    select
    国債金利情報 as dt,
    substring(dt, 1, 1) as era,
    substring(dt, 2) as sepdt,
    column10 as jgb10
    from(
        select
        *,
        row_number() over() as rn
        from read_csv('..\temp\jgbcm_all.csv', encoding='shift_jis')
    )
    where rn > 1
),
Lv_1 as (
    select
    era,
    sepdt,
    split_part(sepdt, '.', 1) as year,
    split_part(sepdt, '.', 2) as month,
    split_part(sepdt, '.', 3) as day,
    *
    from Lv_0
),
Lv_2 as (
    select
    case
        when era = 'S' then 1925 + cast(year as int)
        when era = 'H' then 1988 + cast(year as int)
        when era = 'R' then 2018 + cast(year as int)
    end as year,
    month,
    day,
    jgb10
    from Lv_1
    where jgb10 != '-'
),
Lv_3 as(
    select
    cast(year || '-' || month || '-' || day as date) as date,
    round(cast(jgb10 as double)/100, 5) as jgb10
    from Lv_2
)
select * from Lv_3
);

-- step 2.

-- join jgb10 as risk-free-rate with stock and market return data

create temp table capm as(
with
jgb10 as (
    select
    date as tradeDate,
    jgb10 as Rf
    from jgb10
),
stock as (
    select 
    *, if(Ri is null, 0, Ri) as Ri 
    from (
        select
            tradeDate,
            code,
            (C / lag(C) over(partition by code order by tradeDate)) - 1 as Ri,
        from dev.x.stocks
    )
),
market as (
    select *
    from (
        select 
            tradeDate, 
            (C / lag(C) over(order by tradeDate)) - 1 as Rm
        from dev.x.mktidx
        where code = '0000'
    )
    where Rm is not null
),
capm as (
    select
        s.tradeDate,
        s.code,
        s.Ri - j.Rf as Ri,
        m.Rm - j.Rf as Rm
    from stock s
    left join market m on s.tradeDate = m.tradeDate
    left join jgb10 j on s.tradeDate = j.tradeDate
)
select * from capm where (Ri is not null) and not isnan(Ri) and not isinf(Ri) order by tradeDate, code
);

summarize select * from capm;

-- return: capm

-- create table store.capm as select * from capm;
select count(*) - count(distinct (tradeDate, code)) as dup from capm;



