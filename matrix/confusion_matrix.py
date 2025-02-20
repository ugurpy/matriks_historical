# import used libraries >>>>>>>
import itertools
import pandas as pd
import numpy as np
from matrix.up_down import *
from matrix.plot import plot_confusion_matrix, plt
import scipy.stats as stats
from sklearn.metrics import matthews_corrcoef, mutual_info_score
from sklearn.metrics import adjusted_rand_score, accuracy_score
from matrix.merge_zeros import merge_zeros
from multiprocessing import Pool

# <<<<<<<<<<<<<<<<<<<<<<


# read data from csv >>>>>>>>>>>>>>>>>>>>
dropbox_link = 'https://www.dropbox.com/sh/fdnc4b1x8e9fge7/AAA2UVr5l0k19qapPVfn3COOa?dl=0'
data_path: str = 'data/bist30data.csv'
export_folder = 'results/'
dt: dict = {'symbol': 'str', 'bid_price': 'float64', 'mid_price': 'float64'}
parse_dates: list = ['date']
data: pd.DataFrame = pd.read_csv(data_path, dtype=dt, parse_dates=parse_dates, index_col='date')
# <<<<<<<<<<<<<<<<<<<<<<

# create pivot table from data and get the permutation of symbols >>>>>>>
data = data.reset_index().pivot_table(index='date', columns='symbol', values='mid_price')
all_pairs = [list(pair) for pair in itertools.permutations(data.columns, 2)]
# <<<<<<<<<<<<<<<<<<<<<


error_list = list()
# <<<<<<<<<<<<<<<<<<<<<<<<<
count = 1


# get a each pair and do the following operations >>>>>>>>>>>>>>>>
def calculate(pair):
    log.append(pair)

    global count
    count = count + 1
    print(pair, ' : ', count)

    # select pairs >>>>>>>>
    pivot = data[pair[0]].dropna()
    other = data[pair[1]].dropna()
    # <<<<<<<<<<<<<<<<<<<<

    # calculate change for each day >>>>>>>>>>>>>>>>>
    pivot = pivot.resample('D').apply(lambda x: np.trim_zeros(x.diff().dropna())).droplevel(0)
    other = other.resample('D').apply(lambda x: np.trim_zeros(x.diff().dropna())).droplevel(0)

    change_df = pd.concat([pivot, other], axis=1)

    pivot_start_time: pd.Timestamp = pivot.index.min()
    end_time: pd.Timestamp = change_df.last_valid_index()
    change_df = change_df.between_time(start_time=pivot_start_time.time(), end_time=end_time.time())
    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<

    # up-down >>>>>>>>>>>>
    up_down: pd.DataFrame = change_df.groupby(change_df.index.date).apply(find_updown)
    up_down: pd.DataFrame = up_down.reset_index(drop=True)
    # <<<<<

    # Remove zeros from pivot under a certain duration >>>>
    up_down = merge_zeros(up_down, limit='0.5s')
    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

    y_pred = up_down.iloc[:, 1]
    y_true = up_down.iloc[:, 2]

    matrix = get_confusion_matrix(y_pred, y_true)

    matrix2d = np.delete(matrix, 1, 0).reshape(2, 2)

    # stats
    mcc = matthews_corrcoef(y_true, y_pred)
    acc_score = accuracy_score(y_true, y_pred)
    mi = mutual_info_score(y_true, y_pred)
    ari = adjusted_rand_score(y_true, y_pred)
    oddsratio, p_value = stats.fisher_exact(matrix2d)

    try:
        chi2, p, dof, ex = stats.chi2_contingency(matrix)
    except ValueError:
        error_list.append(pair)
        log.append((pair, ': için chi2 hesaplanamadı ve değerler nan geçildi !'))
        chi2, p, dof, ex = np.nan, np.nan, np.nan, np.nan

    plt.figure()
    plot_confusion_matrix(matrix, title='Normalized confusion matrix',
                          x_label=pair[0], y_label=pair[1], normalize=True)
    file_name = 'graphs_normalized/' + pair[0] + '_' + pair[1] + '.png'
    plt.savefig(export_folder + file_name)
    plt.close()

    plt.figure()
    plot_confusion_matrix(matrix, title='Confusion matrix, without normalized',
                          x_label=pair[0], y_label=pair[1], normalize=False)
    file_name = 'graphs/' + pair[0] + '_' + pair[1] + '.png'
    plt.savefig(export_folder + file_name)
    plt.close()

    s_index = ['matthews_corrcoef', 'accuracy_score', 'mutual_info_score',
               'adjusted_rand_score', 'oddsratio', 'p_value_fisher_exact', 'chi2', 'p_value_chi2', 'dof']

    return pd.Series(data=[mcc, acc_score, mi, ari, oddsratio, p_value, chi2, p, dof], name=tuple(pair), index=s_index)


if __name__ == '__main__':
    pool = Pool(processes=16)

    result = pool.map(calculate, all_pairs)

    result = pd.concat(result, axis=1)

    result.to_csv(export_folder + 'statistics.csv')
