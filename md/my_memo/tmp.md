# オプションデータの検討

最終的に，使えないと判断している．

## 各商品区分ごとに，非NULL率を求める

```cmd
memory D select column_name, null_percentage from(summarize select * from syn.raw.drv_opt where ProdCat = 'EQOP') where null_percentage > 0;
┌─────────────┬─────────────────┐
│ column_name │ null_percentage │
│   varchar   │  decimal(9,2)   │
├─────────────┼─────────────────┤
│ EO          │          100.00 │
│ EH          │          100.00 │
│ EL          │          100.00 │
│ EC          │          100.00 │
│ SQD         │          100.00 │
│ Theo        │           15.32 │
│ BaseVol     │           15.32 │
│ IR          │           15.32 │
│ CCMFlag     │           15.32 │
└─────────────┴─────────────────┘
memory D select column_name, null_percentage from(summarize select * from syn.raw.drv_opt where ProdCat = 'JGBLFE') where null_percentage > 0;
┌─────────────┬─────────────────┐
│ column_name │ null_percentage │
│   varchar   │  decimal(9,2)   │
├─────────────┼─────────────────┤
│ EO          │            1.69 │
│ EH          │            1.69 │
│ EL          │            1.69 │
│ EC          │            1.69 │
│ SQD         │          100.00 │
│ Theo        │          100.00 │
│ BaseVol     │          100.00 │
│ IR          │          100.00 │
│ CCMFlag     │          100.00 │
└─────────────┴─────────────────┘
memory D select column_name, null_percentage from(summarize select * from syn.raw.drv_opt where ProdCat = 'NK225E') where null_percentage > 0;
┌─────────────┬─────────────────┐
│ column_name │ null_percentage │
│   varchar   │  decimal(9,2)   │
├─────────────┼─────────────────┤
│ MO          │           68.82 │
│ MH          │           68.82 │
│ ML          │           68.82 │
│ MC          │           68.82 │
│ EO          │            0.62 │
│ EH          │            0.62 │
│ EL          │            0.62 │
│ EC          │            0.62 │
│ AO          │            0.11 │
│ AH          │            0.11 │
│ AL          │            0.11 │
│ AC          │            0.11 │
│ VoOA        │          100.00 │
│ LTD         │          100.00 │
│ SQD         │          100.00 │
│ Settle      │          100.00 │
│ Theo        │          100.00 │
│ BaseVol     │          100.00 │
│ UnderPx     │          100.00 │
│ IV          │          100.00 │
│ IR          │          100.00 │
│ CCMFlag     │          100.00 │
└─────────────┴─────────────────┘
  22 rows             2 columns
memory D select column_name, null_percentage from(summarize select * from syn.raw.drv_opt where ProdCat = 'TOPIXE') where null_percentage > 0;
┌─────────────┬─────────────────┐
│ column_name │ null_percentage │
│   varchar   │  decimal(9,2)   │
├─────────────┼─────────────────┤
│ MO          │           32.88 │
│ MH          │           32.88 │
│ ML          │           32.88 │
│ MC          │           32.88 │
│ EO          │            0.83 │
│ EH          │            0.83 │
│ EL          │            0.83 │
│ EC          │            0.83 │
│ SQD         │          100.00 │
│ Theo        │          100.00 │
│ BaseVol     │          100.00 │
│ IR          │          100.00 │
│ CCMFlag     │          100.00 │
└─────────────┴─────────────────┘
  13 rows             2 columns

memory D create or replace temp table opt_topix as(select Code, ProdCat, UndSSO, Date, O, H, L, C, VO, OI, Va, CM, Strike, VoOA, LTD, Settle, UnderPX, IV  from syn.raw.drv_opt where ProdCat='TOPIXE' and substring(CM, 6, 2) in ['03', '06', '09', '12']);
```