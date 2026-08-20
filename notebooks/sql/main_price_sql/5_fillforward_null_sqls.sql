UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET O = (
	SELECT t2.O
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.O IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.O IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET H = (
	SELECT t2.H
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.H IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.H IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET L = (
	SELECT t2.L
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.L IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.L IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET C = (
	SELECT t2.C
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.C IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.C IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET UL = (
	SELECT t2.UL
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.UL IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.UL IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET LL = (
	SELECT t2.LL
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.LL IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.LL IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET Vo = (
	SELECT t2.Vo
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.Vo IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.Vo IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET Va = (
	SELECT t2.Va
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.Va IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.Va IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET AdjFactor = (
	SELECT t2.AdjFactor
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.AdjFactor IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.AdjFactor IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET ADjO = (
	SELECT t2.ADjO
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.ADjO IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.ADjO IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET ADjH = (
	SELECT t2.ADjH
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.ADjH IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.ADjH IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET ADjL = (
	SELECT t2.ADjL
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.ADjL IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.ADjL IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET ADjC = (
	SELECT t2.ADjC
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.ADjC IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.ADjC IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET AdjVo = (
	SELECT t2.AdjVo
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.AdjVo IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.AdjVo IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET MO = (
	SELECT t2.MO
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.MO IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.MO IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET MH = (
	SELECT t2.MH
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.MH IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.MH IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET ML = (
	SELECT t2.ML
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.ML IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.ML IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET MC = (
	SELECT t2.MC
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.MC IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.MC IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET MUL = (
	SELECT t2.MUL
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.MUL IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.MUL IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET MLL = (
	SELECT t2.MLL
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.MLL IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.MLL IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET MVo = (
	SELECT t2.MVo
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.MVo IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.MVo IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET MVa = (
	SELECT t2.MVa
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.MVa IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.MVa IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET MAdjO = (
	SELECT t2.MAdjO
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.MAdjO IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.MAdjO IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET MAdjH = (
	SELECT t2.MAdjH
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.MAdjH IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.MAdjH IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET MAdjL = (
	SELECT t2.MAdjL
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.MAdjL IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.MAdjL IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET MAdjC = (
	SELECT t2.MAdjC
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.MAdjC IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.MAdjC IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET MAdjVo = (
	SELECT t2.MAdjVo
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.MAdjVo IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.MAdjVo IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET AO = (
	SELECT t2.AO
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.AO IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.AO IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET AH = (
	SELECT t2.AH
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.AH IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.AH IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET AL = (
	SELECT t2.AL
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.AL IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.AL IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET AC = (
	SELECT t2.AC
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.AC IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.AC IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET AUL = (
	SELECT t2.AUL
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.AUL IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.AUL IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET ALL = (
	SELECT t2.ALL
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.ALL IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.ALL IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET AVo = (
	SELECT t2.AVo
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.AVo IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.AVo IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET AVa = (
	SELECT t2.AVa
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.AVa IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.AVa IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET AAdjO = (
	SELECT t2.AAdjO
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.AAdjO IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.AAdjO IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET AAdjH = (
	SELECT t2.AAdjH
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.AAdjH IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.AAdjH IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET AAdjL = (
	SELECT t2.AAdjL
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.AAdjL IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.AAdjL IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET AAdjC = (
	SELECT t2.AAdjC
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.AAdjC IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.AAdjC IS NULL;



UPDATE NullFilled_DropOrigin_OneHotEncoded_homogenous AS t
SET AAdjVo = (
	SELECT t2.AAdjVo
	FROM NullFilled_DropOrigin_OneHotEncoded_homogenous as t2
	WHERE 
		t2.Code = t.Code 
		AND t2.Date <= t.Date 
		AND t2.AAdjVo IS NOT NULL
	ORDER BY t2.Date DESC
	LIMIT 1
)
WHERE t.AAdjVo IS NULL;

