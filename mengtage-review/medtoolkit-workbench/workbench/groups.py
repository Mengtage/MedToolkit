"""Synthetic numeric group comparisons using the existing MedStat implementation."""
import hashlib
import importlib
import math
import sys
import types
from .core import ROOT, canonical


def validate(payload):
    if set(payload) - {'classification', 'method', 'group', 'value', 'rows', '_retry_of'}:
        raise ValueError('组间比较包含未允许的字段')
    group, value = payload.get('group'), payload.get('value')
    if any(not isinstance(k, str) or not k.strip() or len(k) > 100 for k in (group, value)) or group == value:
        raise ValueError('分组列与数值列须为不同的非空名称')
    rows = payload.get('rows')
    if not isinstance(rows, list) or not 4 <= len(rows) <= 10000:
        raise ValueError('需要4至10000行合成数据')
    groups = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {group, value}:
            raise ValueError('每行仅允许分组列与数值列')
        label, number = row[group], row[value]
        if not isinstance(label, str) or not label.strip() or len(label) > 100:
            raise ValueError('分组标签必须为非空字符串，不允许缺失')
        values = groups.setdefault(label, [])
        if number is not None:
            if type(number) not in (int, float) or not math.isfinite(number) or abs(number) > 1e100:
                raise ValueError('数值必须有限且绝对值不超过1e100，缺失用null')
            values.append(number)
    if not 2 <= len(groups) <= 10 or any(len(v) < 2 for v in groups.values()):
        raise ValueError('需要2至10组，每组至少2个非缺失观察；不自动删除不足样本的组')
    if not any(len(set(v)) > 1 for v in groups.values()):
        raise ValueError('所有组内方差均为零，当前检验组合不可估计')
    return groups


def load_analyzer():
    # Namespace package permits the module's relative import without loading unrelated analyses.
    name = '_workbench_medstat_analysis'
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(ROOT / 'modules/MedStat/src/analysis')]
        sys.modules[name] = package
    return importlib.import_module(name + '.group_analysis').GroupAnalyzer


def analyze(store, pid, payload, jid):
    import pandas as pd
    import scipy
    groups = validate(payload)
    df = pd.DataFrame(payload['rows'])
    result = load_analyzer()(df, {payload['value']: 'numeric_continuous'}, payload['group']).analyze_numeric(payload['value'])
    # Fail explicitly instead of writing NaN/Infinity as apparently usable statistics.
    def finite(obj):
        if isinstance(obj, float) and not math.isfinite(obj):
            raise ValueError('计算结果不可估计或数值溢出')
        if isinstance(obj, dict):
            for value in obj.values(): finite(value)
        elif isinstance(obj, (list, tuple)):
            for value in obj: finite(value)
    finite(result)
    labels = list(groups)
    rows = payload['rows']
    missing = {g: sum(row[payload['group']] == g and row[payload['value']] is None for row in rows) for g in labels}
    result.update({
        'method': 'group_numeric', 'group': payload['group'], 'value': payload['value'],
        'group_order': labels, 'input_rows': len(rows),
        'complete_rows': sum(map(len, groups.values())), 'missing_by_group': missing,
        'excluded_missing_rows': sum(missing.values()), 'classification': payload.get('classification', 'synthetic'), 'llm_calls': 0,
        'input_sha256': hashlib.sha256(canonical({k: payload[k] for k in ('rows', 'group', 'value')}).encode()).hexdigest(),
        'source': 'MedStat/src/analysis/group_analysis.py',
        'environment': {'pandas': pd.__version__, 'scipy': scipy.__version__},
        'test_policy': '沿用旧版：两组同时返回Welch、Mann–Whitney及Cohen d；多组返回ANOVA和Kruskal–Wallis；未自动选择主要检验',
        'direction': '两组差值与Cohen d按首个出现组减第二组；Mann–Whitney U对应首组',
    })
    name = store.save(pid, f'{jid}-statistics.json', result)
    return {'artifact': name, **result}
