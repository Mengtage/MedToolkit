"""Synthetic contingency-table adapter; preserve MedStat's method selection."""
import hashlib
from .core import canonical

METHODS = ('categorical_auto', 'chi2', 'fisher', 'yates')


def validate(payload):
    allowed = {'classification', 'method', 'table', 'row_labels', 'column_labels', '_retry_of'}
    if set(payload) - allowed:
        raise ValueError('列联表任务包含未允许的字段')
    table = payload.get('table')
    if not isinstance(table, list) or not 2 <= len(table) <= 10:
        raise ValueError('列联表需要2至10行')
    if not isinstance(table[0], list) or not 2 <= len(table[0]) <= 10:
        raise ValueError('列联表需要2至10列')
    width = len(table[0])
    for row in table:
        if not isinstance(row, list) or len(row) != width:
            raise ValueError('列联表必须为矩形')
        if any(type(v) is not int or not 0 <= v <= 1_000_000 for v in row):
            raise ValueError('频数必须为0至1000000的整数')
    if sum(map(sum, table)) > 1_000_000:
        raise ValueError('本地验收总频数上限1000000')
    if any(sum(row) == 0 for row in table) or any(sum(row[j] for row in table) == 0 for j in range(width)):
        raise ValueError('列联表存在零边际')
    if payload['method'] == 'yates' and (len(table), width) != (2, 2):
        raise ValueError('Yates仅支持2×2表')
    for key, size in (('row_labels', len(table)), ('column_labels', width)):
        labels = payload.get(key)
        if not isinstance(labels, list) or len(labels) != size:
            raise ValueError('行列标签必须与频数表对应')
        if any(not isinstance(v, str) or not v.strip() or len(v) > 100 for v in labels):
            raise ValueError('标签须为1至100字符的非空字符串')
        if len(set(labels)) != size:
            raise ValueError('同一维度的标签不得重复')


def analyze(store, pid, payload, jid):
    import scipy
    from .adapters import module
    validate(payload)
    path = 'MedStat/src/analysis/categorical_tests.py'
    adapter = module(path, 'medstat_categorical')
    method = 'auto' if payload['method'] == 'categorical_auto' else payload['method']
    result = adapter.CategoricalTestSelector.select_test(payload['table'], method)
    # Preserve the actual method name and approximation metadata from the original module.
    result.update({
        'requested_method': payload['method'],
        'table': payload['table'],
        'row_labels': payload['row_labels'], 'column_labels': payload['column_labels'],
        'n': sum(map(sum, payload['table'])),
        'input_sha256': hashlib.sha256(canonical({k: payload[k] for k in ('table', 'row_labels', 'column_labels')}).encode()).hexdigest(),
        'source': path, 'classification': payload.get('classification', 'synthetic'), 'llm_calls': 0,
        'environment': {'scipy': scipy.__version__},
        'orientation': '行列顺序与输入一致；2×2 OR=(左上×右下)/(右上×左下)',
    })
    name = store.save(pid, f'{jid}-statistics.json', result)
    return {'artifact': name, **result}
