
-- step 0.

drop table Lv_0;
drop table Lv_1;

create or replace temp table Lv_0 as (
select
    distinct tradeDate
from 
    dev.id.node
);

-- step 1.

create or replace temp table Lv_1 as (
select
    tradeDate,
    dense_rank() over(order by tradeDate) as tID, -- ID ignoring the gaps in the tradeDate
    tradeDate - minDate as elpDs, -- elapsed days from the first date
from (
    select
    *, min(tradeDate) over() as minDate
    from Lv_0
)
order by tradeDate
);

-- return Lv_1;

select count(*) - count(distinct (tID, tradeDate)) as dup from Lv_1;
create table dev.id.date as (select * from Lv_1 order by tID);