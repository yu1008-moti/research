# y を得るためのSQLクエリ

```sql
create or replace temp table ret as (
    with 
    shifted as(
        select 
            Code, 
            TradeDate, 
            lag(TradeDate, -1) over w as l1_TradeDate, 
            Mkt, 
            DAdjC,
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
            (l1_DAdjC/DAdjC -1) as return 
        from 
            shifted
    ),
    -- select 
    --     * 
    -- from 
    --     added_r 
    -- where not (isnan(return) or isinf(return)));

    modified_return as(
        select 
            * ,
            -- if(return is null, 0, return) as return,
            -- if(not (isnan(return) or isinf(return)), 1, 0) as is_valid
            case 
                when return is null then 0
                when isnan(return) is true then 0
                when isinf(return) is true then 0
                when return = 0 then 0
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
    ),

    final_return as(
        select 
            * exclude(is_valid)
        from 
            filtered_return
    )

    select 
        *
    from 
        final_return
);

-- ┌─────────┬────────────┬──────────────┬─────────┬──────────┬────────┬──────────────────────┬──────────┐
-- │  Code   │ TradeDate  │ l1_TradeDate │   Mkt   │ l1_DAdjC │ DAdjC  │        return        │ date_gap │
-- │ varchar │    date    │     date     │ varchar │  double  │ double │        double        │  int64   │
-- ├─────────┼────────────┼──────────────┼─────────┼──────────┼────────┼──────────────────────┼──────────┤
-- │ 50160   │ 2010-03-26 │ 2025-03-19   │ 0000    │    874.0 │  437.0 │                  1.0 │     5472 │
-- │ 17860   │ 2008-12-24 │ 2021-04-01   │ 0000    │    289.0 │    1.0 │                288.0 │     4481 │
-- │ 79440   │ 2014-10-24 │ 2020-12-16   │ 0000    │   2920.0 │ 1870.0 │   0.5614973262032086 │     2245 │
-- │ 87290   │ 2020-08-28 │ 2025-09-29   │ 0000    │    173.8 │ 2597.0 │   -0.933076626877166 │     1858 │
-- │ 68100   │ 2010-03-26 │ 2014-03-18   │ 0000    │   1790.0 │ 1869.0 │ -0.04226859283039053 │     1453 │
-- │ 57210   │ 2009-08-07 │ 2013-07-16   │ 0000    │     28.0 │   12.0 │   1.3333333333333335 │     1439 │
-- │ 83030   │ 2022-04-01 │ 2025-12-17   │ 0000    │   1623.0 │ 2275.0 │  -0.2865934065934066 │     1356 │
-- │ 65020   │ 2017-07-31 │ 2021-01-29   │ 0000    │   3415.0 │ 2460.0 │   0.3882113821138211 │     1278 │
-- │ 32509   │ 2017-09-05 │ 2019-07-11   │ 0000    │      6.0 │    1.0 │                  5.0 │      674 │
-- │ 67530   │ 2016-07-29 │ 2017-12-07   │ 0000    │   3805.0 │  920.0 │   3.1358695652173916 │      496 │
-- └─────────┴────────────┴──────────────┴─────────┴──────────┴────────┴──────────────────────┴──────────┘

-- update ret
-- set return = 0
-- where TradeDate = '2010-03-26' and Code = '50160';

-- update ret
-- set return = 0
-- where TradeDate = '2008-12-24' and Code = '17860';

-- update ret
-- set return = 0
-- where TradeDate = '2014-10-24' and Code = '79440';

-- update ret
-- set return = 0
-- where TradeDate = '2020-08-28' and Code = '87290';

-- update ret
-- set return = 0
-- where TradeDate = '2010-03-26' and Code = '68100';

-- update ret
-- set return = 0
-- where TradeDate = '2009-08-07' and Code = '57210';

-- update ret
-- set return = 0
-- where TradeDate = '2022-04-01' and Code = '83030';

-- update ret
-- set return = 0
-- where TradeDate = '2017-07-31' and Code = '65020';

-- update ret
-- set return = 0
-- where TradeDate = '2017-09-05' and Code = '32509';

-- update ret
-- set return = 0
-- where TradeDate = '2016-07-29' and Code = '67530';

delete from ret
where
    TradeDate = '2010-03-26' and Code = '50160';
delete from ret
where
    TradeDate = '2008-12-24' and Code = '17860';
delete from ret
where
    TradeDate = '2014-10-24' and Code = '79440';
delete from ret
where
    TradeDate = '2020-08-28' and Code = '87290';
delete from ret
where
    TradeDate = '2010-03-26' and Code = '68100';
delete from ret
where
    TradeDate = '2009-08-07' and Code = '57210';
delete from ret
where
    TradeDate = '2022-04-01' and Code = '83030';
delete from ret
where
    TradeDate = '2017-07-31' and Code = '65020';
delete from ret
where
    TradeDate = '2017-09-05' and Code = '32509';
delete from ret
where
    TradeDate = '2016-07-29' and Code = '67530';

-- more deeply adjusted data

-- 1.
-- Code = '86850': 
    -- 2009/06/25 ~ 2009/07/02 において謎のNULLが発生．
    -- さらに，調整済み株価に異常を確認

update ret
set 
    DAdjC = DAdjC * 10,
where
    TradeDate < '2009-07-03' and Code = '86850';

update ret
set 
    l1_DAdjC = l1_DAdjC * 10,
where
    TradeDate < '2009-07-02' and Code = '86850';

update ret
set
    return = (l1_DAdjC/DAdjC -1),
where
    Code = '86850';

-- syn D select substring(Code, 5, 1) as code_suffix, count(*) as c from raw.eqt_main group by code_suffix order by c;
-- ┌─────────────┬──────────┐
-- │ code_suffix │    c     │
-- │   varchar   │  int64   │
-- ├─────────────┼──────────┤
-- │ 1           │      293 │
-- │ 6           │      374 │
-- │ 9           │     1023 │
-- │ 5           │     5622 │
-- │ 0           │ 15685087 │
-- └─────────────┴──────────┘

-- なんか，「議決権種類株式」とやらが末尾に0以外の数字が付与されるらしい．
-- 5・6：優先株式・社債型株式として末尾5桁目に付与される．
-- 9：新株予約権証券
-- 1：普通新株式として末尾5桁目に付与される．
-- 1・9は，上場期間が極めて短命であり，除外対象としている．

-- 2.
-- Code = '85970': 
    -- 2009/02/25 において謎のNULLが発生．
    -- さらに，調整済み株価に異常を確認
        -- 2009年2月23日に、東京地方裁判所第20部へ民事再生法の適用を申請して受理された。負債総額は3380億4000万円。
        -- つまるところ，廃止されることが分かったのだが，調べたら正しい値動きをしていた．


-- syn D with
--       c_00 as(select substring(cast(TradeDate as varchar), 1, 4) as year,  count(*) as c from ret where return < -0.0 group by year order by c),
--       c_01 as(select substring(cast(TradeDate as varchar), 1, 4) as year,  count(*) as c from ret where return < -0.1 group by year order by c),
--       c_02 as(select substring(cast(TradeDate as varchar), 1, 4) as year,  count(*) as c from ret where return < -0.2 group by year order by c),
--       c_03 as(select substring(cast(TradeDate as varchar), 1, 4) as year,  count(*) as c from ret where return < -0.3 group by year order by c),
--       c_04 as(select substring(cast(TradeDate as varchar), 1, 4) as year,  count(*) as c from ret where return < -0.4 group by year order by c),
--       c_05 as(select substring(cast(TradeDate as varchar), 1, 4) as year,  count(*) as c from ret where return < -0.5 group by year order by c),
--       c_06 as(select substring(cast(TradeDate as varchar), 1, 4) as year,  count(*) as c from ret where return < -0.6 group by year order by c),
--       c_07 as(select substring(cast(TradeDate as varchar), 1, 4) as year,  count(*) as c from ret where return < -0.7 group by year order by c),
--       c_08 as(select substring(cast(TradeDate as varchar), 1, 4) as year,  count(*) as c from ret where return < -0.8 group by year order by c),
--       c_09 as(select substring(cast(TradeDate as varchar), 1, 4) as year,  count(*) as c from ret where return < -0.9 group by year order by c),
--       c_10 as(select substring(cast(TradeDate as varchar), 1, 4) as year,  count(*) as c from ret where return < -1.0 group by year order by c)
--       select 
--       c00.year as year,
--       c00.c as '-0.0', c01.c as '-0.1', c02.c as '-0.2', c03.c as '-0.3', c04.c as '-0.4', c05.c as '-0.5', c06.c as '-0.6', c07.c as '-0.7', c08.c as '-0.8', c09.c as '-0.9', c10.c as '-1.0'
--       from c_00 as c00
--       LEFT OUTER JOIN c_01 as c01 ON c00.year = c01.year
--       LEFT OUTER JOIN c_02 as c02 ON c00.year = c02.year
--       LEFT OUTER JOIN c_03 as c03 ON c00.year = c03.year
--       LEFT OUTER JOIN c_04 as c04 ON c00.year = c04.year
--       LEFT OUTER JOIN c_05 as c05 ON c00.year = c05.year
--       LEFT OUTER JOIN c_06 as c06 ON c00.year = c06.year
--       LEFT OUTER JOIN c_07 as c07 ON c00.year = c07.year
--       LEFT OUTER JOIN c_08 as c08 ON c00.year = c08.year
--       LEFT OUTER JOIN c_09 as c09 ON c00.year = c09.year
--       LEFT OUTER JOIN c_10 as c10 ON c00.year = c10.year
--       order by year;
-- ┌─────────┬────────┬───────┬───────┬───────┬───────┬───────┬───────┬───────┬───────┬───────┬───────┐
-- │  year   │  -0.0  │ -0.1  │ -0.2  │ -0.3  │ -0.4  │ -0.5  │ -0.6  │ -0.7  │ -0.8  │ -0.9  │ -1.0  │
-- │ varchar │ int64  │ int64 │ int64 │ int64 │ int64 │ int64 │ int64 │ int64 │ int64 │ int64 │ int64 │
-- ├─────────┼────────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┤
-- │ 2008    │ 144338 │  4668 │   154 │    40 │    20 │    10 │     9 │     8 │     5 │     2 │  NULL │
-- │ 2009    │ 197874 │  1225 │   111 │    57 │    24 │    11 │    10 │    10 │     9 │     6 │  NULL │
-- │ 2010    │ 190633 │   403 │    76 │    22 │    13 │     6 │     5 │     5 │     3 │     1 │  NULL │
-- │ 2011    │ 193366 │  2316 │   315 │    58 │    17 │     1 │     1 │     1 │     1 │     1 │  NULL │
-- │ 2012    │ 189829 │   354 │    32 │    18 │     7 │     4 │     3 │     3 │     3 │     3 │  NULL │
-- │ 2013    │ 194207 │   745 │    16 │     1 │     1 │     1 │  NULL │  NULL │  NULL │  NULL │  NULL │
-- │ 2014    │ 205766 │   356 │    18 │  NULL │  NULL │  NULL │  NULL │  NULL │  NULL │  NULL │  NULL │
-- │ 2015    │ 216369 │   469 │    28 │     7 │     4 │     3 │     3 │     3 │     3 │     1 │  NULL │
-- │ 2016    │ 223786 │   945 │    27 │     1 │  NULL │  NULL │  NULL │  NULL │  NULL │  NULL │  NULL │
-- │ 2017    │ 226497 │   434 │    25 │     7 │     4 │     3 │     2 │  NULL │  NULL │  NULL │  NULL │
-- │ 2018    │ 257954 │  1193 │    59 │     5 │     2 │     1 │     1 │     1 │     1 │     1 │  NULL │
-- │ 2019    │ 245315 │   610 │    37 │     3 │     1 │  NULL │  NULL │  NULL │  NULL │  NULL │  NULL │
-- │ 2020    │ 261131 │  1467 │    44 │     7 │     3 │     2 │  NULL │  NULL │  NULL │  NULL │  NULL │
-- │ 2021    │ 258573 │   491 │    26 │     2 │  NULL │  NULL │  NULL │  NULL │  NULL │  NULL │  NULL │
-- │ 2022    │ 229729 │   486 │    42 │     6 │     4 │     4 │     2 │     1 │  NULL │  NULL │  NULL │
-- │ 2023    │ 202664 │   410 │    39 │  NULL │  NULL │  NULL │  NULL │  NULL │  NULL │  NULL │  NULL │
-- │ 2024    │ 192249 │  1506 │    75 │  NULL │  NULL │  NULL │  NULL │  NULL │  NULL │  NULL │  NULL │
-- │ 2025    │ 180748 │   724 │    22 │     1 │     1 │     1 │     1 │     1 │  NULL │  NULL │  NULL │
-- │ 2026    │  50047 │   194 │     9 │     2 │     1 │  NULL │  NULL │  NULL │  NULL │  NULL │  NULL │
-- └─────────┴────────┴───────┴───────┴───────┴───────┴───────┴───────┴───────┴───────┴───────┴───────┘
--   19 rows                                                                               12 columns

create or replace temp table pl (
    p_std integer, p_lim integer
);

insert into pl values
(100-1, 30),
(200-1, 50),
(500-1, 80),
(700-1, 100),
(1000-1, 150),
(1500-1, 300),
(2000-1, 400),
(3000-1, 500),
(5000-1, 700),
(7000-1 , 1000),
(10000-1, 1500),
(15000-1, 3000),
(20000-1, 4000),
(30000-1, 5000),
(50000-1, 7000),
(70000-1, 10000),
(100000-1, 15000),
(150000-1, 30000),
(200000-1, 40000),
(300000-1, 50000),
(500000-1, 70000),
(700000-1, 100000),
(1000000-1, 150000),
(1500000-1, 300000),
(2000000-1, 400000),
(3000000-1, 500000),
(5000000-1, 700000),
(7000000-1, 1000000),
(10000000-1, 1500000),
(15000000-1, 3000000),
(20000000-1, 4000000),
(30000000-1, 5000000),
(50000000-1, 7000000),
(50000000-1, 10000000),

-- syn D select count(*) from imp.eqt_main;
-- ┌─────────────────┐
-- │  count_star()   │
-- │      int64      │
-- ├─────────────────┤
-- │    15538219     │
-- │ (15.54 million) │
-- └─────────────────┘

-- 理論上，return が ± 30 を超えることはあり得ないことが分かった．
-- 加えて，調整済み株価においても100未満で推移する銘柄は，リターンの偏りが大きい
-- 1.999225265134955 %のデータが，調整済み株価が100未満であった．
-- 0.0718679534636499 %のデータが，調整済み株価が10未満であった．

-- そもそも，正解ラベルは return の値そのものではなく，
-- pos/neu/neg の3値分類である．
-- とりあえず，±0.5については一度除外した上で，確率密度関数を再度確認する．


-- memory D select *,
--          (p_std_high+p_lim)/p_std_high -1 as up_high_stop_ratio,
--          (p_std_low+p_lim)/p_std_low -1 as up_low_stop_ratio,
--          (p_std_high-p_lim)/p_std_high -1 as down_high_stop_ratio,
--          (p_std_low-p_lim)/p_std_low -1 as down_low_stop_ratio
--          from pl;
-- ┌────────────┬───────────┬──────────┬─────────────────────┬─────────────────────┬──────────────────────┬──────────────────────┐
-- │ p_std_high │ p_std_low │  p_lim   │ up_high_stop_ratio  │  up_low_stop_ratio  │ down_high_stop_ratio │ down_low_stop_ratio  │
-- │   int32    │   int32   │  int32   │       double        │       double        │        double        │        double        │
-- ├────────────┼───────────┼──────────┼─────────────────────┼─────────────────────┼──────────────────────┼──────────────────────┤
-- │         99 │         1 │       30 │   0.303030303030303 │                30.0 │   -0.303030303030303 │                -30.0 │
-- │        199 │       100 │       50 │ 0.25125628140703515 │                 0.5 │ -0.25125628140703515 │                 -0.5 │
-- │        499 │       200 │       80 │ 0.16032064128256507 │  0.3999999999999999 │ -0.16032064128256518 │                 -0.4 │
-- │        699 │       500 │      100 │ 0.14306151645207432 │ 0.19999999999999996 │ -0.14306151645207443 │ -0.19999999999999996 │
-- │        999 │       700 │      150 │  0.1501501501501501 │  0.2142857142857142 │  -0.1501501501501501 │  -0.2142857142857143 │
-- │       1499 │      1000 │      300 │ 0.20013342228152098 │ 0.30000000000000004 │ -0.20013342228152098 │ -0.30000000000000004 │
-- │       1999 │      1500 │      400 │ 0.20010005002501252 │  0.2666666666666666 │ -0.20010005002501252 │  -0.2666666666666667 │
-- │       2999 │      2000 │      500 │ 0.16672224074691555 │                0.25 │ -0.16672224074691566 │                -0.25 │
-- │       4999 │      3000 │      700 │ 0.14002800560112028 │  0.2333333333333334 │ -0.14002800560112028 │ -0.23333333333333328 │
-- │       6999 │      5000 │     1000 │ 0.14287755393627655 │ 0.19999999999999996 │ -0.14287755393627666 │ -0.19999999999999996 │
-- │       9999 │      7000 │     1500 │    0.15001500150015 │  0.2142857142857142 │    -0.15001500150015 │  -0.2142857142857143 │
-- │      14999 │     10000 │     3000 │  0.2000133342222814 │ 0.30000000000000004 │  -0.2000133342222815 │ -0.30000000000000004 │
-- │      19999 │     15000 │     4000 │ 0.20001000050002493 │  0.2666666666666666 │ -0.20001000050002504 │  -0.2666666666666667 │
-- │      29999 │     20000 │     5000 │ 0.16667222240741353 │                0.25 │ -0.16667222240741353 │                -0.25 │
-- │      49999 │     30000 │     7000 │  0.1400028000560012 │  0.2333333333333334 │ -0.14000280005600108 │ -0.23333333333333328 │
-- │      69999 │     50000 │    10000 │  0.1428591837026243 │ 0.19999999999999996 │  -0.1428591837026243 │ -0.19999999999999996 │
-- │      99999 │     70000 │    15000 │ 0.15000150001500012 │  0.2142857142857142 │ -0.15000150001500012 │  -0.2142857142857143 │
-- │     149999 │    100000 │    30000 │ 0.20000133334222236 │ 0.30000000000000004 │ -0.20000133334222225 │ -0.30000000000000004 │
-- │     199999 │    150000 │    40000 │  0.2000010000050001 │  0.2666666666666666 │ -0.20000100000499998 │  -0.2666666666666667 │
-- │     299999 │    200000 │    50000 │ 0.16666722222407415 │                0.25 │ -0.16666722222407404 │                -0.25 │
-- │     499999 │    300000 │    70000 │ 0.14000028000055997 │  0.2333333333333334 │ -0.14000028000055997 │ -0.23333333333333328 │
-- │     699999 │    500000 │   100000 │ 0.14285734693906704 │ 0.19999999999999996 │ -0.14285734693906704 │ -0.19999999999999996 │
-- │     999999 │    700000 │   150000 │    0.15000015000015 │  0.2142857142857142 │    -0.15000015000015 │  -0.2142857142857143 │
-- │    1499999 │   1000000 │   300000 │ 0.20000013333342226 │ 0.30000000000000004 │ -0.20000013333342226 │ -0.30000000000000004 │
-- │    1999999 │   1500000 │   400000 │ 0.20000010000004997 │  0.2666666666666666 │ -0.20000010000004997 │  -0.2666666666666667 │
-- │    2999999 │   2000000 │   500000 │ 0.16666672222224066 │                0.25 │ -0.16666672222224077 │                -0.25 │
-- │    4999999 │   3000000 │   700000 │ 0.14000002800000555 │  0.2333333333333334 │ -0.14000002800000555 │ -0.23333333333333328 │
-- │    6999999 │   5000000 │  1000000 │ 0.14285716326530906 │ 0.19999999999999996 │ -0.14285716326530906 │ -0.19999999999999996 │
-- │    9999999 │   7000000 │  1500000 │  0.1500000150000016 │  0.2142857142857142 │ -0.15000001500000149 │  -0.2142857142857143 │
-- │   14999999 │  10000000 │  3000000 │ 0.20000001333333417 │ 0.30000000000000004 │ -0.20000001333333417 │ -0.30000000000000004 │
-- │   19999999 │  15000000 │  4000000 │ 0.20000001000000056 │  0.2666666666666666 │ -0.20000001000000045 │  -0.2666666666666667 │
-- │   29999999 │  20000000 │  5000000 │  0.1666666722222223 │                0.25 │ -0.16666667222222242 │                -0.25 │
-- │   49999999 │  30000000 │  7000000 │ 0.14000000280000013 │  0.2333333333333334 │ -0.14000000280000002 │ -0.23333333333333328 │
-- │   49999999 │  50000000 │ 10000000 │ 0.20000000400000006 │ 0.19999999999999996 │ -0.20000000400000006 │ -0.19999999999999996 │
-- └────────────┴───────────┴──────────┴─────────────────────┴─────────────────────┴──────────────────────┴──────────────────────┘
--   34 rows                                                                                                           7 columns
```