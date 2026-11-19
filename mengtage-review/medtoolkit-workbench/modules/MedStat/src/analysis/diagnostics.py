"""
统计诊断模块
基于statsmodels设计的统计检验和诊断功能
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union
import traceback

try:
    from scipy import stats as scipy_stats
    from scipy.stats import (
        ttest_ind, ttest_rel, ttest_1samp,
        mannwhitneyu, wilcoxon, kruskal,
        pearsonr, spearmanr, chi2_contingency, fisher_exact,
        shapiro, kstest, normaltest, anderson
    )
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False

try:
    import statsmodels.api as sm
    from statsmodels.stats.weightstats import ttest_ind as sm_ttest_ind
    from statsmodels.stats.diagnostic import (
        lilliefors, het_breuschpagan, het_white, acorr_ljungbox,
        normal_ad, breaks_hansen, spec_white
    )
    from statsmodels.stats.proportion import binom_test, binom_proportion_test
    from statsmodels.stats.multicomp import pairwise_tukeyhsd, multi_comparison
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False


class NormalityTests:
    """正态性检验"""

    @staticmethod
    def shapiro_wilk(data: np.ndarray) -> Dict:
        """Shapiro-Wilk检验（样本量<5000）"""
        if len(data) < 3:
            return {'error': '样本量至少需要3个'}
        if len(data) > 5000:
            data = data[:5000]

        stat, p_value = shapiro(data)
        return {
            'test': 'Shapiro-Wilk',
            'statistic': float(stat),
            'p_value': float(p_value),
            'normal': "true" if p_value > 0.05 else "false",
            'interpretation': '数据服从正态分布' if p_value > 0.05 else '数据不服从正态分布'
        }

    @staticmethod
    def kolmogorov_smirnov(data: np.ndarray) -> Dict:
        """Kolmogorov-Smirnov检验"""
        stat, p_value = kstest(data, 'norm', args=(np.mean(data), np.std(data)))
        return {
            'test': 'Kolmogorov-Smirnov',
            'statistic': float(stat),
            'p_value': float(p_value),
            'normal': "true" if p_value > 0.05 else "false",
            'interpretation': '数据服从正态分布' if p_value > 0.05 else '数据不服从正态分布'
        }

    @staticmethod
    def anderson_darling(data: np.ndarray) -> Dict:
        """Anderson-Darling检验"""
        result = anderson(data, dist='norm')
        if hasattr(result, 'critical_values'):
            crit_vals = result.critical_values.tolist()
            sig_levels = result.significance_level.tolist()
        else:
            crit_vals = result.critical_values.tolist() if hasattr(result, 'critical_values') else []
            sig_levels = result.significance_level.tolist() if hasattr(result, 'significance_level') else []
        interpretation = f'在{sig_levels[2] if len(sig_levels) > 2 else 5}%显著性水平下检验' if result.statistic < (crit_vals[2] if len(crit_vals) > 2 else 0.784) else '拒绝正态性假设'
        return {
            'test': 'Anderson-Darling',
            'statistic': float(result.statistic),
            'critical_values': crit_vals,
            'significance_levels': sig_levels,
            'interpretation': interpretation
        }

    @staticmethod
    def lilliefors_test(data: np.ndarray) -> Dict:
        """Lilliefors检验"""
        if not STATSMODELS_AVAILABLE:
            return {'error': 'statsmodels未安装'}

        stat, p_value = lilliefors(data)
        return {
            'test': 'Lilliefors',
            'statistic': float(stat),
            'p_value': float(p_value),
            'normal': p_value > 0.05,
            'interpretation': '数据服从正态分布' if p_value > 0.05 else '数据不服从正态分布'
        }

    @staticmethod
    def all_tests(data: np.ndarray) -> Dict:
        """运行所有正态性检验"""
        results = {}

        if len(data) >= 3:
            results['shapiro_wilk'] = NormalityTests.shapiro_wilk(data)

        results['kolmogorov_smirnov'] = NormalityTests.kolmogorov_smirnov(data)
        results['anderson_darling'] = NormalityTests.anderson_darling(data)

        if STATSMODELS_AVAILABLE:
            results['lilliefors'] = NormalityTests.lilliefors_test(data)

        normal_count = sum(1 for r in results.values() if isinstance(r, dict) and r.get('normal') == "true")
        results['summary'] = {
            'total_tests': len(results),
            'tests_rejecting_normality': len(results) - normal_count,
            'conclusion': '数据可能服从正态分布' if normal_count >= len(results) / 2 else '数据可能不服从正态分布'
        }

        return results


class VarianceTests:
    """方差齐性检验"""

    @staticmethod
    def levene(*groups: np.ndarray) -> Dict:
        """Levene检验（对非正态数据更稳健）"""
        stat, p_value = scipy_stats.levene(*groups)
        return {
            'test': 'Levene',
            'statistic': float(stat),
            'p_value': float(p_value),
            'equal_variance': p_value > 0.05,
            'interpretation': '方差齐性' if p_value > 0.05 else '方差不齐'
        }

    @staticmethod
    def bartlett(*groups: np.ndarray) -> Dict:
        """Bartlett检验（要求正态分布）"""
        stat, p_value = scipy_stats.bartlett(*groups)
        return {
            'test': 'Bartlett',
            'statistic': float(stat),
            'p_value': float(p_value),
            'equal_variance': p_value > 0.05,
            'interpretation': '方差齐性' if p_value > 0.05 else '方差不齐'
        }

    @staticmethod
    def fligner_killeen(*groups: np.ndarray) -> Dict:
        """Fligner-Killeen检验（非参数）"""
        stat, p_value = scipy_stats.fligner(*groups)
        return {
            'test': 'Fligner-Killeen',
            'statistic': float(stat),
            'p_value': float(p_value),
            'equal_variance': p_value > 0.05,
            'interpretation': '方差齐性' if p_value > 0.05 else '方差不齐'
        }


class CorrelationTests:
    """相关性检验"""

    @staticmethod
    def pearson_correlation(x: np.ndarray, y: np.ndarray) -> Dict:
        """Pearson相关系数检验"""
        if len(x) != len(y):
            return {'error': '两个变量的样本量必须相同'}

        r, p_value = pearsonr(x, y)
        return {
            'test': 'Pearson',
            'correlation': float(r),
            'p_value': float(p_value),
            'n': len(x),
            'significant': "true" if p_value < 0.05 else "false",
            'interpretation': f'显著相关 (r={r:.4f})' if p_value < 0.05 else f'不显著相关 (r={r:.4f})'
        }

    @staticmethod
    def spearman_correlation(x: np.ndarray, y: np.ndarray) -> Dict:
        """Spearman秩相关系数（非参数）"""
        if len(x) != len(y):
            return {'error': '两个变量的样本量必须相同'}

        r, p_value = spearmanr(x, y)
        return {
            'test': 'Spearman',
            'correlation': float(r),
            'p_value': float(p_value),
            'n': len(x),
            'significant': "true" if p_value < 0.05 else "false",
            'interpretation': f'显著相关 (ρ={r:.4f})' if p_value < 0.05 else f'不显著相关 (ρ={r:.4f})'
        }

    @staticmethod
    def correlation_matrix(data: pd.DataFrame, method: str = 'pearson') -> Dict:
        """计算相关矩阵"""
        if method == 'pearson':
            corr_matrix = data.corr(method='pearson')
        elif method == 'spearman':
            corr_matrix = data.corr(method='spearman')
        else:
            return {'error': f'不支持的方法: {method}'}

        return {
            'method': method,
            'matrix': corr_matrix.to_dict(),
            'n_variables': len(corr_matrix)
        }


class MeanComparisonTests:
    """均值比较检验"""

    @staticmethod
    def ttest_independent(group1: np.ndarray, group2: np.ndarray,
                          equal_var: bool = True) -> Dict:
        """独立样本t检验"""
        if equal_var:
            stat, p_value = ttest_ind(group1, group2)
            test_name = 'Student t-test'
        else:
            stat, p_value = ttest_ind(group1, group2, equal_var=False)
            test_name = 'Welch t-test'

        n1, n2 = len(group1), len(group2)
        mean1, mean2 = np.mean(group1), np.mean(group2)
        var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
        pooled_std = np.sqrt(((n1-1)*var1 + (n2-1)*var2) / (n1+n2-2))
        cohens_d = (mean1 - mean2) / pooled_std if pooled_std > 0 else 0

        return {
            'test': test_name,
            'statistic': float(stat),
            'p_value': float(p_value),
            'group1': {'n': n1, 'mean': float(mean1), 'std': float(np.std(group1, ddof=1))},
            'group2': {'n': n2, 'mean': float(mean2), 'std': float(np.std(group2, ddof=1))},
            'mean_diff': float(mean1 - mean2),
            'cohens_d': float(cohens_d),
            'significant': "true" if p_value < 0.05 else "false",
            'interpretation': f'两组均值存在显著差异 (d={cohens_d:.4f})' if p_value < 0.05 else '两组均值无显著差异'
        }

    @staticmethod
    def ttest_paired(group1: np.ndarray, group2: np.ndarray) -> Dict:
        """配对样本t检验"""
        if len(group1) != len(group2):
            return {'error': '配对样本量必须相同'}

        stat, p_value = ttest_rel(group1, group2)
        mean_diff = np.mean(group1 - group2)
        std_diff = np.std(group1 - group2, ddof=1)
        cohens_d = mean_diff / std_diff if std_diff > 0 else 0

        return {
            'test': 'Paired t-test',
            'statistic': float(stat),
            'p_value': float(p_value),
            'n_pairs': len(group1),
            'mean_diff': float(mean_diff),
            'std_diff': float(std_diff),
            'cohens_d': float(cohens_d),
            'significant': "true" if p_value < 0.05 else "false",
            'interpretation': f'配对差异显著 (d={cohens_d:.4f})' if p_value < 0.05 else '配对差异不显著'
        }

    @staticmethod
    def ttest_one_sample(data: np.ndarray, pop_mean: float) -> Dict:
        """单样本t检验"""
        stat, p_value = ttest_1samp(data, pop_mean)
        mean_data = np.mean(data)

        return {
            'test': 'One-sample t-test',
            'statistic': float(stat),
            'p_value': float(p_value),
            'sample_mean': float(mean_data),
            'pop_mean': float(pop_mean),
            'mean_diff': float(mean_data - pop_mean),
            'significant': "true" if p_value < 0.05 else "false",
            'interpretation': f'样本均值与总体均值存在显著差异' if p_value < 0.05 else '样本均值与总体均值无显著差异'
        }

    @staticmethod
    def anova_one_way(*groups: np.ndarray) -> Dict:
        """单因素方差分析"""
        f_stat, p_value = scipy_stats.f_oneway(*groups)

        group_stats = []
        for i, g in enumerate(groups):
            group_stats.append({
                'group': i + 1,
                'n': len(g),
                'mean': float(np.mean(g)),
                'std': float(np.std(g, ddof=1))
            })

        ss_between = sum(len(g) * (np.mean(g) - np.mean(np.concatenate(groups)))**2 for g in groups)
        ss_total = np.sum((np.concatenate(groups) - np.mean(np.concatenate(groups)))**2)
        ss_within = ss_total - ss_between
        df_between = len(groups) - 1
        df_within = len(np.concatenate(groups)) - len(groups)
        ms_between = ss_between / df_between if df_between > 0 else 0
        ms_within = ss_within / df_within if df_within > 0 else 0
        eta_squared = ss_between / ss_total if ss_total > 0 else 0

        return {
            'test': 'One-way ANOVA',
            'f_statistic': float(f_stat),
            'p_value': float(p_value),
            'groups': group_stats,
            'df_between': df_between,
            'df_within': df_within,
            'ss_between': float(ss_between),
            'ss_within': float(ss_within),
            'eta_squared': float(eta_squared),
            'significant': "true" if p_value < 0.05 else "false",
            'interpretation': '组间存在显著差异' if p_value < 0.05 else '组间无显著差异'
        }

    @staticmethod
    def kruskal_wallis(*groups: np.ndarray) -> Dict:
        """Kruskal-Wallis H检验（非参数）"""
        h_stat, p_value = kruskal(*groups)

        group_stats = []
        for i, g in enumerate(groups):
            group_stats.append({
                'group': i + 1,
                'n': len(g),
                'median': float(np.median(g)),
                'mean_rank': float(scipy_stats.rankdata(np.concatenate(groups))[sum(len(groups[j]) for j in range(i)):sum(len(groups[j]) for j in range(i+1))].mean())
            })

        return {
            'test': 'Kruskal-Wallis H',
            'h_statistic': float(h_stat),
            'p_value': float(p_value),
            'groups': group_stats,
            'significant': "true" if p_value < 0.05 else "false",
            'interpretation': '组间存在显著差异' if p_value < 0.05 else '组间无显著差异'
        }

    @staticmethod
    def mannwhitney_u(group1: np.ndarray, group2: np.ndarray) -> Dict:
        """Mann-Whitney U检验（非参数）"""
        u_stat, p_value = mannwhitneyu(group1, group2, alternative='two-sided')

        n1, n2 = len(group1), len(group2)
        mean_rank1 = scipy_stats.rankdata(np.concatenate([group1, group2]))[:n1].mean()
        mean_rank2 = scipy_stats.rankdata(np.concatenate([group1, group2]))[n1:].mean()

        r = 1 - (2*u_stat) / (n1*n2)

        return {
            'test': 'Mann-Whitney U',
            'u_statistic': float(u_stat),
            'p_value': float(p_value),
            'n1': n1,
            'n2': n2,
            'mean_rank1': float(mean_rank1),
            'mean_rank2': float(mean_rank2),
            'rank_biserial_correlation': float(r),
            'significant': "true" if p_value < 0.05 else "false",
            'interpretation': '两组分布存在显著差异' if p_value < 0.05 else '两组分布无显著差异'
        }

    @staticmethod
    def wilcoxon_signed_rank(data1: np.ndarray, data2: np.ndarray) -> Dict:
        """Wilcoxon符号秩检验（配对非参数）"""
        if len(data1) != len(data2):
            return {'error': '配对样本量必须相同'}

        diff = data1 - data2
        nonzero_diffs = diff[diff != 0]

        if len(nonzero_diffs) < 5:
            return {'error': '非零差值样本量太少'}

        w_stat, p_value = wilcoxon(data1, data2)

        return {
            'test': 'Wilcoxon signed-rank',
            'w_statistic': float(w_stat),
            'p_value': float(p_value),
            'n_pairs': len(data1),
            'n_nonzero': len(nonzero_diffs),
            'median_diff': float(np.median(diff)),
            'significant': "true" if p_value < 0.05 else "false",
            'interpretation': '配对差异显著' if p_value < 0.05 else '配对差异不显著'
        }


class ProportionTests:
    """比例检验"""

    @staticmethod
    def binom_test_successes(n_success: int, n_trials: int, p0: float = 0.5,
                            alternative: str = 'two-sided') -> Dict:
        """二项检验（单样本比例）"""
        if n_trials < 1 or n_success < 0 or n_success > n_trials:
            return {'error': '参数无效'}

        p_hat = n_success / n_trials
        result = binom_test(n_success, n_trials, p0, alternative=alternative)

        return {
            'test': 'Binomial test',
            'n_success': n_success,
            'n_trials': n_trials,
            'sample_proportion': float(p_hat),
            'hypothesized_proportion': p0,
            'p_value': float(result),
            'significant': "true" if result < 0.05 else "false",
            'interpretation': f'比例与{p0}存在显著差异' if result < 0.05 else f'比例与{p0}无显著差异'
        }

    @staticmethod
    def chi_square_test(contingency_table: np.ndarray) -> Dict:
        """卡方检验（独立性/拟合优度）"""
        if contingency_table.ndim != 2:
            return {'error': '需要2维列联表'}

        if contingency_table.shape[0] < 2 or contingency_table.shape[1] < 2:
            return {'error': '列联表至少需要2x2'}

        chi2, p_value, dof, expected = chi2_contingency(contingency_table)
        cramers_v = np.sqrt(chi2 / (contingency_table.sum() * min(contingency_table.shape[0] - 1, contingency_table.shape[1] - 1)))

        return {
            'test': 'Chi-square test',
            'chi2_statistic': float(chi2),
            'p_value': float(p_value),
            'df': int(dof),
            'cramers_v': float(cramers_v),
            'sample_size': int(contingency_table.sum()),
            'significant': "true" if p_value < 0.05 else "false",
            'expected_frequencies': expected.tolist(),
            'interpretation': '变量之间存在显著关联' if p_value < 0.05 else '变量之间无显著关联'
        }

    @staticmethod
    def fisher_exact_test(table: np.ndarray) -> Dict:
        """Fisher精确检验（2x2表）"""
        if table.shape != (2, 2):
            return {'error': '需要2x2列联表'}

        odds_ratio, p_value = fisher_exact(table)

        return {
            'test': "Fisher's exact test",
            'odds_ratio': float(odds_ratio),
            'p_value': float(p_value),
            'table': table.tolist(),
            'significant': "true" if p_value < 0.05 else "false",
            'interpretation': '变量之间存在显著关联' if p_value < 0.05 else '变量之间无显著关联'
        }


class EffectSizeCalculator:
    """效应量计算器"""

    @staticmethod
    def cohens_d(group1: np.ndarray, group2: np.ndarray, pooled: bool = True) -> float:
        """Cohen's d 效应量"""
        mean1, mean2 = np.mean(group1), np.mean(group2)
        var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
        n1, n2 = len(group1), len(group2)

        if pooled:
            pooled_var = ((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2)
            return (mean1 - mean2) / np.sqrt(pooled_var)
        else:
            return (mean1 - mean2) / np.sqrt((var1 + var2) / 2)

    @staticmethod
    def eta_squared(f_stat: float, df_between: int, df_within: int) -> float:
        """Eta平方（方差解释比例）"""
        return (f_stat * df_between) / (f_stat * df_between + df_within)

    @staticmethod
    def odds_ratio_to_risk_ratio(odds_ratio: float, p0: float) -> float:
        """将优势比转换为风险比"""
        return odds_ratio / (1 - p0 + p0 * odds_ratio)

    @staticmethod
    def number_needed_to_treat(p1: float, p2: float) -> float:
        """需要治疗人数（NNT）"""
        return 1 / abs(p1 - p2)


class MultipleComparisons:
    """多重比较校正"""

    @staticmethod
    def bonferroni_correction(p_values: List[float], alpha: float = 0.05) -> Dict:
        """Bonferroni校正"""
        n_tests = len(p_values)
        adjusted_alpha = alpha / n_tests

        results = []
        n_significant = 0
        for i, p in enumerate(p_values):
            significant = p < adjusted_alpha
            if significant:
                n_significant += 1
            results.append({
                'test': i + 1,
                'p_value': float(p),
                'adjusted_alpha': adjusted_alpha,
                'significant': "true" if significant else "false"
            })

        return {
            'method': 'Bonferroni',
            'original_alpha': alpha,
            'adjusted_alpha': adjusted_alpha,
            'n_tests': n_tests,
            'n_significant': n_significant,
            'results': results
        }

    @staticmethod
    def false_discovery_rate(p_values: List[float], alpha: float = 0.05) -> Dict:
        """False Discovery Rate校正（Benjamini-Hochberg）"""
        n = len(p_values)
        sorted_indices = np.argsort(p_values)
        sorted_p = np.array(p_values)[sorted_indices]

        adjusted_p = np.zeros(n)
        for i in range(n - 1, -1, -1):
            bh_factor = n / (i + 1)
            adjusted_p[sorted_indices[i]] = min(sorted_p[i] * bh_factor, 1.0)

            if i < n - 1:
                adjusted_p[sorted_indices[i]] = min(adjusted_p[sorted_indices[i]], adjusted_p[sorted_indices[i + 1]])

        results = []
        n_significant = 0
        for i, p in enumerate(p_values):
            significant = adjusted_p[i] < alpha
            if significant:
                n_significant += 1
            results.append({
                'test': i + 1,
                'p_value': float(p),
                'adjusted_p_value': float(adjusted_p[i]),
                'significant': "true" if significant else "false"
            })

        return {
            'method': 'Benjamini-Hochberg FDR',
            'original_alpha': alpha,
            'n_tests': n,
            'n_significant': n_significant,
            'results': results
        }

    @staticmethod
    def tukey_hsd(data_dict: Dict[str, np.ndarray], alpha: float = 0.05) -> Dict:
        """Tukey HSD多重比较"""
        if not STATSMODELS_AVAILABLE:
            return {'error': 'statsmodels未安装'}

        groups = list(data_dict.keys())
        data_list = [data_dict[g] for g in groups]

        try:
            tukey_result = pairwise_tukeyhsd(np.concatenate(data_list),
                                             np.repeat(groups, [len(d) for d in data_list]),
                                             alpha=alpha)

            results = []
            for i in range(len(tukey_result.groupsunique)):
                for j in range(i + 1, len(tukey_result.groupsunique)):
                    results.append({
                        'comparison': f"{tukey_result.groupsunique[i]} vs {tukey_result.groupsunique[j]}",
                        'meandiff': float(tukey_result.meandiffs[i, j]),
                        'p_adj': float(tukey_result.pvalues[i, j]),
                        'lower': float(tukey_result.confint[:, 0][i, j]),
                        'upper': float(tukey_result.confint[:, 1][i, j]),
                        'reject': bool(tukey_result.reject[i, j])
                    })

            return {
                'method': 'Tukey HSD',
                'alpha': alpha,
                'groups': groups,
                'results': results
            }
        except Exception as e:
            return {'error': str(e)}
