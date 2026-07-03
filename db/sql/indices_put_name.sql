
-- 以下リンクは「配当込み」に関するWebサイト
-- https://www.matsui.co.jp/money-satellite/column/fund/cl-2026033101_fund.html

CREATE OR REPLACE TABLE idx_prc_tmp AS
  SELECT 
    *,
    CASE
		----------------------------------------------------------------------
		-- 東証業種別指数
		----------------------------------------------------------------------
    	WHEN Code = '0040' THEN '東証業種別 水産・農林業'
    	WHEN Code = '0041' THEN '東証業種別 鉱業'
    	WHEN Code = '0042' THEN '東証業種別 建設業'
    	WHEN Code = '0043' THEN '東証業種別 食料品'
    	WHEN Code = '0044' THEN '東証業種別 繊維製品'
    	WHEN Code = '0045' THEN '東証業種別 パルプ・紙'
    	WHEN Code = '0046' THEN '東証業種別 化学'
    	WHEN Code = '0047' THEN '東証業種別 医薬品'
    	WHEN Code = '0048' THEN '東証業種別 石油・石炭製品​'
    	WHEN Code = '0049' THEN '東証業種別 ゴム製品'
    	WHEN Code = '004A' THEN '東証業種別 ガラス・土石製品'
    	WHEN Code = '004B' THEN '東証業種別 鉄鋼'
    	WHEN Code = '004C' THEN '東証業種別 非鉄金属'
    	WHEN Code = '004D' THEN '東証業種別 金属製品'
    	WHEN Code = '004E' THEN '東証業種別 機械'
    	WHEN Code = '004F' THEN '東証業種別 電気機器'
    	WHEN Code = '0050' THEN '東証業種別 輸送用機器'
    	WHEN Code = '0051' THEN '東証業種別 精密機器'
    	WHEN Code = '0052' THEN '東証業種別 その他製品'
    	WHEN Code = '0053' THEN '東証業種別 電気・ガス業'
    	WHEN Code = '0054' THEN '東証業種別 陸運業'
    	WHEN Code = '0055' THEN '東証業種別 海運業'
    	WHEN Code = '0056' THEN '東証業種別 空運業'
    	WHEN Code = '0057' THEN '東証業種別 倉庫・運輸関連業​'
    	WHEN Code = '0058' THEN '東証業種別 情報・通信業'
    	WHEN Code = '0059' THEN '東証業種別 卸売業'
    	WHEN Code = '005A' THEN '東証業種別 小売業'
    	WHEN Code = '005B' THEN '東証業種別 銀行業'
    	WHEN Code = '005C' THEN '東証業種別 証券・商品先物取引業'
    	WHEN Code = '005D' THEN '東証業種別 保険業'
    	WHEN Code = '005E' THEN '東証業種別 その他金融業'
    	WHEN Code = '005F' THEN '東証業種別 不動産業'
    	WHEN Code = '0060' THEN '東証業種別 サービス業'
		WHEN Code = '6040' THEN '配当込み 東証業種別 水産・農林業 終値'
    	WHEN Code = '6041' THEN '配当込み 東証業種別 鉱業 終値'
    	WHEN Code = '6042' THEN '配当込み 東証業種別 建設業 終値'
    	WHEN Code = '6043' THEN '配当込み 東証業種別 食料品 終値'
    	WHEN Code = '6044' THEN '配当込み 東証業種別 繊維製品 終値'
    	WHEN Code = '6045' THEN '配当込み 東証業種別 パルプ・紙 終値'
    	WHEN Code = '6046' THEN '配当込み 東証業種別 化学 終値'
    	WHEN Code = '6047' THEN '配当込み 東証業種別 医薬品 終値'
    	WHEN Code = '6048' THEN '配当込み 東証業種別 石油・石炭製品 終値'
    	WHEN Code = '6049' THEN '配当込み 東証業種別 ゴム製品 終値'
    	WHEN Code = '604A' THEN '配当込み 東証業種別 ガラス・土石製品 終値'
    	WHEN Code = '604B' THEN '配当込み 東証業種別 鉄鋼 終値'
    	WHEN Code = '604C' THEN '配当込み 東証業種別 非鉄金属 終値'
    	WHEN Code = '604D' THEN '配当込み 東証業種別 金属製品 終値'
    	WHEN Code = '604E' THEN '配当込み 東証業種別 機械 終値'
    	WHEN Code = '604F' THEN '配当込み 東証業種別 電気機器 終値'
    	WHEN Code = '6050' THEN '配当込み 東証業種別 輸送用機器 終値'
    	WHEN Code = '6051' THEN '配当込み 東証業種別 精密機器 終値'
    	WHEN Code = '6052' THEN '配当込み 東証業種別 その他製品 終値'
    	WHEN Code = '6053' THEN '配当込み 東証業種別 電気・ガス業 終値'
    	WHEN Code = '6054' THEN '配当込み 東証業種別 陸運業 終値'
    	WHEN Code = '6055' THEN '配当込み 東証業種別 海運業 終値'
    	WHEN Code = '6056' THEN '配当込み 東証業種別 空運業 終値'
    	WHEN Code = '6057' THEN '配当込み 東証業種別 倉庫・運輸関連業 終値'
    	WHEN Code = '6058' THEN '配当込み 東証業種別 情報・通信業 終値'
    	WHEN Code = '6059' THEN '配当込み 東証業種別 卸売業 終値'
    	WHEN Code = '605A' THEN '配当込み 東証業種別 小売業 終値'
    	WHEN Code = '605B' THEN '配当込み 東証業種別 銀行業 終値'
    	WHEN Code = '605C' THEN '配当込み 東証業種別 証券・商品先物取引業 終値'
    	WHEN Code = '605D' THEN '配当込み 東証業種別 保険業 終値'
    	WHEN Code = '605E' THEN '配当込み 東証業種別 その他金融業 終値'
    	WHEN Code = '605F' THEN '配当込み 東証業種別 不動産業 終値'
    	WHEN Code = '6060' THEN '配当込み 東証業種別 サービス業 終値'
		----------------------------------------------------------------------
		-- This Section is corrspoding to the prc_main of S33 categories
		----------------------------------------------------------------------


		----------------------------------------------------------------------
		-- TOPIX-17指数
		----------------------------------------------------------------------
    	WHEN Code = '0080' THEN 'TOPIX-17 食品'
    	WHEN Code = '0081' THEN 'TOPIX-17 エネルギー資源'
    	WHEN Code = '0082' THEN 'TOPIX-17 建設・資材'
    	WHEN Code = '0083' THEN 'TOPIX-17 素材・化学'
    	WHEN Code = '0084' THEN 'TOPIX-17 医薬品'
    	WHEN Code = '0085' THEN 'TOPIX-17 自動車・輸送機'
    	WHEN Code = '0086' THEN 'TOPIX-17 鉄鋼・非鉄'
    	WHEN Code = '0087' THEN 'TOPIX-17 機械'
    	WHEN Code = '0088' THEN 'TOPIX-17 電機・精密'
    	WHEN Code = '0089' THEN 'TOPIX-17 情報通信・サービスその他'
    	WHEN Code = '008A' THEN 'TOPIX-17 電力・ガス'
    	WHEN Code = '008B' THEN 'TOPIX-17 運輸・物流'
    	WHEN Code = '008C' THEN 'TOPIX-17 商社・卸売'
    	WHEN Code = '008D' THEN 'TOPIX-17 小売'
    	WHEN Code = '008E' THEN 'TOPIX-17 銀行'
    	WHEN Code = '008F' THEN 'TOPIX-17 金融（除く銀行）'
    	WHEN Code = '0090' THEN 'TOPIX-17 不動産'
    	WHEN Code = '6080' THEN '配当込み TOPIX-17 食品 終値'
    	WHEN Code = '6081' THEN '配当込み TOPIX-17 エネルギー資源 終値'
    	WHEN Code = '6082' THEN '配当込み TOPIX-17 建設・資材 終値'
    	WHEN Code = '6083' THEN '配当込み TOPIX-17 素材・化学 終値'
    	WHEN Code = '6084' THEN '配当込み TOPIX-17 医薬品 終値'
    	WHEN Code = '6085' THEN '配当込み TOPIX-17 自動車・輸送機 終値'
    	WHEN Code = '6086' THEN '配当込み TOPIX-17 鉄鋼・非鉄 終値'
    	WHEN Code = '6087' THEN '配当込み TOPIX-17 機械 終値'
    	WHEN Code = '6088' THEN '配当込み TOPIX-17 電機・精密 終値'
    	WHEN Code = '6089' THEN '配当込み TOPIX-17 情報通信・サービスその他 終値'
    	WHEN Code = '608A' THEN '配当込み TOPIX-17 電力・ガス 終値'
    	WHEN Code = '608B' THEN '配当込み TOPIX-17 運輸・物流 終値'
    	WHEN Code = '608C' THEN '配当込み TOPIX-17 商社・卸売 終値'
    	WHEN Code = '608D' THEN '配当込み TOPIX-17 小売 終値'
    	WHEN Code = '608E' THEN '配当込み TOPIX-17 銀行 終値'
    	WHEN Code = '608F' THEN '配当込み TOPIX-17 金融（除く銀行） 終値'
    	WHEN Code = '6090' THEN '配当込み TOPIX-17 不動産 終値'
		----------------------------------------------------------------------
		-- This Section is corrspoding to the prc_main of S17 categories
		----------------------------------------------------------------------


		----------------------------------------------------------------------
		-- プライム／スタンダード／グロース市場指数
		----------------------------------------------------------------------
		-- 市場の再編については，公式の文言を参照している
		-- 東証は、以上の課題を踏まえて市場区分の見直しに向けた検討を進め、
		-- 2022年4月4日に、「プライム市場・スタンダード市場・グロース市場」の3つの市場区分がスタートいたしました。
		-- https://www.jpx.co.jp/equities/improvements/market-structure/01.html

		-- 2022/06/27〜
    	WHEN Code = '0500' THEN '東証プライム市場指数' -- >> Mkt = 'プライム'
    	WHEN Code = '0501' THEN '東証スタンダード市場指数' -- >> Mkt = 'スタンダード'
    	WHEN Code = '0502' THEN '東証グロース市場指数' -- >> Mkt = 'グロース'

		-- 2022/04/04～2022/06/27
		WHEN Code = '7000' THEN '配当込み 東証プライム市場指数 終値' -- >> Mkt = 'プライム'
    	WHEN Code = '7001' THEN '配当込み 東証スタンダード市場指数 終値' -- >> Mkt = 'スタンダード'
    	WHEN Code = '7002' THEN '配当込み 東証グロース市場指数 終値' -- >> Mkt = 'グロース'

		-- 2022年4月の東証市場区分再編によりマザーズ市場は廃止されていますが、
		-- 一定のルールに基づき東証マザーズ指数の構成銘柄の入替を行い、
		-- 2023年11月6日より指数名称を「東証グロース市場250指数」に変更されています。
		-- 詳細はこちらをご参照ください。(https://www.jpx.co.jp/news/6030/20230428-01.html)
		WHEN Code = '0070' THEN '東証グロース市場250指数(旧：東証マザーズ指数※)' -- >> Mkt = 'マザーズ'

		-- 2008/5/7〜2022/4/1（2・3日は土曜と日曜なので，実質2022/04/04まで）
		WHEN Code = '0000' THEN 'TOPIX' -- >> Mkt = '東証一部'

		-- 2008/5/7〜2022/4/1（2・3日は土曜と日曜なので，実質2022/04/04まで）
		WHEN Code = '0001' THEN '東証二部総合指数' -- >> Mkt = '東証二部'

		-- 2008/5/7〜2022/4/1（2・3日は土曜と日曜なので，実質2022/04/04まで）
		WHEN Code = '0091' THEN 'JASDAQINDEX' -- >> Mkt = 'JASDAQ グロース／スタンダード'

		-- 使用しない可能性 大
		WHEN Code = '6000' THEN '配当込み TOPIX 終値' -- >> Mkt = '東証一部'
		----------------------------------------------------------------------
		-- This Section is corrspoding to the prc_main of Mkt categories
		----------------------------------------------------------------------


		----------------------------------------------------------------------
		-- JPX指数
		----------------------------------------------------------------------
    	WHEN Code = '0503' THEN 'JPXプライム150指数'
    	WHEN Code = '0504' THEN 'JPXスタートアップ急成長100指数'
		WHEN Code = '6503' THEN '配当込み JPXプライム150指数 終値'
    	WHEN Code = '6504' THEN '配当込み JPXスタートアップ急成長100指数 終値'
		WHEN Code = 'B507' THEN '配当込み JPX日経インデックス400 終値'
		----------------------------------------------------------------------


		----------------------------------------------------------------------
		-- TOPIX指数
		----------------------------------------------------------------------
    	WHEN Code = '6000' THEN '配当込み TOPIX 終値'
		----------------------------------------------------------------------


		----------------------------------------------------------------------
		-- TOPIX指数
		----------------------------------------------------------------------
		WHEN Code = '0028' THEN 'TOPIX Core30'
    	WHEN Code = '0029' THEN 'TOPIX Large70'
    	WHEN Code = '002A' THEN 'TOPIX 100'
    	WHEN Code = '002B' THEN 'TOPIX Mid400'
    	WHEN Code = '002C' THEN 'TOPIX 500'
    	WHEN Code = '002D' THEN 'TOPIX Small'
    	WHEN Code = '002E' THEN 'TOPIX 1000'
    	WHEN Code = '002F' THEN 'TOPIX Small500'
    	WHEN Code = '6028' THEN '配当込み TOPIX Core30 終値'
    	WHEN Code = '6029' THEN '配当込み TOPIX Large70 終値'
    	WHEN Code = '602A' THEN '配当込み TOPIX 100 終値'
    	WHEN Code = '602B' THEN '配当込み TOPIX Mid400 終値'
    	WHEN Code = '602C' THEN '配当込み TOPIX 500 終値'
    	WHEN Code = '602D' THEN '配当込み TOPIX Small 終値'
    	WHEN Code = '602E' THEN '配当込み TOPIX 1000 終値'
		----------------------------------------------------------------------


		----------------------------------------------------------------------
		-- TOPIXバリュー／グロース指数
		----------------------------------------------------------------------
		WHEN Code = '8100' THEN 'TOPIX バリュー'
    	WHEN Code = '812C' THEN 'TOPIX 500バリュー'
    	WHEN Code = '812D' THEN 'TOPIX Smallバリュー'
    	WHEN Code = '8200' THEN 'TOPIX グロース'
    	WHEN Code = '822C' THEN 'TOPIX 500グロース'
    	WHEN Code = '822D' THEN 'TOPIX Smallグロース'
    	WHEN Code = 'B100' THEN '配当込み TOPIX バリュー 終値'
    	WHEN Code = 'B200' THEN '配当込み TOPIX グロース 終値'
    	WHEN Code = 'B12C' THEN '配当込み TOPIX 500バリュー 終値'
    	WHEN Code = 'B22C' THEN '配当込み TOPIX 500グロース 終値'
    	WHEN Code = 'B12D' THEN '配当込み TOPIX Smallバリュー 終値'
    	WHEN Code = 'B22D' THEN '配当込み TOPIX Smallグロース 終値'
		----------------------------------------------------------------------


		----------------------------------------------------------------------
		-- REIT指数
		----------------------------------------------------------------------
		WHEN Code = '0075' THEN 'REIT'
    	WHEN Code = '8501' THEN '東証REITオフィス指数'
    	WHEN Code = '8502' THEN '東証REIT住宅指数'
    	WHEN Code = '8503' THEN '東証REIT商業・物流等指数'
    	WHEN Code = '6075' THEN '配当込み REIT 終値'
    	WHEN Code = 'B501' THEN '配当込み 東証REITオフィス指数 終値'
    	WHEN Code = 'B502' THEN '配当込み 東証REIT住宅指数 終値'
    	WHEN Code = 'B503' THEN '配当込み 東証REIT商業・物流等指数 終値'
		----------------------------------------------------------------------


		----------------------------------------------------------------------
		-- その他指数
		----------------------------------------------------------------------
		WHEN Code = 'B500' THEN '配当込み 配当フォーカス100 終値'
		WHEN Code = '0070' THEN '東証グロース市場250指数(旧：東証マザーズ指数※)'
		WHEN Code = '6096' THEN '税引後 配当込み JPX日経インデックス400 終値'
		WHEN Code = '6095' THEN '税引後 配当込み TOPIX 終値'
		----------------------------------------------------------------------


  	ELSE '-' END AS IdxNm,
	CASE
		WHEN Code = '0040' OR Code = '6040' THEN '0050' -- 水産・農林業
		WHEN Code = '0041' OR Code = '6041' THEN '1050' -- 鉱業
		WHEN Code = '0042' OR Code = '6042' THEN '2050' -- 建設業
		WHEN Code = '0043' OR Code = '6043' THEN '3050' -- 食料品
		WHEN Code = '0044' OR Code = '6044' THEN '3100' -- 繊維製品
		WHEN Code = '0045' OR Code = '6045' THEN '3150' -- パルプ・紙
		WHEN Code = '0046' OR Code = '6046' THEN '3200' -- 化学
		WHEN Code = '0047' OR Code = '6047' THEN '3250' -- 医薬品
		WHEN Code = '0048' OR Code = '6048' THEN '3300' -- 石油・石炭製品​
		WHEN Code = '0049' OR Code = '6049' THEN '3350' -- ゴム製品
		WHEN Code = '004A' OR Code = '604A' THEN '3400' -- ガラス・土石製品
		WHEN Code = '004B' OR Code = '604B' THEN '3450' -- 鉄鋼
		WHEN Code = '004C' OR Code = '604C' THEN '3500' -- 非鉄金属
		WHEN Code = '004D' OR Code = '604D' THEN '3550' -- 金属製品
		WHEN Code = '004E' OR Code = '604E' THEN '3600' -- 機械
		WHEN Code = '004F' OR Code = '604F' THEN '3650' -- 電気機器
		WHEN Code = '0050' OR Code = '6050' THEN '3700' -- 輸送用機器
		WHEN Code = '0051' OR Code = '6051' THEN '3750' -- 精密機器
		WHEN Code = '0052' OR Code = '6052' THEN '3800' -- その他製品
		WHEN Code = '0053' OR Code = '6053' THEN '4050' -- 電気・ガス業
		WHEN Code = '0054' OR Code = '6054' THEN '5050' -- 陸運業
		WHEN Code = '0055' OR Code = '6055' THEN '5100' -- 海運業
		WHEN Code = '0056' OR Code = '6056' THEN '5150' -- 空運業
		WHEN Code = '0057' OR Code = '6057' THEN '5200' -- 倉庫・運輸関連業​
		WHEN Code = '0058' OR Code = '6058' THEN '5250' -- 情報・通信業
		WHEN Code = '0059' OR Code = '6059' THEN '6050' -- 卸売業
		WHEN Code = '005A' OR Code = '605A' THEN '6100' -- 小売業
		WHEN Code = '005B' OR Code = '605B' THEN '7050' -- 銀行業
		WHEN Code = '005C' OR Code = '605C' THEN '7100' -- 証券・商品先物取引業
		WHEN Code = '005D' OR Code = '605D' THEN '7150' -- 保険業
		WHEN Code = '005E' OR Code = '605E' THEN '7200' -- その他金融業
		WHEN Code = '005F' OR Code = '605F' THEN '8050' -- 不動産業
		WHEN Code = '0060' OR Code = '6060' THEN '9050' -- サービス業
	ELSE '-' END AS S33
	CASE
		WHEN Code = '0080' OR Code = '6080' THEN '1'  -- 食品
		WHEN Code = '0081' OR Code = '6081' THEN '2'  -- エネルギー資源
		WHEN Code = '0082' OR Code = '6082' THEN '3'  -- 建設・資材
		WHEN Code = '0083' OR Code = '6083' THEN '4'  -- 素材・化学
		WHEN Code = '0084' OR Code = '6084' THEN '5'  -- 医薬品
		WHEN Code = '0085' OR Code = '6085' THEN '6'  -- 自動車・輸送機
		WHEN Code = '0086' OR Code = '6086' THEN '7'  -- 鉄鋼・非鉄
		WHEN Code = '0087' OR Code = '6087' THEN '8'  -- 機械
		WHEN Code = '0088' OR Code = '6088' THEN '9'  -- 電機・精密
		WHEN Code = '0089' OR Code = '6089' THEN '10' -- 情報通信・サービスその他
		WHEN Code = '008A' OR Code = '608A' THEN '11' -- 電力・ガス
		WHEN Code = '008B' OR Code = '608B' THEN '12' -- 運輸・物流
		WHEN Code = '008C' OR Code = '608C' THEN '13' -- 商社・卸売
		WHEN Code = '008D' OR Code = '608D' THEN '14' -- 小売
		WHEN Code = '008E' OR Code = '608E' THEN '15' -- 銀行
		WHEN Code = '008F' OR Code = '608F' THEN '16' -- 金融（除く銀行）
		WHEN Code = '0090' OR Code = '6090' THEN '17' -- 不動産
	ELSE '-' END AS S17
  END AS Mkt

  FROM idx_prc