select *
from (
    select
        substring(CM, 3, 2) || substring(Code, 4, 2) as Code,
        -- ProdCat,
        cast(Date as date) as TradeDate,
        O, H, L, C,
        AO, AH, AL, AC,
        Vo, OI, Va, VoOA,
        EmMrgnTrgDiv,
        LTD,
        Settle,
        CCMFlag
    from 
        raw.drv_ftr
    where
        ProdCat = 'TOPIXF'
)
where
    '$start_date' <= TradeDate and TradeDate <= '$end_date'