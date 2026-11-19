select *
from(
    select 
        DiscDate as TradeDate,
        * exclude(DiscDate)
    from 
        imp.fin_sum
)
where
    '$start_date' <= TradeDate and TradeDate <= '$end_date'