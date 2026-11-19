
-- step 0

drop table Lv_0;

-- step 1.

create or replace temp table Lv_0 as (
    select 
        cast(Date as date) as tradeDate,
        Code as code,
        O, H, L, C
    from syn.raw.idx_prc
    where Code in [
        '0040', '0041', '0042', '0043',  -- s33
        '0044', '0045', '0046', '0047',
        '0048', '0049', '004A', '004B',
        '004C', '004D', '004E', '004F',
        '0050', '0051', '0052', '0053',
        '0054', '0055', '0056', '0057',
        '0058', '0059', '005A', '005B',
        '005C', '005D', '005E', '005F',
        '0060', 
        '0080', '0081', '0082', '0083',  -- s17
        '0084', '0085', '0086', '0087',
        '0088', '0089', '008A', '008B',
        '008C', '008D', '008E', '008F',
        '0090',
        '0000', '0001', '0070', '0091',  -- TOPIX, 東証二部, マザーズ, JASDAQ
        '0500', '0501', '0502'           -- Prime, Standard, Growth
    ]
);

-- return Lv_0;

select count(*) - count(distinct (tradeDate, code)) as dup from Lv_0;

summarize select * from Lv_0;

select * from Lv_0 order by code, tradeDate;
