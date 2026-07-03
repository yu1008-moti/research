# 指数データの利用方針

## 利用テーブル

### Mkt カテゴリ

プライム・スタンダード・グロースは，東証の市場再編成に伴い，2022/04/04 から新たに設置された市場区分です．<br>
配当込みの指数データのみ，2022/04/04 から提供しており，一時的に配当非込みの指数データを代替します．<br>
また，JASDAQのスタンダード・グロースは，現在廃止されているだけでなく，指数データが個別に存在しないことから，プールされた指数である JASDAQINDEX のみ使用します．

|指数コード|指数名称|市場区分コード|市場区分|開始期間|終了期間|
|:-:|-|:-:|:-:|:-:|:-:|
|0500<br>7000|東証プライム市場指数<br>配当込み 東証プライム市場指数 終値|0111|プライム|2022/06/27<br>2022/04/04|2026/04/17<br>2022/06/27|
|0501<br>7001|東証スタンダード市場指数<br>配当込み 東証スタンダード市場指数 終値|0112|スタンダード|2022/06/27<br>2022/04/04|2026/04/17<br>2022/06/27|
|0502<br>7002|東証グロース市場指数<br>配当込み 東証グロース市場指数 終値|0113|グロース|2022/06/27<br>2022/04/04|2026/04/17<br>2022/06/27|
|0070|東証グロース市場250指数<br>（旧：東証マザーズ指数※）|0104|マザーズ|2008/05/07|2026/04/17|
|0000|TOPIX|0101|東証一部|2008/05/07|2026/04/17|
|0001|東証二部総合指数|0102|東証二部|2008/05/07|2022/04/03|
|0091|JASDAQINDEX|0106<br>0107|JASDAQ スタンダード<br>JASDAQ グロース|2008/05/07|2022/04/03|

### S33 カテゴリ

指数の各業種別の指数は，S33コードに対応する業種別の指数です．<br>
そのため，エッジ構築・株価の変数変換の際に，S33コードを利用することができます．

|指数コード|指数名称|S33コード|S33名称|開始期間|終了期間|
|:-:|-|:-:|:-:|:-:|:-:|
|0040|東証業種別 水産・農林業|0050|水産・農林業|2008/05/07|2026/04/17|
|0041|東証業種別 鉱業|1050|鉱業|2008/05/07|2026/04/17|
|0042|東証業種別 建設業|2050|建設業|2008/05/07|2026/04/17|
|0043|東証業種別 食料品|3050|食料品|2008/05/07|2026/04/17|
|0044|東証業種別 繊維製品|3100|繊維製品|2008/05/07|2026/04/17|
|0045|東証業種別 パルプ・紙|3150|パルプ・紙|2008/05/07|2026/04/17|
|0046|東証業種別 化学|3200|化学|2008/05/07|2026/04/17|
|0047|東証業種別 医薬品|3250|医薬品|2008/05/07|2026/04/17|
|0048|東証業種別 石油・石炭製品|3300|石油・石炭製品|2008/05/07|2026/04/17|
|0049|東証業種別 ゴム製品|3350|ゴム製品|2008/05/07|2026/04/17|
|004A|東証業種別 ガラス・土石製品|3400|ガラス・土石製品|2008/05/07|2026/04/17|
|004B|東証業種別 鉄鋼|3450|鉄鋼|2008/05/07|2026/04/17|
|004C|東証業種別 非鉄金属|3500|非鉄金属|2008/05/07|2026/04/17|
|004D|東証業種別 金属製品|3550|金属製品|2008/05/07|2026/04/17|
|004E|東証業種別 機械|3600|機械|2008/05/07|2026/04/17|
|004F|東証業種別 電気機器|3650|電気機器|2008/05/07|2026/04/17|
|0050|東証業種別 輸送用機器|3700|輸送用機器|2008/05/07|2026/04/17|
|0051|東証業種別 精密機器|3750|精密機器|2008/05/07|2026/04/17|
|0052|東証業種別 その他製品|3800|その他製品|2008/05/07|2026/04/17|
|0053|東証業種別 電気・ガス業|4050|電気・ガス業|2008/05/07|2026/04/17|
|0054|東証業種別 陸運業|5050|陸運業|2008/05/07|2026/04/17|
|0055|東証業種別 海運業|5100|海運業|2008/05/07|2026/04/17|
|0056|東証業種別 空運業|5150|空運業|2008/05/07|2026/04/17|
|0057|東証業種別 倉庫・運輸関連業|5200|倉庫・運輸関連業|2008/05/07|2026/04/17|
|0058|東証業種別 情報・通信業|5250|情報・通信業|2008/05/07|2026/04/17|
|0059|東証業種別 卸売業|6050|卸売業|2008/05/07|2026/04/17|
|005A|東証業種別 小売業|6100|小売業|2008/05/07|2026/04/17|
|005B|東証業種別 銀行業|7050|銀行業|2008/05/07|2026/04/17|
|005C|東証業種別 証券・商品先物取引業|7100|証券・商品先物取引業|2008/05/07|2026/04/17|
|005D|東証業種別 保険業|7150|保険業|2008/05/07|2026/04/17|
|005E|東証業種別 その他金融業|7200|その他金融業|2008/05/07|2026/04/17|
|005F|東証業種別 不動産業|8050|不動産業|2008/05/07|2026/04/17|
|0060|東証業種別 サービス業|9050|サービス業|2008/05/07|2026/04/17|
|-|-|9999|その他|2008/05/07|2026/04/17|

## 不足しているデータの補完

頑張って手動で集めてきたデータを，SQLで補完する．<br>
このとき，埋めているデータはデータ取得開始日の 2008/05/07 のみである．<br>
他は，IPOが原因なので，IPOフラグとして処理する．<br>
ちなみに，情報の参照元は調整済み価格だったので，調整済み価格 `Adj-OHLC` を埋める．

> 以下のデータは，J-Quants から取得したデータではない．<br>実際に取得してみれば分かると思うが，以下に掲載しているデータは J-Quants から取得できない．

```sql
UPDATE eqt_main_tmp
SET AdjO=1280, AdjH=1280, AdjL=1280, AdjC=1280 
WHERE Date = '2008/5/7 00:00:00' AND Code = '13170';

UPDATE eqt_main_tmp
SET AdjO=1149, AdjH=1162, AdjL=1149, AdjC=1162 
WHERE Date = '2008/5/7 00:00:00' AND Code = '13180';

UPDATE eqt_main_tmp
SET AdjO=13430, AdjH=13430, AdjL=13400, AdjC=13400 
WHERE Date = '2008/5/7 00:00:00' AND Code = '16210';

UPDATE eqt_main_tmp
SET AdjO=18000, AdjH=18000, AdjL=18000, AdjC=18000 
WHERE Date = '2008/5/7 00:00:00' AND Code = '16320';

UPDATE eqt_main_tmp
SET AdjO=120, AdjH=120, AdjL=120, AdjC=120 
WHERE Date = '2008/5/7 00:00:00' AND Code = '17260';

UPDATE eqt_main_tmp
SET AdjO=665, AdjH=665, AdjL=665, AdjC=665 
WHERE Date = '2008/5/7 00:00:00' AND Code = '17370';

UPDATE eqt_main_tmp
SET AdjO=141, AdjH=141, AdjL=137, AdjC=137 
WHERE Date = '2008/5/7 00:00:00' AND Code = '17640';

UPDATE eqt_main_tmp
SET AdjO=550, AdjH=550, AdjL=550, AdjC=550 
WHERE Date = '2008/5/7 00:00:00' AND Code = '17670';

UPDATE eqt_main_tmp
SET AdjO=125, AdjH=125, AdjL=125, AdjC=125 
WHERE Date = '2008/5/7 00:00:00' AND Code = '18460';

UPDATE eqt_main_tmp
SET AdjO=281, AdjH=281, AdjL=281, AdjC=281 
WHERE Date = '2008/5/7 00:00:00' AND Code = '19870';

UPDATE eqt_main_tmp
SET AdjO=50300, AdjH=52300, AdjL=49200, AdjC=51300 
WHERE Date = '2008/5/7 00:00:00' AND Code = '21220';

UPDATE eqt_main_tmp
SET AdjO=480, AdjH=480, AdjL=480, AdjC=480 
WHERE Date = '2008/5/7 00:00:00' AND Code = '22160';

UPDATE eqt_main_tmp
SET AdjO=136, AdjH=140, AdjL=136, AdjC=136 
WHERE Date = '2008/5/7 00:00:00' AND Code = '22910';

UPDATE eqt_main_tmp
SET AdjO=820, AdjH=820, AdjL=820, AdjC=820 
WHERE Date = '2008/5/7 00:00:00' AND Code = '28050';

UPDATE eqt_main_tmp
SET AdjO=809, AdjH=809, AdjL=809, AdjC=809 
WHERE Date = '2008/5/7 00:00:00' AND Code = '28980';

UPDATE eqt_main_tmp
SET AdjO=1300, AdjH=1300, AdjL=1300, AdjC=1300 
WHERE Date = '2008/5/7 00:00:00' AND Code = '29230';

UPDATE eqt_main_tmp
SET AdjO=529, AdjH=530, AdjL=529, AdjC=530 
WHERE Date = '2008/5/7 00:00:00' AND Code = '37990';

UPDATE eqt_main_tmp
SET AdjO=309, AdjH=330, AdjL=309, AdjC=320 
WHERE Date = '2008/5/7 00:00:00' AND Code = '39550';

UPDATE eqt_main_tmp
SET AdjO=574, AdjH=574, AdjL=574, AdjC=574 
WHERE Date = '2008/5/7 00:00:00' AND Code = '41870';

UPDATE eqt_main_tmp
SET AdjO=401, AdjH=410, AdjL=401, AdjC=410 
WHERE Date = '2008/5/7 00:00:00' AND Code = '43640';

UPDATE eqt_main_tmp
SET AdjO=257, AdjH=260, AdjL=257, AdjC=260 
WHERE Date = '2008/5/7 00:00:00' AND Code = '44090';

UPDATE eqt_main_tmp
SET AdjO=239, AdjH=239, AdjL=239, AdjC=239 
WHERE Date = '2008/5/7 00:00:00' AND Code = '46420';

UPDATE eqt_main_tmp
SET AdjO=3990, AdjH=3990, AdjL=3990, AdjC=3990 
WHERE Date = '2008/5/7 00:00:00' AND Code = '48500';

UPDATE eqt_main_tmp
SET AdjO=8840, AdjH=8840, AdjL=8840, AdjC=8840 
WHERE Date = '2008/5/7 00:00:00' AND Code = '48630';

UPDATE eqt_main_tmp
SET AdjO=303, AdjH=303, AdjL=297, AdjC=297 
WHERE Date = '2008/5/7 00:00:00' AND Code = '49990';

UPDATE eqt_main_tmp
SET AdjO=240, AdjH=240, AdjL=240, AdjC=240 
WHERE Date = '2008/5/7 00:00:00' AND Code = '53550';

UPDATE eqt_main_tmp
SET AdjO=649, AdjH=649, AdjL=632, AdjC=632 
WHERE Date = '2008/5/7 00:00:00' AND Code = '58160';

UPDATE eqt_main_tmp
SET AdjO=377, AdjH=377, AdjL=376, AdjC=376 
WHERE Date = '2008/5/7 00:00:00' AND Code = '59330';

UPDATE eqt_main_tmp
SET AdjO=159, AdjH=159, AdjL=159, AdjC=159 
WHERE Date = '2008/5/7 00:00:00' AND Code = '59640';

UPDATE eqt_main_tmp
SET AdjO=197, AdjH=197, AdjL=197, AdjC=197 
WHERE Date = '2008/5/7 00:00:00' AND Code = '61120';

UPDATE eqt_main_tmp
SET AdjO=436, AdjH=436, AdjL=436, AdjC=436 
WHERE Date = '2008/5/7 00:00:00' AND Code = '61440';

UPDATE eqt_main_tmp
SET AdjO=460, AdjH=460, AdjL=460, AdjC=460 
WHERE Date = '2008/5/7 00:00:00' AND Code = '63210';

UPDATE eqt_main_tmp
SET AdjO=265, AdjH=270, AdjL=265, AdjC=270 
WHERE Date = '2008/5/7 00:00:00' AND Code = '63250';

UPDATE eqt_main_tmp
SET AdjO=190, AdjH=198, AdjL=190, AdjC=198 
WHERE Date = '2008/5/7 00:00:00' AND Code = '63920';

UPDATE eqt_main_tmp
SET AdjO=680, AdjH=680, AdjL=680, AdjC=680 
WHERE Date = '2008/5/7 00:00:00' AND Code = '66870';

UPDATE eqt_main_tmp
SET AdjO=260, AdjH=260, AdjL=260, AdjC=260 
WHERE Date = '2008/5/7 00:00:00' AND Code = '67430';

UPDATE eqt_main_tmp
SET AdjO=590, AdjH=594, AdjL=588, AdjC=588 
WHERE Date = '2008/5/7 00:00:00' AND Code = '74420';

UPDATE eqt_main_tmp
SET AdjO=9500, AdjH=9500, AdjL=9500, AdjC=9500 
WHERE Date = '2008/5/7 00:00:00' AND Code = '76610';

UPDATE eqt_main_tmp
SET AdjO=619, AdjH=619, AdjL=619, AdjC=619 
WHERE Date = '2008/5/7 00:00:00' AND Code = '77470';

UPDATE eqt_main_tmp
SET AdjO=283, AdjH=283, AdjL=283, AdjC=283 
WHERE Date = '2008/5/7 00:00:00' AND Code = '79200';

UPDATE eqt_main_tmp
SET AdjO=1320, AdjH=1320, AdjL=1320, AdjC=1320 
WHERE Date = '2008/5/7 00:00:00' AND Code = '79790';

UPDATE eqt_main_tmp
SET AdjO=180, AdjH=180, AdjL=180, AdjC=180 
WHERE Date = '2008/5/7 00:00:00' AND Code = '80230';

UPDATE eqt_main_tmp
SET AdjO=4860, AdjH=4860, AdjL=4860, AdjC=4860 
WHERE Date = '2008/5/7 00:00:00' AND Code = '86340';

UPDATE eqt_main_tmp
SET AdjO=6330, AdjH=6330, AdjL=6330, AdjC=6330 
WHERE Date = '2008/5/7 00:00:00' AND Code = '86400';

UPDATE eqt_main_tmp
SET AdjO=13400, AdjH=13400, AdjL=13400, AdjC=13400 
WHERE Date = '2008/5/7 00:00:00' AND Code = '86650';

UPDATE eqt_main_tmp
SET AdjO=12350, AdjH=12350, AdjL=12350, AdjC=12350 
WHERE Date = '2008/5/7 00:00:00' AND Code = '86660';

UPDATE eqt_main_tmp
SET AdjO=1600, AdjH=1600, AdjL=1600, AdjC=1600 
WHERE Date = '2008/5/7 00:00:00' AND Code = '86890';

UPDATE eqt_main_tmp
SET AdjO=198, AdjH=198, AdjL=189, AdjC=189 
WHERE Date = '2008/5/7 00:00:00' AND Code = '90170';

UPDATE eqt_main_tmp
SET AdjO=391, AdjH=391, AdjL=391, AdjC=391 
WHERE Date = '2008/5/7 00:00:00' AND Code = '90590';

UPDATE eqt_main_tmp
SET AdjO=180, AdjH=182, AdjL=180, AdjC=182 
WHERE Date = '2008/5/7 00:00:00' AND Code = '90630';

UPDATE eqt_main_tmp
SET AdjO=570, AdjH=570, AdjL=570, AdjC=570 
WHERE Date = '2008/5/7 00:00:00' AND Code = '90820';

UPDATE eqt_main_tmp
SET AdjO=430, AdjH=430, AdjL=430, AdjC=430 
WHERE Date = '2008/5/7 00:00:00' AND Code = '93110';

UPDATE eqt_main_tmp
SET AdjO=319, AdjH=319, AdjL=319, AdjC=319 
WHERE Date = '2008/5/7 00:00:00' AND Code = '93610';

UPDATE eqt_main_tmp
SET AdjO=3000, AdjH=3000, AdjL=3000, AdjC=3000 
WHERE Date = '2008/5/7 00:00:00' AND Code = '94810';

UPDATE eqt_main_tmp
SET AdjO=491, AdjH=491, AdjL=491, AdjC=491 
WHERE Date = '2008/5/7 00:00:00' AND Code = '95390';

UPDATE eqt_main_tmp
SET AdjO=398, AdjH=398, AdjL=398, AdjC=398 
WHERE Date = '2008/5/7 00:00:00' AND Code = '95420';

UPDATE eqt_main_tmp
SET AdjO=351, AdjH=351, AdjL=350, AdjC=350 
WHERE Date = '2008/5/7 00:00:00' AND Code = '95440';

UPDATE eqt_main_tmp
SET AdjO=978, AdjH=978, AdjL=978, AdjC=978 
WHERE Date = '2008/5/7 00:00:00' AND Code = '96290';

UPDATE eqt_main_tmp
SET AdjO=546, AdjH=546, AdjL=546, AdjC=546 
WHERE Date = '2008/5/7 00:00:00' AND Code = '96800';
```
