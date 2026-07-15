CREATE OR REPLACE TABLE fin_sum_tmp AS
    WITH 
    p1_base AS(
        SELECT 

            ------------------------------------------------------------------------------------------------------------------------
            -- meta information
            ------------------------------------------------------------------------------------------------------------------------
            
            CAST(DiscDate AS Date) AS DiscDate, 
            Code, 
            CurPerType,
            LAG(CAST(DiscDate AS Date)) OVER (PARTITION BY Code ORDER BY DiscDate) AS L_DiscDate,
            CAST(CurPerSt AS Date) AS CurPerSt,
            CAST(CurPerEn AS Date) AS CurPerEn,

            ------------------------------------------------------------------------------------------------------------------------
            -- Balance-Sheet Value
            ------------------------------------------------------------------------------------------------------------------------

            COALESCE(TA, LAST_VALUE(TA) OVER Yearly_w, LAST_VALUE(TA) OVER Quarterly_w) AS pre_TA, 
            COALESCE(Eq, LAST_VALUE(Eq) OVER Yearly_w, LAST_VALUE(Eq) OVER Quarterly_w) AS pre_Eq, 

            ------------------------------------------------------------------------------------------------------------------------
            -- Profit-Loss Values
            ------------------------------------------------------------------------------------------------------------------------
            
            COALESCE(Sales, LAST_VALUE(Sales IGNORE NULLS) OVER Yearly_w, 0) AS Sales, 
            COALESCE(OP     , LAST_VALUE(OP    IGNORE NULLS) OVER Yearly_w, 0) AS OprP,
            COALESCE(OdP    , LAST_VALUE(OdP     IGNORE NULLS) OVER Yearly_w, 0) AS OrdP,
            COALESCE(NP     , LAST_VALUE(NP    IGNORE NULLS) OVER Yearly_w, 0) AS NetP,

            ------------------------------------------------------------------------------------------------------------------------
            -- stock-numbers information
            ------------------------------------------------------------------------------------------------------------------------
            
            COALESCE(
            ShOutFY,
            LAST_VALUE(ShOutFY IGNORE NULLS) OVER Yearly_w,
            LAST_VALUE(ShOutFY IGNORE NULLS) OVER Quarterly_w
            ) AS pre_IsSh,
            
            COALESCE(
            TrShFY, 
            LAST_VALUE(TrShFY    IGNORE NULLS) OVER Yearly_w,
            LAST_VALUE(TrShFY    IGNORE NULLS) OVER Quarterly_w,
            ) AS pre_TrSh,

            ------------------------------------------------------------------------------------------------------------------------
            -- perShares Values
            ------------------------------------------------------------------------------------------------------------------------
            
            COALESCE(EPS, NetP/(pre_IsSh-pre_TrSh), Eq/(pre_IsSh)) AS EPS, 
            
            COALESCE(BPS, Eq/(pre_IsSh-pre_TrSh)    , Eq/(pre_IsSh)) AS BPS,

            ------------------------------------------------------------------------------------------------------------------------
            -- dividened Values
            ------------------------------------------------------------------------------------------------------------------------
            
            CASE
            WHEN CurPerType = '1Q' THEN COALESCE(Div1Q, 0)
            WHEN CurPerType = '2Q' THEN COALESCE(Div2Q, 0)
            WHEN CurPerType = '3Q' THEN COALESCE(Div3Q, 0)
            WHEN CurPerType = 'FY' THEN COALESCE(DivFY, 0)
            ELSE 0
            END AS Div,
            CASE
            WHEN DivAnn IS NULL THEN COALESCE(SUM(Div) OVER Yearly_w, 0)
            ELSE DivAnn
            END AS DivAnn,

            ------------------------------------------------------------------------------------------------------------------------
            -- Cash-Flow Values
            ------------------------------------------------------------------------------------------------------------------------
            
            COALESCE(CFO, 0) AS CFO, 
            COALESCE(CFI, 0) AS CFI, 
            COALESCE(CFF, 0) AS CFF, 
            COALESCE(CashEq, 0) AS CashEq, 

            CASE 
            WHEN CFO + CFI + CFF + CashEq IS NULL THEN 0 
            ELSE 1 
            END AS ExistCF,
            
            COALESCE(EqAR, pre_Eq/pre_TA) AS EqAR, 
            
            ------------------------------------------------------------------------------------------------------------------------
            -- Forecast Values
            ------------------------------------------------------------------------------------------------------------------------
            
            COALESCE(FDiv1Q, NxFDiv1Q) AS FDiv1Q, NxFDiv1Q,
            COALESCE(FDiv2Q, NxFDiv2Q) AS FDiv2Q, NxFDiv2Q,
            COALESCE(FDiv3Q, NxFDiv3Q) AS FDiv3Q, NxFDiv3Q,
            COALESCE(FDivFY, NxFDivFY) AS FDivFY, NxFDivFY,
            
            CASE 
            WHEN CurPerType = '2Q' THEN COALESCE(FSales, FSales2Q*2, NxFSales2Q*2, NxFSales) 
            ELSE COALESCE(FSales, NxFSales) 
            END AS FSales,

            CASE 
            WHEN CurPerType = '2Q' THEN COALESCE(FOP, FOP2Q*2, NxFOP2Q*2, NxFOP) 
            ELSE COALESCE(FOP , NxFOP) 
            END AS FOP,

            CASE 
            WHEN CurPerType = '2Q' THEN COALESCE(FOdP, FOdP2Q*2, NxFOdP2Q*2, NxFOdP) 
            ELSE COALESCE(FOdP , NxFOdP) 
            END AS FOdP,
            
            CASE 
            WHEN CurPerType = '2Q' THEN COALESCE(FNP, FNP2Q*2, NxFNp2Q*2, NxFNP) 
            ELSE COALESCE(FNP , NxFNP) 
            END AS FNP,

            CASE 
            WHEN CurPerType = '2Q' THEN COALESCE(FEPS, FEPS2Q*2, NxFEPS2Q*2, NxFEPS) 
            ELSE COALESCE(FEPS , NxFEPS) 
            END AS FEPS,

            ------------------------------------------------------------------------------------------------------------------------
        
        FROM fin_sum
        WHERE
            CurPerType NOT IN ('4Q', '5Q') AND CurPerType IS NOT NULL AND
            REGEXP_MATCHES(DocType, '([1-4]Q|FY)FinancialStatements_Consolidated_JP')

        WINDOW
        -- yearly : group by same year
        Yearly_w AS(
            PARTITION BY Code, CurFYEn
            ORDER BY DiscDate
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ),

        -- quarterly : group by same quarter
        Quarterly_w AS(
            PARTITION BY Code, CurPerType
            ORDER BY DiscDate
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW    
        )
    ),

    p2_base AS(
        SELECT 
            COLUMNS(
            c -> 
                c NOT LIKE('F%') AND
                c NOT IN ('pre_IsSh', 'pre_TrSh', 'EPS', 'BPS', 'EqAR', 'pre_TA', 'pre_Eq')
            ),

            LAG(Sales) OVER simple_w AS LaggedSales,
            LAG(OprP)  OVER simple_w AS LaggedOprP,
            LAG(OrdP)  OVER simple_w AS LaggedOrdP,
            LAG(NetP)  OVER simple_w AS LaggedNetP,

            COALESCE(LAST_VALUE(pre_TA IGNORE NULLS) OVER simple_w) AS TA,
            COALESCE(LAST_VALUE(pre_Eq IGNORE NULLS) OVER simple_w) AS Eq,     
            
            COALESCE(LAST_VALUE(EqAR     IGNORE NULLS) OVER simple_w) AS EqAR,
            COALESCE(LAST_VALUE(pre_IsSh IGNORE NULLS) OVER simple_w) AS IsSh,
            COALESCE(LAST_VALUE(pre_TrSh IGNORE NULLS) OVER simple_w, 0) AS TrSh,

            CASE
            WHEN NetP > 0 THEN COALESCE(EPS, NetP/(IsSh-TrSh), NetP/(IsSh))
            ELSE 0
            END AS pre_EPS, 

            pre_EPS AS EPS, 
            
            CASE
            WHEN Eq > 0 THEN COALESCE(BPS, Eq/(IsSh-TrSh), Eq/(IsSh)) 
            ELSE 0
            END AS BPS,
            
            COALESCE(LAST_VALUE(FDiv1Q IGNORE NULLS) OVER simple_w, 0) AS pre_FDiv1Q,
            COALESCE(LAST_VALUE(FDiv2Q IGNORE NULLS) OVER simple_w, 0) AS pre_FDiv2Q,
            COALESCE(LAST_VALUE(FDiv3Q IGNORE NULLS) OVER simple_w, 0) AS pre_FDiv3Q,
            COALESCE(LAST_VALUE(FDivFY IGNORE NULLS) OVER simple_w, 0) AS pre_FDivFY,
            COALESCE(LAST_VALUE(FSales IGNORE NULLS) OVER simple_w, Sales   *1.5) AS FSales,
            COALESCE(LAST_VALUE(FOP    IGNORE NULLS) OVER simple_w, OprP    *1.5) AS FOprP,
            COALESCE(LAST_VALUE(FOdP   IGNORE NULLS) OVER simple_w, OrdP    *1.5) AS FOrdP,
            COALESCE(LAST_VALUE(FNP    IGNORE NULLS) OVER simple_w, NetP    *1.5) AS FNetP,
            COALESCE(LAST_VALUE(FEPS   IGNORE NULLS) OVER simple_w, pre_EPS *1.5) AS FEPS,

            CASE 
            WHEN CurPerType = '1Q' THEN COALESCE(pre_FDiv1Q, NxFDiv1Q)
            WHEN CurPerType = '2Q' THEN COALESCE(pre_FDiv2Q, NxFDiv2Q)
            WHEN CurPerType = '3Q' THEN COALESCE(pre_FDiv3Q, NxFDiv3Q)
            WHEN CurPerType = 'FY' THEN COALESCE(pre_FDivFY, NxFDivFY)
            ELSE 0
            END AS FDivNxQ,
        
        FROM p1_base

        WINDOW 
        -- simple : group by Code Only
        simple_w AS(
            PARTITION BY Code
            ORDER BY DiscDate 
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )
        
        ORDER BY Code, DiscDate
    ),
    
    p3_base AS(
      SELECT 
          DiscDate, Code, CurPerType, CurPerSt, CurPerEn,
          Sales, FSales, 
          OprP , FOprP , 
          OrdP , FOrdP , 
          NetP , FNetP , 
          Div  , DivAnn, FDivNxQ,
          CFO, CFI, CFF, CashEq,
          TA, Eq, EqAR,
          IsSh, TrSh,
          EPS, FEPS, BPS
      FROM p2_base
      WHERE DiscDate - L_DiscDate > 80
      WINDOW w AS(
        PARTITION BY Code
        ORDER BY DiscDate
      )
      ORDER BY Code, DiscDate
    )
    
    SELECT
      DiscDate, Code, CurPerType, CurPerSt, CurPerEn,
      Sales - LaggedSales AS Sales, FSales,
      FSales/Sales AS FSalesRatio, 
    FROM p3_base