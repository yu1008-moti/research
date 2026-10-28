import torch
import numpy as np
import pandas as pd
from statsmodels.regression.rolling import RollingOLS
import statsmodels.api as sm
from typing import List, Tuple
import scripts.datap.graph.const as c
import os


__all__ = ['get_corr_edge']

################## ROLLING OLS AND CORRELATION CALCULATION ##################

def _get_indices_values(corr: torch.Tensor, mask: torch.Tensor):
    result = (corr*mask).to_sparse().coalesce()
    return result.indices().to(torch.long).cpu(), result.values().to(torch.float32).cpu()


def _calc_residuals(capm_data: pd.DataFrame):

    capm_data['residual'] = np.nan  # Initialize the residual column with NaN values
    capm_data['beta']     = np.nan  # Initialize the beta column with NaN values
    capm_data['alpha']    = np.nan  # Initialize the alpha column with NaN values

    shorter_than_freedom_deg = []
    shorter_than_window_size = []
    num_cID = len(capm_data['cID'].unique())

    for i, code in enumerate(capm_data['cID'].unique(), 1):
        df:pd.DataFrame = capm_data[capm_data['cID'] == code]
        X = df['Rm'] # market return
        y = df['Ri'] # stock return

        assert len(X) == len(y), f"Length mismatch: X has {len(X)} rows, y has {len(y)} rows"

        if len(X) <= 2: # 自由度は「n-2」であり，少なくとも2つのデータ点が必要
            # capm_data.loc[df.index, 'residual'] = 0.0
            # capm_data.loc[df.index, 'alpha']    = 0.0
            # capm_data.loc[df.index, 'beta']     = 0.0

            # if residual is 0.0, situation means capm is perfectly fitted
            # we don't calc corr for those stock
            # because it is not enough data to calc corr

            shorter_than_freedom_deg.append(code)
        elif len(X) <= c.DEFAULT_WINDOW_SIZE:
            shorter_than_window_size.append(code)
        else:
            X = sm.add_constant(data=X)
            result = RollingOLS(endog=y, exog=X, window=c.DEFAULT_WINDOW_SIZE).fit()
            pred_y = result.params[c.JENSEN_ALPHA] + result.params[c.BETA] * df['Rm'] # y'= α + βx
            
            capm_data.loc[df.index, 'residual'] = y - pred_y # r = y - y'
            capm_data.loc[df.index, 'alpha']    = result.params[c.JENSEN_ALPHA] # α
            capm_data.loc[df.index, 'beta']     = result.params[c.BETA] # β

        print(f"\r[{i:4d}/{num_cID}] Processed cID: {code}", end='')
    print(f"\n[WARNING]shorter_than_freedom_deg: {shorter_than_freedom_deg} ({len(shorter_than_freedom_deg)}) was set 0.0 to all params.")
    print(f"[WARNING]shorter_than_window_size: {shorter_than_window_size} ({len(shorter_than_window_size)}) was set 0.0 to all params.")
    print(f"Displayed codes aren't able to have corr edge.")
    print('Finished')
    capm_data.to_parquet(c.CAPM_DATA_FILE_PATH, index=False)  # Save the DataFrame to a Parquet file


def _calc_corr_matrix(pivot_tensor: torch.Tensor):
    T, _ = pivot_tensor.shape
    buf = pivot_tensor[:c.DEFAULT_WINDOW_SIZE, :]
    sum = torch.sum(buf, dim=0)
    gram_matrix = buf.T @ buf

    for t in range(c.DEFAULT_WINDOW_SIZE, T):
        mean = sum / c.DEFAULT_WINDOW_SIZE
        cov = (gram_matrix / c.DEFAULT_WINDOW_SIZE) - torch.outer(mean, mean)
        std = torch.sqrt(torch.diag(cov))
        corr = cov / torch.outer(std, std)
        corr = torch.nan_to_num(corr, nan=0.0) 
        corr.fill_diagonal_(0)
        mask = torch.abs(corr) > c.CORR_THRESHOLD
        # mask = corr > c.CORR_THRESHOLD

        edge_indices, edge_values = _get_indices_values(corr, mask)

        assert edge_indices.shape[0] == 2
        assert edge_indices.shape[1] == edge_values.shape[0]

        yield t, edge_indices, edge_values

        x_new = pivot_tensor[t]
        x_old = pivot_tensor[t - c.DEFAULT_WINDOW_SIZE]
        sum  += x_new - x_old
        gram_matrix += torch.outer(x_new, x_new) - torch.outer(x_old, x_old)

################## ROLLING OLS AND CORRELATION CALCULATION ##################

def get_corr_edge(capm_data: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:

    capm_data = capm_data.sort_values(by=['tID', 'cID']).reset_index(drop=True)

    if not os.path.exists(c.CAPM_DATA_FILE_PATH):
        print(f"\t[INFO] {c.CAPM_DATA_FILE_PATH} does not exist. Calculating residuals...")
        _calc_residuals(capm_data)
    else:
        capm_data = pd.read_parquet(c.CAPM_DATA_FILE_PATH)
        assert 'residual' in capm_data.columns, "The 'residual' column is missing in the capm_data DataFrame."
        assert 'alpha' in capm_data.columns, "The 'alpha' column is missing in the capm_data DataFrame."
        assert 'beta' in capm_data.columns, "The 'beta' column is missing in the capm_data DataFrame."

    capm_data = capm_data[~capm_data["residual"].isna()]

    residual_matrix = capm_data.pivot(index='tID', columns='cID', values='residual')
    pivot_tensor = torch.tensor(
        residual_matrix.values,
        dtype=torch.float32,
        device=c.DEVICE
    )
    tIDs = residual_matrix.index.to_numpy()
    cIDs = residual_matrix.columns.to_numpy()
    lnIDs = capm_data.loc[:, ['tID', 'cID', 'lnID']]
    assert pivot_tensor.shape[0] == len(tIDs), f"Shape mismatch: pivot_tensor has {pivot_tensor.shape[0]} rows, but tIDs has {len(tIDs)} elements."

    edge_index_list, attr_list, tIDs_list = [], [], []
    num_empty = 0

    for i, (t, edge_indices, edge_values) in enumerate(_calc_corr_matrix(pivot_tensor), 1):
        t = tIDs[t]
        lnIDs_t = lnIDs.loc[lnIDs['tID'] == t, ['cID', 'lnID']].set_index('cID')['lnID']
        expanded_lnIDs_t = torch.tensor(lnIDs_t.reindex(cIDs, fill_value=torch.nan).to_numpy(), dtype=torch.int32)  # Fill missing cIDs with -1
        if edge_indices.shape[1] > 0:
            edge_indices[0] = expanded_lnIDs_t[edge_indices[0]]
            edge_indices[1] = expanded_lnIDs_t[edge_indices[1]]
            edge_index_list.append(edge_indices)
            attr_list.append(edge_values)
            tIDs_list.append(torch.full((edge_values.shape[0],), t, dtype=torch.int16))
        else: num_empty += 1
        print(f"\r[{i:4d}/{len(tIDs)}(empty:{num_empty:4d})] Processed tID: {t}", end='')
    print("\nFinished")

    edge_index = torch.cat(edge_index_list, dim=1).to(torch.long).cpu().numpy()
    edge_attr  = torch.cat(attr_list, dim=0).to(torch.float32).cpu().numpy()
    tIDs = torch.cat(tIDs_list, dim=0).to(torch.int16).cpu().numpy()

    return edge_index, tIDs, edge_attr