

-- step.0

drop table Lv_0;

-- step 1.

create or replace temp table Lv_0 as (
select 
    TradeDate as tradeDate,
    Code as code,
    DAdjO as O,
    DAdjH as H,
    DAdjL as L,
    DAdjC as C,
    AdjVo as V,
    S33 as s33,
    S17 as s17,
    Mkt as mkt
from syn.imp.eqt_main
);