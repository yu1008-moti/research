select 
    TradeDate, Code, 
    MAdjO, MAdjH, MAdjL, MAdjC, MUpL, MLoL, 
    AAdjO, AAdjH, AAdjL, AAdjC, AUpL, ALoL, 
    AdjVo, Mrgn, 
    S33, S17, Mkt 
from 
    imp.eqt_main 
where 
    -- Mkt='0000' and
    '$start_date' <= TradeDate and TradeDate <= '$end_date'