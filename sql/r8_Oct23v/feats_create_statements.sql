
-- step 0

drop table if exists Lv_0;
drop table if exists Lv_1;
drop table if exists Lv_2;
drop table if exists Lv_3;
drop table if exists Lv_4;

-- step 0.1.

create temp table Lv_0 as (
select *
from(
    select
    *, min(DiscDate) over (partition by Code, CurPerEn) as minDiscDate
    from (
        select
        *,
        from syn.raw.fin_sum
        where DocType like '__FinancialStatements$_Consolidated$_JP' escape '$'
    )
)
where DiscDate = minDiscDate
order by DiscDate, Code
);

-- step 1.

create temp table Lv_1 as(
select
cast(DiscDate as date) as tradeDate,
Code as code,
CurPerType,
last_value(Sales ignore nulls) over (partition by Code, CurPerType order by tradeDate rows between unbounded preceding and current row) as Sales,
last_value(OP    ignore nulls) over (partition by Code, CurPerType order by tradeDate rows between unbounded preceding and current row) as OP,
last_value(OdP   ignore nulls) over (partition by Code, CurPerType order by tradeDate rows between unbounded preceding and current row) as OdP,
last_value(NP    ignore nulls) over (partition by Code, CurPerType order by tradeDate rows between unbounded preceding and current row) as NP,
EPS,
last_value(TA     ignore nulls) over (partition by Code, CurPerType order by tradeDate rows between unbounded preceding and current row) as TA,
last_value(Eq     ignore nulls) over (partition by Code, CurPerType order by tradeDate rows between unbounded preceding and current row) as Eq,
last_value(EqAR   ignore nulls) over (partition by Code, CurPerType order by tradeDate rows between unbounded preceding and current row) as EqAR,
BPS,
if(CFO    is null, 0, CFO   ) as CFO,
if(CFI    is null, 0, CFI   ) as CFI,
if(CFF    is null, 0, CFF   ) as CFF,
if(CashEq is null, 0, CashEq) as CashEq,
case when CurPerType = '1Q' then Div1Q
     when CurPerType = '2Q' then Div2Q
     when CurPerType = '3Q' then Div3Q
     when CurPerType = 'FY' then DivFY
     else 0
end as DivnQ,
last_value(ShOutFY ignore nulls) over (partition by Code order by tradeDate rows between unbounded preceding and current row) as ShOutFY,
last_value(TrShFY  ignore nulls) over (partition by Code order by tradeDate rows between unbounded preceding and current row) as TrShFY,
from Lv_0
);

-- step 1.*

-- 1.1. Share data
update Lv_1
set TrShFY = ShOutFY * 0 -- need to seek reasonable value (default: 0.0)
where TrShFY is null;

update Lv_1
set DivnQ = 0
where DivnQ is null;

-- 1.2. P/L series
update Lv_1
set Sales = 0
where Sales is null;

update Lv_1
set OP = 0
where OP is null;

update Lv_1
set OdP = 0
where OdP is null;

update Lv_1
set NP = 0
where NP is null;

-- 1.3. B/S series
update Lv_1
set TA = 0
where TA is null;

update Lv_1
set Eq = 0
where Eq is null;

-- step 2.

create temp table Lv_2 as (
select *
from(
    pivot(
    select
    * exclude(CurPerType),
    case when CurPerType = '1Q' then 'Q1'
         when CurPerType = '2Q' then 'Q2'
         when CurPerType = '3Q' then 'Q3'
         when CurPerType = 'FY' then 'FY'
    end as CurPerType
    from Lv_1)
    on CurPerType
));

-- step 3.

-- 3.1. Remaining : [EPS, BPS, EqAR]
create temp table Lv_3 as (
select
tradeDate, code, Sales, OP, OdP, NP,
if(EPS is null, NP/(ShOutFY-TrShFY), EPS) as EPS,
TA, Eq,
if(EqAR is null, Eq/(TA), EqAR) as EqAR,
if(BPS is null, Eq/(ShOutFY-TrShFY), BPS) as BPS,
CFO, CFI, CFF, CashEq, DivnQ,
ShOutFY - TrShFY as ActualShOutFY,
Q1, Q2, Q3, FY
from Lv_2
order by tradeDate, Code
);

-- 3.2. solute Nan and Inf values
update Lv_3
set EPS = 0
where isnan(EPS) or isinf(EPS);

update Lv_3
set BPS = 0
where isnan(BPS) or isinf(BPS);

update Lv_3
set EqAR = 0
where isnan(EqAR) or isinf(EqAR);

-- 3.3. set 0 for as under limit
update Lv_3
set EPS = 0
where EPS < 0;

update Lv_3
set BPS = 0
where BPS < 0;

-- 3.4. modify Q1~3 and FY max-value

update Lv_3
set Q1 = 1
where Q1 > 1;

update Lv_3
set Q2 = 1
where Q2 > 1;

update Lv_3
set Q3 = 1
where Q3 > 1;

update Lv_3
set FY = 1
where FY > 1;

-- 4. solute potential error

create temp table Lv_4 as (
with 
Lv_3_1 as (
    select
    *,
    if(ActualShOutFY < 0, null, ActualShOutFY) as tmp_ActualShOutFY
    from Lv_3
),
Lv_3_2 as (
    select
    *,
    -- lag(tradeDate) over (partition by Code order by tradeDate) as prev_tradeDate,
    last_value(tmp_ActualShOutFY ignore nulls) over (partition by Code order by tradeDate rows between unbounded preceding and current row) as imp_ActualShOutFY
    from Lv_3_1
),
Lv_3_3 as (
    select 
    tradeDate, code, 
    Sales, OP, OdP, NP, EPS, 
    TA, Eq, EqAR, BPS,
    CFO, CFI, CFF, CashEq, DivnQ, 
    if(tmp_ActualShOutFY is null, imp_ActualShOutFY, tmp_ActualShOutFY) as ActualShOutFY, 
    Q1, Q2, Q3, FY
    from Lv_3_2
    -- where tradeDate - prev_tradeDate > 70
)
select * from Lv_3_3
);

create temp table Lv_5 as (
select 
* 
from (
    select 
    * 
    from (
        select 
        *, row_number() over(partition by tradeDate, code order by CFO desc) as rn -- to eliminate error rows
        from Lv_4 --dev.feats.statements
    ) 
where rn=1
)
);

-- -- display results
summarize select * from Lv_5;

-- -- check
select * from Lv_5 where code in ['97480'] order by code, tradeDate;

-- return Lv_4;

-- if you want to create a permanent table, you can use the following command:
-- create or replace table <table-Name> as (select * from Lv_4 <etc.>);
