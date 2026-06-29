# DB 詳細

## 現在の状況（チェック済み = DB構築済み）

各DBがどのように構築され，逆になぜ無視されたのかを詳細に記述する．

### 作成必須項目

#### derivative シリーズ

- [x] derivatives_bars_daily_futures
- [x] derivatives_bars_daily_options

#### equity シリーズ

- [x] equities_bars_daily
- [x] equities_investor-types
- [x] equities_master

#### financial シリーズ

- [x] fins_details
- [x] fins_dividend
- [x] fins_summary

#### index シリーズ

- [x] indices_bars_daily

#### markets シリーズ

- [x] markets_breakdown
- [x] markets_margin-alert
- [x] markets_margin-interest
- [x] markets_short-ratio

全て構築完了（2026年6月29日）．

### 無視項目

|データタイプ|理由|
|:-|:-|
|derivatives_bars_daily_options_225|derivatives_bars_daily_options に含まれるため|
|equities_earnings-calendar|現在の最新情報以外は記録されていないため|
|indices_bars_daily_topix|indices_bars_daily に含まれており，処理済みのため|
|markets_calendar|市場が空いているか否かであり，必要ではないため|
|markets_short-sale-report|全期間に渡って取得できたデータが０件だったため|

## 各ファイルに対する処理

|ファイルタイプ|処理内容|
|:-|:-|
|derivatives_bars_daily_futures|スクリプトからDB構築済み|

## 今後

- [ ] データの整備
- [ ] エッジの定義
- [ ] エッジの整備
