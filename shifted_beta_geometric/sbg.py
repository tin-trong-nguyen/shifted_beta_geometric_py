"""
Implementation of the shifted beta geometric (sBG) model from "How to Project Customer Retention" (Fader and Hardie 2006)

http://www.brucehardie.com/papers/021/sbg_2006-05-30.pdf

Apache 2 License
"""

from math import log

import numpy as np

from scipy.optimize import minimize
from scipy.special import hyp2f1

__author__ = "JD Maturen"


def fit(data, init_params=[1.0, 1.0], return_res=False, raise_error=False):
    """Fit sBG to data.

    data: 2D array. each row represents one cohort, containing the absolute numbers of users retained in observed time period.
    init_params: initial [alpha, beta].

    Return: [alpha, beta] fitted"""
    func = lambda params: - log_likelihood(params[0], params[1], data)
    res = minimize(func, init_params, method="nelder-mead", options={"xtol": 1e-8})
    result = res.x

    if res.status != 0:
        result = np.array([None, None])
        if raise_error:
            raise Exception(res.message)

    if return_res:
        result = res

    return result


def log_likelihood(alpha, beta, data):
    """Function to maximize to obtain ideal alpha and beta parameters using data across multiple (contiguous) cohorts.
    `data` must be a list of cohorts each with an absolute number per observed time unit."""
    if alpha <= 0 or beta <= 0:
        return -9999

    probabilities = generate_probabilities(alpha, beta, max(map(len, data)))

    total = 0
    for i, cohort in enumerate(data, start=1):
        for j in range(1, len(cohort)):
            total += (cohort[j-1] - cohort[j]) * log(probabilities[j])  # python index from 0
        total += cohort[-1] * log(survivor(probabilities, len(cohort) - 1))

    return total


def generate_probabilities(alpha, beta, max_range):
    """Generate probabilities in one pass.
    Return p = list of probabilities generated using sbg.
    p[0] is assigned to None to align index (so p[t] = p(T=t) in the paper)."""
    p = [None, alpha / (alpha + beta)]
    for t in range(2, max_range + 1):
        pt = (beta + t - 2) / (alpha + beta + t - 1) * p[t - 1]
        p.append(pt)
    return p


def survivor(probabilities, t):
    """Input: probabilities generated by generate_probabilities().
    Return: value of S(t) (survivor function)"""
    return 1 - sum(probabilities[1:t+1])


def predicted_retention(alpha, beta, t):
    """Predicted retention probability at t. Function 8 in the paper.
    t is indexed similar to the paper (start at 1)"""
    return (beta + t - 1) / (alpha + beta + t - 1)


def generate_predicted_retentions_x0(alpha, beta, max_range):
    """Generate list of retention rates from model parameters.
    Input:
        alpha_beta (list): [alpha, beta]
        max_range (int): how many retention rates to generate
    Return: list of retention rates, indexing from 0 (r[0] = r1 in the paper)
    *Using different indexing for this method to make it easy to compare with actual retentions.
    """
    if alpha is None or beta is None or max_range <= 0:
        return None
    return [predicted_retention(alpha, beta, t) for t in range(1, max_range + 1)]


def predicted_survival(alpha, beta, max_range, cohort_user_count=1):
    """Predicted survivor count for all period in max_range.
    When cohort_user_count=1 (default), returns survival probability (percentage of customers retained).
    Function 1 in the paper. *S[0] = S0 = 1 * cohort_user_count"""
    s = [1, predicted_retention(alpha, beta, 1)]
    for t in range(2, max_range):
        s.append(predicted_retention(alpha, beta, t) * s[t - 1])
    s = list(map(lambda x: x * cohort_user_count, s))
    return s


def generate_predicted_survival_x0(alpha, beta, max_range, cohort_user_count=1):
    """Same as predicted_survival, but using different indexing for this method
    to make it easy to compare with actual retentions."""
    if alpha is None or beta is None or max_range <= 0:
        return None
    return predicted_survival(alpha, beta, max_range + 1, cohort_user_count)[1:]


def derl(alpha, beta, d, n):
    """discounted expected residual lifetime from "Customer-Base Valuation in a Contractual Setting: The Perils of
    Ignoring Heterogeneity" (Fader and Hardie 2009)
    n is the count of periods the cohort has (cohorts with only period 0 has 1 period)"""
    return (beta + n - 1) / (alpha + beta + n - 1) * hyp2f1(
        1, beta + n, alpha + beta + n, 1 / (1 + d)
    )


def calculate_diff_with_lag_1(row):
    a = np.array(row)
    b = a[1:].copy()
    b.resize(len(a))
    return b / a


def calculate_retention_rates(data):
    """Calculate retention_rates from multi_cohort data"""
    return list(map(calculate_diff_with_lag_1, data))


def smape(actual, predicted):
    """Calculate SMAPE from 2 list/array of data.
    Output * 100% = % difference"""
    return np.average(2 * np.abs(np.subtract(actual, predicted)) / (np.abs(actual) + np.abs(predicted)))


def higher_prediction_ratio(actual, predicted):
    """Take 2 list of numbers, return proportion of predicted that are higher than actual"""
    b = np.array(predicted) > np.array(actual)
    return sum(b) / len(b)


def test_generate_probabilities():
    print('testing generate_probabilities()')
    p = generate_probabilities(1, 1, 7)
    print(
        p[0] is None and
        np.allclose(p[1:], [0.5, 0.167, 0.083, 0.050, 0.033, 0.024, 0.018], atol=1e-3)
    )


def test_survivor():
    print('testing survivor()')
    p = [None, 0.5, 0.167, 0.083, 0.050, 0.033, 0.024, 0.018]
    s = survivor(p, 7)
    print(np.allclose(s, 0.125, atol=1e-3))


def test_fit_one_cohort():
    "sGB paper"
    print('testing fit() one cohort')
    data = [
        [1000, 869, 743, 653, 593, 551, 517, 491]
    ]
    alpha, beta = fit(data)

    print('testing log_likelihood')
    print(np.allclose(log_likelihood(1.0, 1.0, data), -2115.5, 1e-3))
    print('testing alpha beta')
    print(np.allclose(alpha, 0.668, 1e-3) and np.allclose(beta, 3.806, 1e-3))


def test_fit_multi_cohort():
    "sGB multi-cohort paper"
    print('testing fit() multi cohort')
    data = [
        [10000, 8000, 6480, 5307, 4391],
        [10000, 8000, 6480, 5307],
        [10000, 8000, 6480],
        [10000, 8000],
    ]
    alpha, beta = fit(data)
    print('testing alpha beta')
    print(np.allclose(alpha, 3.80, 1e-2) and np.allclose(beta, 15.19, 1e-2))


def test_derl():
    print('testing derl case 1')
    print(np.allclose(derl(3.80, 15.20, 0.1, 5), 3.84, 1e-2))
    print(np.allclose(derl(3.80, 15.20, 0.1, 3), 3.59, 1e-2))
    print(np.allclose(derl(3.80, 15.20, 0.1, 1), 3.31, 1e-2))

    print(np.allclose(derl(0.067, 0.267, 0.1, 5), 10.19, 1e-2))
    print(np.allclose(derl(0.067, 0.267, 0.1, 3), 9.86, 1e-2))
    print(np.allclose(derl(0.067, 0.267, 0.1, 1), 7.68, 1e-2))


def test():
    test_generate_probabilities()
    test_survivor()
    test_fit_one_cohort()
    test_fit_multi_cohort()
    test_derl()


if __name__ == "__main__":
    test()
