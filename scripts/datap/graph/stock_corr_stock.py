import torch
import numpy as np
import pandas as pd
from statsmodels.regression.rolling import RollingOLS
import statsmodels.api as sm
from typing import List, Tuple
import scripts.datap.graph.const as c


__all__ = ['get_corr_edge']


def _get_nodeID(capm_data: pd.DataFrame, codeID: int, dateID: int) -> int:
    """
    Get the nodeID for a given codeID and dateID from the DataFrame.
    """
    nodeID = capm_data.loc[
        (capm_data['codeID'] == codeID) & (capm_data['dateID'] == dateID), 
        'nodeID'
    ].values[0]
    assert isinstance(nodeID, (int)), f"nodeID should be an integer, got {type(nodeID)}"
    return nodeID

################## ROLLING OLS AND CORRELATION CALCULATION ##################

def _get_indices_values(corr: torch.Tensor, mask: torch.Tensor):
    result = (corr*mask).to_sparse().coalesce()
    return result.indices().to(torch.long).cpu(), result.values().to(torch.float32).cpu()


def _calc_residuals(capm_data: pd.DataFrame):

    capm_data['residual'] = np.nan  # Initialize the residual column with NaN values
    capm_data['beta']     = np.nan  # Initialize the beta column with NaN values
    capm_data['alpha']    = np.nan  # Initialize the alpha column with NaN values

    short_length_codes = []
    
    for code in capm_data['codeID'].unique():
        df:pd.DataFrame = capm_data[capm_data['codeID'] == code]
        X = df['Rm'] # market return
        y = df['Ri'] # stock return

        assert len(X) == len(y), f"Length mismatch: X has {len(X)} rows, y has {len(y)} rows"

        if len(X) <= 2: # 自由度は「n-2」であり，少なくとも2つのデータ点が必要
            capm_data.loc[df.index, 'residual'] = 0.0
            capm_data.loc[df.index, 'alpha']    = 0.0
            capm_data.loc[df.index, 'beta']     = 0.0
            short_length_codes.append(code)
        else:
            X = sm.add_constant(data=X)
            result = RollingOLS(endog=y, exog=X, window=min(c.DEFAULT_WINDOW_SIZE, len(X))).fit()
            pred_y = result.params[c.JENSEN_ALPHA] + result.params[c.BETA] * df['Rm'] # y'= α + βx
            
            capm_data.loc[df.index, 'residual'] = y - pred_y # r = y - y'
            capm_data.loc[df.index, 'alpha']    = result.params[c.JENSEN_ALPHA] # α
            capm_data.loc[df.index, 'beta']     = result.params[c.BETA] # β

        print(f"\rProcessed codeID: {code}", end='')
    print(f"\nshort_length_codes: {short_length_codes} ({len(short_length_codes)})")
    print('Finished')


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

        yield pivot_tensor[t], edge_indices, edge_values

        x_new = pivot_tensor[t]
        x_old = pivot_tensor[t - c.DEFAULT_WINDOW_SIZE]
        sum  += x_new - x_old
        gram_matrix += torch.outer(x_new, x_new) - torch.outer(x_old, x_old)

################## ROLLING OLS AND CORRELATION CALCULATION ##################

def get_corr_edge(capm_data: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:

    capm_data = capm_data.sort_values(by=['tID', 'cID']).reset_index(drop=True)

    _calc_residuals(capm_data) 

    return_matrix = capm_data.pivot(index='tID', columns='cID', values='residual')
    pivot_tensor = torch.tensor(
        return_matrix.values,
        dtype=torch.float32,
        device=c.DEVICE
    )
    tIDs = return_matrix.index.to_numpy()
    cID2lnID = capm_data.loc[:, ['tID', 'cID', 'lnID']].drop_duplicates()

    edge_index_list, attr_list, tIDs_list = [], [], []

    for i, (t, edge_indices, edge_values) in enumerate(_calc_corr_matrix(pivot_tensor), 1):
        t = tIDs[t]
        cID2lnID_t = cID2lnID.loc[cID2lnID['tID'] == t, :].set_index('cID')['lnID'].to_dict()
        edge_indices = np.vectorize(cID2lnID_t.get)(edge_indices.cpu().numpy())

        edge_index_list.append(edge_indices)
        attr_list.append(edge_values)
        tIDs_list.append(torch.full((edge_values.shape[0],), t, dtype=torch.int16))

        print(f"\r{i}/{len(tIDs)}: {t}", end='')
    print("\nFinished")

    edge_index = torch.cat(edge_index_list, dim=1).to(torch.long).cpu().numpy()
    edge_attr  = torch.cat(attr_list, dim=0).to(torch.float32).cpu().numpy()
    tIDs = torch.cat(tIDs_list, dim=0).to(torch.int16).cpu().numpy()

    return edge_index, tIDs, edge_attr