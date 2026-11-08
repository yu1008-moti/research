create temp table Lv_1 as (
with 
any2ID as (
    select
        n.gnID,
        n.ntID,
        o.* exclude(tradeDate, code)
    from dev.x.statements as o
    join dev.id.node as n
    on o.code = n.code and o.tradeDate = n.tradeDate and n.ntID = 1
)
select
    e.tradeDate,
    n.code,
    o.* exclude(gnID, ntID)
from dev.edge.recent_report as e
join any2ID as o
on e.statement_gnID = o.gnID
join dev.id.node as n
on e.stock_gnID = n.gnID and e.tradeDate = n.tradeDate and n.ntID = 0
order by tradeDate, code
);

select count(*) - count(distinct (tradeDate, code)) as dup from Lv_1;

-- ┌───────┐
-- │  dup  │
-- │ int64 │
-- ├───────┤
-- │     0 │
-- └───────┘

create or replace table dev.x.full_statements as (select * from Lv_1 order by tradeDate, code);

---------------------------------------------- BELOW IS VERSION 2 ----------------------------------------------

create temp table Lv_1 as (
with 
get_next_tradeDate as (
    select 
        tradeDate,
        lag(tradeDate, -1) over (partition by code order by tradeDate) as next_tradeDate,
        code,
    from dev.x.statements
),
fill_null_next_tradeDate as (
    select 
        tradeDate,
        if(next_tradeDate is null, cast('2026-04-17' as DATE), next_tradeDate) as next_tradeDate,
        code
    from get_next_tradeDate
),
expanded as (
    select 
        e.tradeDate as expand_tradeDate,
        o.tradeDate,
        o.code,
    from dev.id.date as e
    join fill_null_next_tradeDate as o
    on e.tradeDate >= o.tradeDate and e.tradeDate < o.next_tradeDate
),
set_values as(
    select
        o.expand_tradeDate as tradeDate,
        o.code,
        stm.* exclude(tradeDate, code)
    from expanded as o
    join dev.x.statements as stm
    on o.code = stm.code and o.tradeDate = stm.tradeDate
)
select * from set_values order by tradeDate, code
);
