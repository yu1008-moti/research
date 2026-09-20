-- SET threads = 1;

/*
CREATE OR REPLACE TEMP MACRO _isinfORnan(x) AS(
    isinf(x) OR isnan(x)
);
*/

CREATE OR REPLACE TEMP MACRO Cast2Date(x) AS(
    CAST(x AS Date)
);

CREATE OR REPLACE TEMP MACRO isExist(x) AS(
    IF(x IS NULL, 0, 1)
);

CREATE OR REPLACE TEMP MACRO CalcRatio(x, y) AS(
    -- IF(_isinfORnan(x/y), 0, x/y)
    -- x/y
    IF(x*y = 0, 0, x/y)

);

CREATE OR REPLACE TEMP MACRO ffill(x, w, Code, CurFYEn, CurPerType, DiscDate) AS(
    CASE
        WHEN w = '*' THEN COALESCE(x, LAST_VALUE(x IGNORE NULLS) OVER (PARTITION BY Code, CurPerType ORDER BY DiscDate ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), -- 1st: Quarterly WINDOW
                                      LAST_VALUE(x IGNORE NULLS) OVER (PARTITION BY Code, CurFYEn    ORDER BY DiscDate ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), -- 2nd: Yearly WINDOW 
                                      LAST_VALUE(x IGNORE NULLS) OVER (PARTITION BY Code             ORDER BY DiscDate ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) -- 3rd: All Range WINDOW
        WHEN w = 'Y' THEN COALESCE(x, LAST_VALUE(x IGNORE NULLS) OVER (PARTITION BY Code, CurFYEn    ORDER BY DiscDate ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) -- Yearly WINDOW
        WHEN w = 'Q' THEN COALESCE(x, LAST_VALUE(x IGNORE NULLS) OVER (PARTITION BY Code, CurPerType ORDER BY DiscDate ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) -- Quarterly WINDOW
        WHEN w = 'A' THEN COALESCE(x, LAST_VALUE(x IGNORE NULLS) OVER (PARTITION BY Code             ORDER BY DiscDate ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) -- All Range WINDOW
    END
);

CREATE OR REPLACE TEMP MACRO getLag(x, w, Code, CurFYEn, CurPerType, DiscDate) AS(
    CASE
        WHEN w = 'Y' THEN LAG(x) OVER (PARTITION BY Code, CurFYEn    ORDER BY DiscDate ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) -- Yearly WINDOW
        WHEN w = 'Q' THEN LAG(x) OVER (PARTITION BY Code, CurPerType ORDER BY DiscDate ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) -- Quarterly WINDOW
        WHEN w = 'A' THEN LAG(x) OVER (PARTITION BY Code             ORDER BY DiscDate ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) -- All Range WINDOW
        WHEN w = 'S' THEN LAG(x) OVER (PARTITION BY Code             ORDER BY DiscDate                                                 ) -- Simple WINDOW
    END
);

CREATE OR REPLACE TEMP MACRO myLog(x) AS(
  CASE
    WHEN x > 0 THEN  LOG( x)
    WHEN x < 0 THEN -LOG(-x)
    WHEN x = 0 THEN 0
  END
);

CREATE OR REPLACE TABLE fin_sum_tmp AS
    WITH 
    ini AS(
        SELECT 

            Cast2Date(DiscDate) AS DiscDate, 
            Cast2Date(CurFYEn) AS CurFYEn,
            Code, CurPerType,
            Cast2Date(CurPerSt) AS CurPerSt, 
            Cast2Date(CurPerEn) AS CurPerEn,

            * EXCLUDE(DiscDate, CurFYEn, Code, CurPerType, CurPerSt, CurPerEn),

            COALESCE(
                LAG(CAST(DiscDate AS Date)) OVER (PARTITION BY Code ORDER BY DiscDate), 
                CAST(DiscDate AS Date) - 90 /* Approx. 1Q total days length */
            ) AS L_DiscDate,
            CAST(DiscDate AS DATE) - CAST(CurPerEn AS DATE) AS gap_DiscDate_CurPerEn
    
    
        FROM fin_sum
        WHERE
            CurPerType NOT IN ('4Q', '5Q') AND CurPerType IS NOT NULL AND
            REGEXP_MATCHES(DocType, '([1-4]Q|FY)FinancialStatements_Consolidated_JP')
        ORDER BY Code, DiscDate, CurPerEn
    ),

    base AS(
        SELECT * EXClUDE(L_DiscDate, gap_DiscDate_CurPerEn)
        FROM ini
        WHERE 
            DiscDate - L_DiscDate > 60 AND
            (0 < gap_DiscDate_CurPerEn AND gap_DiscDate_CurPerEn < 60)
        ORDER BY Code, DiscDate, CurPerEn

    ),

    EasyRepl AS(
        SELECT 

            DiscDate, Code, 
            CurFYEn, CurPerType,
            
            COALESCE(CFO,    0) AS CFO_tmp, 
            COALESCE(CFI,    0) AS CFI_tmp, 
            COALESCE(CFF,    0) AS CFF_tmp, 
            COALESCE(CashEq, 0) AS CashEq_tmp, 
            
            COALESCE(FDiv1Q, NxFDiv1Q) AS FDiv1Q_tmp,
            COALESCE(FDiv2Q, NxFDiv2Q) AS FDiv2Q_tmp,
            COALESCE(FDiv3Q, NxFDiv3Q) AS FDiv3Q_tmp,
            COALESCE(FDivFY, NxFDivFY) AS FDivFY_tmp,
        
        FROM base
    ),

    isExistBinary AS(
        SELECT 
            
            DiscDate, Code, 
            CurFYEn, CurPerType,

            isExist(Eq) AS Exist_Eq,
            isExist(TA) AS Exist_TA,

            isExist(Sales) AS Exist_Sales,
            isExist(OP)    AS Exist_OP,
            isExist(OdP)   AS Exist_OdP,
            isExist(NP)    AS Exist_NP,

            isExist(ShOutFY) AS Exist_IsSh,
            isExist(TrShFY)  AS Exist_TrSh,
            
            isExist(CFO + CFI + CFF + CashEq) AS ExistCF,

        FROM base
    ),

    ForwardFill_pre AS(
        SELECT

            DiscDate, Code, CurFYEn, CurPerType,

            ffill(TA, '*', Code, CurFYEn, CurPerType, DiscDate) AS TA_tmp,
            ffill(Eq, '*', Code, CurFYEn, CurPerType, DiscDate) AS Eq_tmp

        FROM base
    ),

    ForwardFill AS(
        SELECT 

            b.DiscDate, b.Code,
            b.CurFYEn, b.CurPerType, 
            
            ffill(b.Sales,      '*', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS Sales_tmp, 
            ffill(b.OP,         '*', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS OP_tmp,
            ffill(b.OdP,        '*', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS OdP_tmp,
            ffill(b.NP,         '*', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS NP_tmp,
            
            ffill(b.ShOutFY,    '*', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS IsSh_tmp,
            ffill(b.TrShFY,     '*', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS TrSh_tmp,
            
            ffill((COALESCE(b.EqAR, CalcRatio(fp.Eq_tmp, fp.TA_tmp), 0)), 'A', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS EqAR_tmp,

            ffill(e.FDiv1Q_tmp, 'Q', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS FDiv1Q_tmp,
            ffill(e.FDiv2Q_tmp, 'Q', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS FDiv2Q_tmp,
            ffill(e.FDiv3Q_tmp, 'Q', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS FDiv3Q_tmp,
            ffill(e.FDivFY_tmp, 'Q', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS FDivFY_tmp,

            ffill(b.FSales,     '*', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS FSales_tmp,
            ffill(b.FOP,        '*', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS FOP_tmp,
            ffill(b.FOdP,       '*', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS FOdP_tmp,
            ffill(b.FNP,        '*', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS FNP_tmp,
            ffill(b.FEPS,       '*', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS FEPS_tmp,
        
        FROM base b
        JOIN EasyRepl e
            USING(DiscDate, Code, CurFYEn, CurPerType)
        JOIN ForwardFill_pre fp
            USING(DiscDate, Code, CurFYEn, CurPerType)
    ),

    ReallyGain AS(
        SELECT 
            
            b.DiscDate, b.Code,
            b.CurFYEn, b.CurPerType,

            f.Sales_tmp - COALESCE(getLag(f.Sales_tmp, 'Y', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate), 0) AS Sales_ReallyGain_tmp,
            f.OP_tmp    - COALESCE(getLag(f.OP_tmp,    'Y', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate), 0) AS    OP_ReallyGain_tmp,
            f.OdP_tmp   - COALESCE(getLag(f.OdP_tmp,   'Y', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate), 0) AS   OdP_ReallyGain_tmp,
            f.NP_tmp    - COALESCE(getLag(f.NP_tmp,    'Y', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate), 0) AS    NP_ReallyGain_tmp,

        
        FROM base b
        JOIN ForwardFill f
            USING(DiscDate, Code, CurFYEn, CurPerType)
    ),

    PreQ_Vals AS(
        SELECT 
            
            b.DiscDate, b.Code, 
            b.CurFYEn, b.CurPerType,

            getLag(fp.TA_tmp, 'S', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS TA_preQ,
            getLag(fp.Eq_tmp, 'S', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS Eq_preQ,

            /* lysQ：昨年同期の値を格納している */

            getLag(g.Sales_ReallyGain_tmp, 'Q', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS Sales_ReallyGain_lysQ_tmp,
            getLag(   g.OP_ReallyGain_tmp, 'Q', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS    OP_ReallyGain_lysQ_tmp,
            getLag(  g.OdP_ReallyGain_tmp, 'Q', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS   OdP_ReallyGain_lysQ_tmp,
            getLag(   g.NP_ReallyGain_tmp, 'Q', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS    NP_ReallyGain_lysQ_tmp,

            /* preQ：前四半期の成長率を格納している */

            getLag(g.Sales_ReallyGain_tmp, 'S', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS Sales_ReallyGain_preQ_tmp,
            getLag(   g.OP_ReallyGain_tmp, 'S', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS    OP_ReallyGain_preQ_tmp,
            getLag(  g.OdP_ReallyGain_tmp, 'S', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS   OdP_ReallyGain_preQ_tmp,
            getLag(   g.NP_ReallyGain_tmp, 'S', b.Code, b.CurFYEn, b.CurPerType, b.DiscDate) AS    NP_ReallyGain_preQ_tmp,

            COALESCE(LAST_VALUE(b.FDiv1Q IGNORE NULLS) OVER (PARTITION BY b.Code, b.CurPerType ORDER BY b.DiscDate ROWS BETWEEN 1 PRECEDING AND CURRENT ROW), 0) AS FDiv1Q_tmp,
            COALESCE(LAST_VALUE(b.FDiv2Q IGNORE NULLS) OVER (PARTITION BY b.Code, b.CurPerType ORDER BY b.DiscDate ROWS BETWEEN 1 PRECEDING AND CURRENT ROW), 0) AS FDiv2Q_tmp,
            COALESCE(LAST_VALUE(b.FDiv3Q IGNORE NULLS) OVER (PARTITION BY b.Code, b.CurPerType ORDER BY b.DiscDate ROWS BETWEEN 1 PRECEDING AND CURRENT ROW), 0) AS FDiv3Q_tmp,
            COALESCE(LAST_VALUE(b.FDivFY IGNORE NULLS) OVER (PARTITION BY b.Code, b.CurPerType ORDER BY b.DiscDate ROWS BETWEEN 1 PRECEDING AND CURRENT ROW), 0) AS FDivFY_tmp,

        FROM base b
        JOIN ForwardFill_pre fp
            USING(DiscDate, Code, CurFYEn, CurPerType)
        JOIN ReallyGain g
            USING(DiscDate, Code, CurFYEn, CurPerType)
    ),

    calculated AS(
        SELECT 

            b.DiscDate, b.Code,
            b.CurFYEn, b.CurPerType,

            -- 売上高に対する割合
            CalcRatio( f.OP_tmp , f.Sales_tmp) AS  OP_Rate,
            CalcRatio(f.OdP_tmp , f.Sales_tmp) AS OdP_Rate,
            CalcRatio( f.NP_tmp , f.Sales_tmp) AS  NP_Rate,

            -- 成長率
            CalcRatio(g.Sales_ReallyGain_tmp - p.Sales_ReallyGain_preQ_tmp, ABS(p.Sales_ReallyGain_preQ_tmp)) AS Sales_ReallyGain_VSpreQ_GrowthRatio,
            CalcRatio(   g.OP_ReallyGain_tmp -    p.OP_ReallyGain_preQ_tmp, ABS(   p.OP_ReallyGain_preQ_tmp)) AS    OP_ReallyGain_VSpreQ_GrowthRatio,
            CalcRatio(  g.OdP_ReallyGain_tmp -   p.OdP_ReallyGain_preQ_tmp, ABS(  p.OdP_ReallyGain_preQ_tmp)) AS   OdP_ReallyGain_VSpreQ_GrowthRatio,
            CalcRatio(   g.NP_ReallyGain_tmp -    p.NP_ReallyGain_preQ_tmp, ABS(   p.NP_ReallyGain_preQ_tmp)) AS    NP_ReallyGain_VSpreQ_GrowthRatio,
 
            -- 昨年同期比
            CalcRatio(g.Sales_ReallyGain_tmp - p.Sales_ReallyGain_lysQ_tmp, ABS(p.Sales_ReallyGain_lysQ_tmp)) AS Sales_ReallyGain_VSlysQ_GrowthRatio,
            CalcRatio(   g.OP_ReallyGain_tmp -    p.OP_ReallyGain_lysQ_tmp, ABS(   p.OP_ReallyGain_lysQ_tmp)) AS    OP_ReallyGain_VSlysQ_GrowthRatio,
            CalcRatio(  g.OdP_ReallyGain_tmp -   p.OdP_ReallyGain_lysQ_tmp, ABS(  p.OdP_ReallyGain_lysQ_tmp)) AS   OdP_ReallyGain_VSlysQ_GrowthRatio,
            CalcRatio(   g.NP_ReallyGain_tmp -    p.NP_ReallyGain_lysQ_tmp, ABS(   p.NP_ReallyGain_lysQ_tmp)) AS    NP_ReallyGain_VSlysQ_GrowthRatio,

            -- 達成率
            CalcRatio(f.Sales_tmp - f.FSales_tmp, ABS(f.FSales_tmp)) AS Sales_AchievementRatio,
            CalcRatio(   f.OP_tmp -    f.FOP_tmp, ABS(   f.FOP_tmp)) AS    OP_AchievementRatio,
            CalcRatio(  f.OdP_tmp -   f.FOdP_tmp, ABS(  f.FOdP_tmp)) AS   OdP_AchievementRatio,
            CalcRatio(   f.NP_tmp -    f.FNP_tmp, ABS(   f.FNP_tmp)) AS    NP_AchievementRatio,

            CalcRatio(fp.TA_tmp, p.TA_preQ) AS TA_GrowthRatio,
            CalcRatio(fp.Eq_tmp, p.Eq_preQ) AS Eq_GrowthRatio,
            CalcRatio(f.TrSh_tmp, f.IsSh_tmp) AS Sh_Ratio,

        FROM base b
        JOIN ForwardFill f
            USING(DiscDate, Code, CurFYEn, CurPerType)
        JOIN ForwardFill_pre fp
            USING(DiscDate, Code, CurFYEn, CurPerType)
        JOIN ReallyGain g
            USING(DiscDate, Code, CurFYEn, CurPerType)
        JOIN PreQ_Vals p
            USING(DiscDate, Code, CurFYEn, CurPerType)
    ),

    SimpleQuery AS(
        SELECT 

            b.DiscDate, b.Code,
            b.CurFYEn, b.CurPerType,

            CASE 
                WHEN b.CurPerType = '1Q' THEN COALESCE(p.FDiv1Q_tmp, b.NxFDiv1Q)
                WHEN b.CurPerType = '2Q' THEN COALESCE(p.FDiv2Q_tmp, b.NxFDiv2Q)
                WHEN b.CurPerType = '3Q' THEN COALESCE(p.FDiv3Q_tmp, b.NxFDiv3Q)
                WHEN b.CurPerType = 'FY' THEN COALESCE(p.FDivFY_tmp, b.NxFDivFY)
            ELSE 0
            END AS FDivNxQ,

            CASE
                WHEN b.CurPerType = '1Q' THEN COALESCE(b.Div1Q, 0)
                WHEN b.CurPerType = '2Q' THEN COALESCE(b.Div2Q, 0)
                WHEN b.CurPerType = '3Q' THEN COALESCE(b.Div3Q, 0)
                WHEN b.CurPerType = 'FY' THEN COALESCE(b.DivFY, 0)
            ELSE 0
            END AS Div,

            myLog(COALESCE(
                b.EPS, 
                CalcRatio(fp.Eq_tmp, f.IsSh_tmp - f.TrSh_tmp),
                CalcRatio(fp.Eq_tmp, f.IsSh_tmp)
            )) AS log_EPS,
            
            myLog(COALESCE(
                b.BPS, 
                CalcRatio(fp.Eq_tmp, f.IsSh_tmp - f.TrSh_tmp),
                CalcRatio(fp.Eq_tmp, f.IsSh_tmp)
            )) AS log_BPS,

            CASE
                WHEN b.DivAnn IS NULL THEN COALESCE(SUM(Div) OVER (PARTITION BY b.Code, b.CurFYEn ORDER BY b.DiscDate), 0)
            ELSE b.DivAnn
            END AS DivAnn,

            myLog(e.CFO_tmp + e.CFI_tmp) AS log_FCF,

            myLog(f.Sales_tmp) AS log_Sales,
            myLog(f.OP_tmp) AS log_OP,
            myLog(f.OdP_tmp) AS log_OdP,
            myLog(f.NP_tmp) AS log_NP,

            myLog(f.FSales_tmp) AS log_FSales,
            myLog(f.FOP_tmp) AS log_FOP,
            myLog(f.FOdP_tmp) AS log_FOdP,
            myLog(f.FNP_tmp) AS log_FNP,
            myLog(f.FEPS_tmp) AS log_FEPS,

            myLog(fp.TA_tmp) AS log_TA,
            myLog(fp.Eq_tmp) AS log_Eq,

            myLog(e.CashEq_tmp) AS log_CashEq,
            myLog(f.EqAR_tmp) AS log_EqAR,
            myLog(e.CFO_tmp) AS log_CFO,
            myLog(e.CFI_tmp) AS log_CFI,
            myLog(e.CFF_tmp) AS log_CFF,

            myLog(f.IsSh_tmp) AS log_IsSh,
            myLog(f.TrSh_tmp) AS log_TrSh,

            myLog(r.Sales_ReallyGain_tmp) AS log_Sales_ReallyGain,
            myLog(r.OP_ReallyGain_tmp) AS log_OP_ReallyGain,
            myLog(r.OdP_ReallyGain_tmp) AS log_OdP_ReallyGain,
            myLog(r.NP_ReallyGain_tmp) AS log_NP_ReallyGain,

            myLog(c.OP_Rate) AS log_OP_Rate,
            myLog(c.OdP_Rate) AS log_OdP_Rate,
            myLog(c.NP_Rate) AS log_NP_Rate,

            myLog(c.Sales_ReallyGain_VSpreQ_GrowthRatio) AS log_Sales_ReallyGain_VSpreQ_GrowthRatio,
            myLog(c.OP_ReallyGain_VSpreQ_GrowthRatio) AS log_OP_ReallyGain_VSpreQ_GrowthRatio,
            myLog(c.OdP_ReallyGain_VSpreQ_GrowthRatio) AS log_OdP_ReallyGain_VSpreQ_GrowthRatio,
            myLog(c.NP_ReallyGain_VSpreQ_GrowthRatio) AS log_NP_ReallyGain_VSpreQ_GrowthRatio,

            myLog(c.Sales_ReallyGain_VSlysQ_GrowthRatio) AS log_Sales_ReallyGain_VSlysQ_GrowthRatio,
            myLog(c.OP_ReallyGain_VSlysQ_GrowthRatio) AS log_OP_ReallyGain_VSlysQ_GrowthRatio,
            myLog(c.OdP_ReallyGain_VSlysQ_GrowthRatio) AS log_OdP_ReallyGain_VSlysQ_GrowthRatio,
            myLog(c.NP_ReallyGain_VSlysQ_GrowthRatio) AS log_NP_ReallyGain_VSlysQ_GrowthRatio,

            myLog(c.Sales_AchievementRatio) AS log_Sales_AchievementRatio,
            myLog(c.OP_AchievementRatio) AS log_OP_AchievementRatio,
            myLog(c.OdP_AchievementRatio) AS log_OdP_AchievementRatio,
            myLog(c.NP_AchievementRatio) AS log_NP_AchievementRatio,

            myLog(c.TA_GrowthRatio) AS log_TA_GrowthRatio,
            myLog(c.Eq_GrowthRatio) AS log_Eq_GrowthRatio,
            myLog(c.Sh_Ratio) AS log_Sh_Ratio,

            myLog(g.Sales_ReallyGain_tmp) AS log_Sales_ReallyGain_tmp,
            myLog(g.OP_ReallyGain_tmp) AS log_OP_ReallyGain_tmp,
            myLog(g.OdP_ReallyGain_tmp) AS log_OdP_ReallyGain_tmp,
            myLog(g.NP_ReallyGain_tmp) AS log_NP_ReallyGain_tmp,


        FROM base b
        JOIN PreQ_Vals p
            USING(DiscDate, Code, CurFYEn, CurPerType)
        JOIN EasyRepl e
            USING(DiscDate, Code, CurFYEn, CurPerType)
        JOIN ForwardFill f
            USING(DiscDate, Code, CurFYEn, CurPerType)
        JOIN ForwardFill_pre fp
            USING(DiscDate, Code, CurFYEn, CurPerType)
        JOIN ReallyGain r
            USING(DiscDate, Code, CurFYEn, CurPerType)
        JOIN Calculated c
            USING(DiscDate, Code, CurFYEn, CurPerType)
        JOIN ReallyGain g
            USING(DiscDate, Code, CurFYEn, CurPerType)
    ),

    Aggr AS(
        SELECT 
            s.DiscDate, s.Code, s.CurFYEn, s.CurPerType,
            s.* EXCLUDE(DiscDate, Code, CurFYEn, CurPerType),
            b.* EXCLUDE(DiscDate, Code, CurFYEn, CurPerType),
        FROM SimpleQuery s
        JOIN isExistBinary b
            USING(DiscDate, Code, CurFYEn, CurPerType)
    ),

    GetNULLFlag AS(
        SELECT 
            DiscDate, Code, CurFYEn, CurPerType,
            LIST_REDUCE(LIST_VALUE(* COLUMNS(* EXCLUDE(DiscDate, Code, CurFYEn, CurPerType))), (x, y) -> x + y) AS all_sum
        FROM Aggr
    ),
    
    fill_NULL_BY_ZERO AS(
        SELECT
            DiscDate,
            Code,
            CurPerType,
            CurFYEn,

            -- Profit Ratio
            COALESCE(log_OP_Rate, 0) AS log_OP_Rate,
            COALESCE(log_OdP_Rate, 0) AS log_OdP_Rate,
            COALESCE(log_NP_Rate, 0) AS log_NP_Rate,

            -- Sales
            COALESCE(log_Sales, 0) AS log_Sales,
            COALESCE(log_Sales_ReallyGain_VSpreQ_GrowthRatio, 0) AS log_Sales_ReallyGain_VSpreQ_GrowthRatio,
            COALESCE(log_Sales_ReallyGain_VSlysQ_GrowthRatio, 0) AS log_Sales_ReallyGain_VSlysQ_GrowthRatio,
            COALESCE(log_Sales_AchievementRatio, 0) AS log_Sales_AchievementRatio,
            COALESCE(log_FSales, 0) AS log_FSales,
            COALESCE(log_Sales_ReallyGain, 0) AS log_Sales_ReallyGain,
            COALESCE(Exist_Sales, 0) AS Exist_Sales,

            -- OP
            COALESCE(log_OP, 0) AS log_OP,
            COALESCE(log_OP_ReallyGain_VSpreQ_GrowthRatio, 0) AS log_OP_ReallyGain_VSpreQ_GrowthRatio,
            COALESCE(log_OP_ReallyGain_VSlysQ_GrowthRatio, 0) AS log_OP_ReallyGain_VSlysQ_GrowthRatio,
            COALESCE(log_OP_AchievementRatio, 0) AS log_OP_AchievementRatio,
            COALESCE(log_FOP, 0) AS log_FOP,
            COALESCE(log_OP_ReallyGain, 0) AS log_OP_ReallyGain,
            COALESCE(Exist_OP, 0) AS Exist_OP,

            -- OdP
            COALESCE(log_OdP, 0) AS log_OdP,
            COALESCE(log_OdP_ReallyGain_VSpreQ_GrowthRatio, 0) AS log_OdP_ReallyGain_VSpreQ_GrowthRatio,
            COALESCE(log_OdP_ReallyGain_VSlysQ_GrowthRatio, 0) AS log_OdP_ReallyGain_VSlysQ_GrowthRatio,
            COALESCE(log_OdP_AchievementRatio, 0) AS log_OdP_AchievementRatio,
            COALESCE(log_FOdP, 0) AS log_FOdP,
            COALESCE(log_OdP_ReallyGain, 0) AS log_OdP_ReallyGain,
            COALESCE(Exist_OdP, 0) AS Exist_OdP,

            -- NP
            COALESCE(log_NP, 0) AS log_NP,
            COALESCE(log_NP_ReallyGain_VSpreQ_GrowthRatio, 0) AS log_NP_ReallyGain_VSpreQ_GrowthRatio,
            COALESCE(log_NP_ReallyGain_VSlysQ_GrowthRatio, 0) AS log_NP_ReallyGain_VSlysQ_GrowthRatio,
            COALESCE(log_NP_AchievementRatio, 0) AS log_NP_AchievementRatio,
            COALESCE(log_FNP, 0) AS log_FNP,
            COALESCE(log_NP_ReallyGain, 0) AS log_NP_ReallyGain,
            COALESCE(Exist_NP, 0) AS Exist_NP,
            
            -- Balance Sheet TA
            COALESCE(log_TA_GrowthRatio, 0) AS log_TA_GrowthRatio,
            COALESCE(log_TA, 0) AS log_TA,
            COALESCE(Exist_TA, 0) AS Exist_TA,

            -- Balance Sheet Eq
            COALESCE(log_Eq_GrowthRatio, 0) AS log_Eq_GrowthRatio,
            COALESCE(log_Eq, 0) AS log_Eq,
            COALESCE(Exist_Eq, 0) AS Exist_Eq,

            -- Share Div
            COALESCE(Div, 0) AS Div,
            COALESCE(FDivNxQ, 0) AS FDiv,
            COALESCE(DivAnn, 0) AS DivAnn,

            -- Share quantity
            -- COALESCE(log_Sh_Ratio, 0) AS Sh_Ratio,
            COALESCE(log_IsSh, 0) AS log_IsSh,
            COALESCE(Exist_IsSh, 0) AS Exist_IsSh,
            COALESCE(log_TrSh, 0) AS log_TrSh,
            COALESCE(Exist_TrSh, 0) AS Exist_TrSh,
            
            -- Indicator
            COALESCE(log_EPS, 0) AS log_EPS,
            COALESCE(log_FEPS, 0) AS log_FEPS,
            COALESCE(log_BPS, 0) AS log_BPS,
            COALESCE(log_EqAR, 0) AS log_EqAR,

            -- Cash Flow
            COALESCE(log_FCF, 0) AS log_FCF,
            COALESCE(log_CFO, 0) AS log_CFO,
            COALESCE(log_CFI, 0) AS log_CFI,
            COALESCE(log_CFF, 0) AS log_CFF,
            COALESCE(log_CashEq, 0) AS log_CashEq,
            COALESCE(ExistCF, 0) AS ExistCF,

            IF(nf.all_sum IS NULL, 1, 0) AS NULL_Flag

        FROM Aggr
        JOIN GetNULLFlag nf
            USING(DiscDate, Code, CurFYEn, CurPerType)
    )

    SELECT * FROM fill_NULL_BY_ZERO
