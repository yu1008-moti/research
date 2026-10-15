create or replace temp table final_return as(
    select 
        * exclude(is_valid)
    from (
        with 
        shifted as(
            select 
                Code, 
                TradeDate, 
                lag(TradeDate, -1) over w as l1_TradeDate, 
                Mkt, 
                DAdjC,
                AdjVo,
                lag(DAdjC, -1) over w as l1_DAdjC
            from 
                imp.eqt_main 
            where 
                Mkt in ['0000', '0500', '7000']
            window w as (
                partition by Code 
                order by code, TradeDate
            ) 
            order by Code, TradeDate
        ), 

        added_return as(
            select 
                Code, 
                TradeDate, 
                l1_TradeDate, 
                Mkt, 
                l1_DAdjC, 
                DAdjC, 
                AdjVo,
                (l1_DAdjC/DAdjC -1) as return 
            from 
                shifted
        ),

        modified_return as(
            select 
                * ,
                case 
                    when return is null then 0
                    when isnan(return) is true then 0
                    when isinf(return) is true then 0
                    when AdjVo = 0 then 0
                    else 1
                end as is_valid
            from 
                added_return
        ),

        filtered_return as(
            select 
                * 
            from 
                modified_return
            where 
                is_valid = 1
        )

        select 
            *
        from 
            filtered_return
    )
);

delete from final_return
where
    TradeDate = '2010-03-26' and Code = '50160';

delete from final_return
where
    TradeDate = '2008-12-24' and Code = '17860';

delete from final_return
where
    TradeDate = '2014-10-24' and Code = '79440';

delete from final_return
where
    TradeDate = '2020-08-28' and Code = '87290';

delete from final_return
where
    TradeDate = '2010-03-26' and Code = '68100';

delete from final_return
where
    TradeDate = '2009-08-07' and Code = '57210';

delete from final_return
where
    TradeDate = '2022-04-01' and Code = '83030';

delete from final_return
where
    TradeDate = '2017-07-31' and Code = '65020';

delete from final_return
where
    TradeDate = '2017-09-05' and Code = '32509';

delete from final_return
where
    TradeDate = '2016-07-29' and Code = '67530';

update final_return
set 
    DAdjC = DAdjC * 10,
where
    TradeDate < '2009-07-03' and Code = '86850';

update final_return
set 
    l1_DAdjC = l1_DAdjC * 10,
where
    TradeDate < '2009-07-02' and Code = '86850';

update final_return
set
    return = (l1_DAdjC/DAdjC -1),
where
    Code = '86850';


select 
    TradeDate, Code, return, Mkt, DAdjC, l1_DAdjC, l1_TradeDate, 
    if(return < -0.006283662477558294, 1, 0) as negative,
    if(return > 0.0062893081761006275, 1, 0) as positive,
    if(return >= -0.006283662477558294 and return <= 0.0062893081761006275, 1, 0) as neutral
from 
    final_return
where
    -0.5 < return and return < 0.5 
    and TradeDate < '2025-01-01'