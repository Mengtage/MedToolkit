"""Baseline tables with explicit types, missingness and legacy test policy."""
import hashlib
import math
import warnings
from .core import canonical


def validate(payload):
    if set(payload) - {'classification', 'method', 'rows', 'variable_types', 'strata', '_retry_of'}:
        raise ValueError('基线表包含未允许的字段')
    types = payload.get('variable_types')
    if not isinstance(types, dict) or not 1 <= len(types) <= 30:
        raise ValueError('需指定1至30列的变量类型')
    if any(not isinstance(k, str) or not k.strip() or len(k) > 100 or v not in ('numeric_continuous', 'categorical') for k, v in types.items()):
        raise ValueError('仅支持显式连续数值型和字符串分类变量')
    strata = payload.get('strata')
    if strata is not None and (not isinstance(strata, str) or types.get(strata) != 'categorical'):
        raise ValueError('分组列必须包含在类型字典中且为分类变量')
    variables = [k for k in types if k != strata]
    if not variables: raise ValueError('至少提供一个非分组变量')
    rows = payload.get('rows')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 10000:
        raise ValueError('需要1至10000行合成数据')
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(types):
            raise ValueError('数据列必须与类型字典完全对应')
        for name, kind in types.items():
            value = row[name]
            if value is None:
                if name == strata: raise ValueError('分组列不允许缺失')
                continue
            if kind == 'numeric_continuous':
                if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1e100:
                    raise ValueError('数值必须有限且绝对值不超过1e100')
            elif not isinstance(value, str) or not value.strip() or len(value) > 100:
                raise ValueError('分类值必须是非空字符串，缺失用null')
    labels = list(dict.fromkeys(row[strata] for row in rows)) if strata else ['Overall']
    if strata and not 2 <= len(labels) <= 10:
        raise ValueError('分组基线表需要2至10组')
    grouped = {label: [r for r in rows if not strata or r[strata] == label] for label in labels}
    for name in variables:
        valid = [[r[name] for r in subset if r[name] is not None] for subset in grouped.values()]
        if not strata and not valid[0]: raise ValueError('当前入口不接受全缺失变量')
        if strata:
            minimum = 2 if types[name] == 'numeric_continuous' else 1
            if any(len(v) < minimum for v in valid):
                raise ValueError('各组数值变量至少2个有效值，分类变量至少1个；不静默删除组')
            if types[name] == 'numeric_continuous' and not any(len(set(v)) > 1 for v in valid):
                raise ValueError('所有组内方差为零，当前检验组合不可估计')
            if types[name] == 'categorical' and len(set(v for group in valid for v in group)) < 2:
                raise ValueError('分组分类比较至少需要两个有效水平')
    return variables, grouped


def analyze(store, pid, payload, jid):
    import pandas as pd
    import numpy as np
    import scipy
    from .adapters import module
    variables, groups = validate(payload)
    source = 'MedStat/src/analysis/tableone.py'
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        result = module(source, 'medstat_tableone').TableOne(
            pd.DataFrame(payload['rows']), payload['variable_types'], payload.get('strata')).generate()
    # DataFrame has structural NaN in fields not applicable to a row's variable type.
    table = []
    numeric_fields = {'mean', 'sd', 'median', 'q25', 'q75'}
    for row in result['table'].to_dict(orient='records'):
        for key, value in row.items():
            if row['type'] == 'numeric' and key in numeric_fields and pd.isna(value):
                if key != 'sd' or row['n'] > 1:
                    raise ValueError('描述统计结果不可估计')
            if pd.isna(value): row[key] = None
        table.append(row)
    result['table'] = table
    boundaries = []
    def plain(value, path=''):
        if isinstance(value, np.generic): value = value.item()
        if isinstance(value, float) and not math.isfinite(value):
            # Fisher OR may be infinite while its exact P value remains valid.
            if path.endswith('.statistic') and any(path == f'p_values.{i}.statistic' and r.get('test') == "Fisher's Exact" for i, r in enumerate(result['p_values'])):
                boundaries.append(path)
                return None
            raise ValueError('统计结果不可估计或数值溢出')
        if isinstance(value, dict): return {k: plain(v, f'{path}.{k}' if path else k) for k, v in value.items()}
        if isinstance(value, list): return [plain(v, f'{path}.{i}') for i, v in enumerate(value)]
        return value
    result = plain(result)
    if payload.get('strata'):
        df = pd.DataFrame(payload['rows'])
        for test in result['p_values']:
            if test['type'] == 'categorical':
                contingency = pd.crosstab(df[payload['strata']], df[test['variable']])
                test['row_labels'] = list(contingency.index)
                test['column_labels'] = list(contingency.columns)
                test['contingency_table'] = contingency.values.tolist()
                if test['test'] == "Fisher's Exact":
                    test['statistic_name'] = 'odds_ratio'
                    test['odds_ratio_boundary'] = test['statistic'] is None or test['statistic'] == 0
    result.update({
        'method': 'tableone', 'classification': 'synthetic', 'llm_calls': 0,
        'input_rows': len(payload['rows']), 'variable_types': payload['variable_types'],
        'group_order': list(groups),
        'missingness': {g: {name: {'n_valid': sum(r[name] is not None for r in rows), 'n_missing': sum(r[name] is None for r in rows)} for name in variables} for g, rows in groups.items()},
        'percentage_denominator': 'nonmissing_within_group',
        'nonfinite_boundary_fields': boundaries,
        'warnings': [{'category': w.category.__name__, 'message': str(w.message)} for w in caught],
        'test_policy': '沿用旧版：按全样本正态性选择展示及数值检验；正态两组使用等方差t检验，非Welch；分类检验遵循TableOne原规则',
        'source': source, 'environment': {'pandas': pd.__version__, 'scipy': scipy.__version__},
        'input_sha256': hashlib.sha256(canonical({k: payload.get(k) for k in ('rows', 'variable_types', 'strata')}).encode()).hexdigest(),
    })
    name = store.save(pid, f'{jid}-statistics.json', result)
    return {'artifact': name, **result}
