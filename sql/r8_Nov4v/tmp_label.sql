select * exclude(column_type, count, null_percentage)
from
(
	summarize select
	* exclude(seq_Ri), list_sum(seq_Ri)
	from(
		select 
		*,
		list(NxLogRi) over(
			partition by cID
			order by tID
			rows between current row and 52 following
		) as seq_Ri
		from act.label.nxri
	)
	order by tID
);