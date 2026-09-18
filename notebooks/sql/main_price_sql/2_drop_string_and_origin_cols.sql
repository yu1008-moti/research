-- OneHotEncoded_homogenous を読み込み

CREATE TABLE IF NOT EXISTS DropOrigin_OneHotEncoded_homogenous AS
SELECT *
FROM OneHotEncoded_homogenous;

-- delete origin original columns
-- DROP COLUMN :  CoName, CoNameEn, S17Nm, S33Nm, ScaleCat, MktNm, MrgnNm;
ALTER TABLE DropOrigin_OneHotEncoded_homogenous DROP COLUMN CoName;

ALTER TABLE DropOrigin_OneHotEncoded_homogenous DROP COLUMN CoNameEn;

ALTER TABLE DropOrigin_OneHotEncoded_homogenous DROP COLUMN S17Nm;

ALTER TABLE DropOrigin_OneHotEncoded_homogenous DROP COLUMN S17;

ALTER TABLE DropOrigin_OneHotEncoded_homogenous DROP COLUMN S33Nm;

ALTER TABLE DropOrigin_OneHotEncoded_homogenous DROP COLUMN S33;

ALTER TABLE DropOrigin_OneHotEncoded_homogenous DROP COLUMN ScaleCat;

ALTER TABLE DropOrigin_OneHotEncoded_homogenous DROP COLUMN MktNm;

ALTER TABLE DropOrigin_OneHotEncoded_homogenous DROP COLUMN Mkt;

ALTER TABLE DropOrigin_OneHotEncoded_homogenous DROP COLUMN MrgnNm;

ALTER TABLE DropOrigin_OneHotEncoded_homogenous DROP COLUMN Mrgn;