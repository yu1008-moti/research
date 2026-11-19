
-- step 0.

drop table Lv_0;
drop table Lv_1;
drop table Lv_1_1;
drop table Lv_1_2;


-- step 1.

-- define ntID
-- 0: stocks
-- 1: statements
-- 2: mktidx
-- 3: futures

create temp table Lv_0 as (
    select tradeDate, code, 0 as ntID from dev.x.stocks
    union all
    select tradeDate, code, 1 as ntID from dev.x.statements
    union all
    select tradeDate, code, 2 as ntID from dev.x.mktidx
    union all
    select tradeDate, code, 3 as ntID from dev.x.futures
);

-- step 2.

-- 2.1. get Global-id & Local-id

create temp table Lv_1_1 as (
    select 
        code, row_number() over() -1 as cID 
    from (
        select
            code,
            list_sort(list_distinct(list(ntID))) as ntID_list
        from Lv_0
        group by code
        order by ntID_list[1], code
    )
);

create temp table Lv_1_2 as (
select
    L0.tradeDate, L0.code, L0.ntID,
    row_number() over(order by L0.tradeDate, L0.ntID, L0.code) -1 as gnID,
    row_number() over(partition by L0.tradeDate order by L0.ntID, L0.code) -1 as lnID,
    L1.cID as cID
from Lv_0 as L0
inner join Lv_1_1 as L1
on L0.code = L1.code
order by tradeDate, ntID, cID
);

-- return Lv_1_2;

select * from Lv_1_2 order by tradeDate, ntID, cID;

summarize select * from Lv_1_2;

select count(*) - count(distinct (tradeDate, code, ntID)) as dup from Lv_1_2;

-- ┌───────┐
-- │  dup  │
-- │ int64 │
-- ├───────┤
-- │     0 │
-- └───────┘

select
    count(*) - count(distinct lnID) as dup_lnID,
from Lv_1_2
group by tradeDate
having dup_lnID > 0;

-- ┌──────────┐
-- │ dup_lnID │
-- │  int64   │
-- └──────────┘
--    0 rows

create table dev.id.node as (select * from Lv_1_2 order by tradeDate, ntID, cID);

