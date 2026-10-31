create or replace table dev.seq.futures as(
select
        n.gnID,  -- means global node ID (global: unique ID for each rows in all dates)
        list(n.gnID) over(
            partition by n.cID
            order by t.tID
            rows between 24 preceding and current row -- means past 24 nodes and current node, total 25 nodes
        ) as seq
    from dev.x.futures as o
    join dev.id.node as n
    on o.code = n.code and o.tradeDate = n.tradeDate and n.ntID = 3
    join dev.id.date as t
    on o.tradeDate = t.tradeDate
    order by t.tID, n.lnID
);