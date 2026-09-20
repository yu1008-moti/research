WITH spare_feature AS(
  SELECT
    PubDate, Section,
  
    InsCoSell  + BankSell  + TrstBnkSell  + OthFinSell AS FinInsSell,
    InsCoBuy   + BankBuy   + TrstBnkBuy   + OthFinBuy  AS FinInsBuy,
    InsCoTot   + BankTot   + TrstBnkTot   + OthFinTot  AS FinInsTot,
    
    InvTrSell  + BusCoSell + OthCoSell    + FinInsSell AS InsSell,
    InvTrBuy   + BusCoBuy  + OthCoBuy     + FinInsBuy  AS InsBuy,
    InvTrTot   + BusCoTot  + OthCoTot     + FinInsTot  AS InsTot
  FROM eqt_inv
  WHERE
    PubDate >= '2008-05-07 00:00:00' AND
    Section != 'TokyoNagoya'
)
  
SELECT 
  CAST(s.PubDate AS DATE) AS PubDate,
  CASE
    WHEN s.Section = 'TSE1st'      THEN 1 
    WHEN s.Section = 'TSE2nd'      THEN 2
    WHEN s.Section = 'TSEMothers'  THEN 3 
    WHEN s.Section = 'TSEJASDAQ'   THEN 4
    WHEN s.Section = 'TSEPrime'    THEN 5 
    WHEN s.Section = 'TSEStandard' THEN 6 
    WHEN s.Section = 'TSEGrowth'   THEN 7
  ELSE 0
  END AS Section_id,
  
  (o.PropSell+1)   /   (o.PropBuy+1) AS PropBSRatio,
  (o.BrkSell +1)   /   (o.BrkBuy +1) AS BrkBSRatio,
  (o.TotSell +1)   /   (o.TotBuy +1) AS TotBSRatio,
  (o.PropTot +1)   /   (o.BrkTot +1) AS TotRatio,
  
  (s.InsSell +1)   /   (s.InsBuy +1) AS InsBSRatio,
   s.InsTot        /    o.BrkTot     AS InsWeight,
  
  (o.IndSell +1)   /   (o.IndBuy+1)  AS IndBSRatio,
   o.IndTot        /    o.BrkTot     AS IndWeight,
  
  (o.FrgnSell+1)   /   (o.FrgnBuy+1) AS FrgnBSRatio,
   o.FrgnTot       /    o.BrkTot     AS FrgnWeight,
  
  (o.SecCoSell+1)  /  (o.SecCoBuy+1) AS SecCoBSRatio,
   o.SecCoTot      /   o.BrkTot      AS SecCoWeight,
  
  (o.InvTrSell+1)  /  (o.InvTrBuy+1) AS InvTrBSRatio,
  o.InvTrTot       /   o.BrkTot      AS InvTrWeight,
  
  (o.BusCoSell+1)  /  (o.BusCoBuy+1) AS BusCoBSRatio,
   o.BusCoTot      /   o.BrkTot      AS BusCoWeight,
  
  (o.OthCoSell+1)  /  (o.BusCoBuy+1) AS OthCoBSRatio,
   o.OthCoTot      /   o.BrkTot      AS OthCoWeight,
  
  (s.FinInsSell+1) / (s.FinInsBuy+1) AS FinInsBSRatio,
   s.FinInsTot     /  o.BrkTot       AS FinInsWeight,
  
  (o.InsCoSell+1)  /  (o.InsCoBuy+1) AS InsCoBSRatio,
   o.InsCoTot      /   o.BrkTot      AS InsCoWeight,
  
  (o.BankSell+1)   /   (o.BankBuy+1) AS BankBSRatio,
   o.BankTot       /    o.BrkTot     AS BankWeight,
  
  (o.TrstBnkSell+1)/(o.TrstBnkBuy+1) AS TrstBnkBSRatio,
   o.TrstBnkTot    / o.BrkTot        AS TrstBnkWeight,

  -- To avoid multi-coliner
  -- log(o.OthFinSell+1)/(o.OthFinBuy+1) AS OthFinBSRatio,
  -- o.OthFinTot/o.BrkTot AS OthFinWeight
  
FROM eqt_inv o
JOIN spare_feature s
ON 
  o.PubDate = s.PubDate AND 
  o.Section = s.Section