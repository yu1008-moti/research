import scripts.datap.graph.db_connect as db_connect

import pandas as pd
import numpy as np

def test_get_main_praice_table():
    res = db_connect.get_main_price_table()

    assert isinstance(res, pd.DataFrame), "Result is not a DataFrame"
    assert not res.empty, "Result DataFrame is empty"
    assert ~res.isna().any().any(), f"Result DataFrame contains NaN values: {~res.isna().any()}"