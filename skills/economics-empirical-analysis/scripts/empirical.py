"""Local reproducible empirical runner. No remote upload or arbitrary code execution."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import jsonschema
import numpy as np
import pandas as pd
import pyreadstat
import statsmodels.api as sm

SKILL = Path(__file__).resolve().parents[1]
PACKAGES = ['pandas', 'numpy', 'scipy', 'statsmodels', 'pyreadstat', 'openpyxl', 'jsonschema', 'matplotlib']


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic checkpoint; serialization is strict (NaN/Infinity forbidden).
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(payload + '\n', encoding='utf-8')
    temp.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def latex_escape(value):
    replacements = {
        '\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$',
        '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}',
        '~': r'\textasciitilde{}', '^': r'\textasciicircum{}',
    }
    return ''.join(replacements.get(char, char) for char in str(value))


def write_coefficient_latex(table, path, spec_id):
    rows = [
        r'\begin{table}[htbp]', r'\centering',
        r'\caption{Coefficient estimates: ' + latex_escape(spec_id) + '}',
        r'\begin{tabular}{lrrrrr}', r'\toprule',
        r'Term & Estimate & Std. error & $p$-value & 95\% CI low & 95\% CI high \\',
        r'\midrule',
    ]
    for row in table.itertuples(index=False):
        estimate = f'{float(row.estimate):.6g}'
        stderr = f'{float(row.std_error):.6g}'
        pvalue = f'{float(row.p_value):.6g}'
        low = f'{float(row.ci_low):.6g}'
        high = f'{float(row.ci_high):.6g}'
        rows.append(f'{latex_escape(row.term)} & {estimate} & {stderr} & {pvalue} & {low} & {high} \\\\')
    rows.extend([r'\bottomrule', r'\end{tabular}', r'\end{table}'])
    Path(path).write_text('\n'.join(rows) + '\n', encoding='utf-8')


def write_report_latex(request, model_states, limitations, root):
    rows = [
        r'\documentclass[UTF8]{ctexart}',
        r'\usepackage[a4paper,margin=2.5cm]{geometry}',
        r'\usepackage{booktabs}',
        r'\usepackage{graphicx}',
        r'\usepackage[hidelinks]{hyperref}',
        r'\title{Empirical run: ' + latex_escape(request['run_id']) + '}',
        r'\author{paper-writing-workflow}',
        r'\date{}',
        r'\begin{document}',
        r'\maketitle',
        r'\section{Research question}',
        latex_escape(request['question']),
        r'\section{Models}',
    ]
    for state in model_states:
        spec_id = state['spec_id']
        rows.append(r'\subsection{' + latex_escape(spec_id) + '}')
        if state['status'] == 'complete':
            result = read_json(root / 'models' / spec_id / 'result.json')
            rows.append(latex_escape(
                f"N={result['n_used']}; missing exclusions={result['n_missing_excluded']}; "
                f"covariance={result['spec']['covariance']}."
            ))
            rows.extend([
                r'\input{../models/' + spec_id + r'/coefficients.tex}',
                r'\begin{figure}[htbp]',
                r'\centering',
                r'\includegraphics[width=0.85\linewidth]{../models/' + spec_id + r'/coefficients.pdf}',
                r'\caption{Coefficient estimates and 95\% confidence intervals.}',
                r'\end{figure}',
            ])
        else:
            rows.append(r'\textbf{Failed:} ' + latex_escape(state.get('error', 'unknown error')))
    rows.extend([r'\section{Limitations}', r'\begin{itemize}'])
    rows.extend(r'\item ' + latex_escape(item) for item in limitations)
    rows.extend([r'\end{itemize}', r'\end{document}'])
    (root / 'results' / 'report.tex').write_text('\n'.join(rows) + '\n', encoding='utf-8')


def validate(value, name):
    jsonschema.Draft202012Validator(read_json(SKILL / 'schemas' / name)).validate(value)


def safe_child(root, name):
    target = (Path(root) / name).resolve()
    if not target.is_relative_to(Path(root).resolve()) or target == Path(root).resolve():
        raise ValueError('Artifact path escapes run directory')
    return target


def environment():
    return {'python': platform.python_version(), 'platform': platform.platform(),
            'packages': {p: importlib.metadata.version(p) for p in PACKAGES}}


def load_data(path, spec):
    suffix = path.suffix.lower()
    metadata = {'format': suffix, 'source_sha256': sha(path)}
    if suffix == '.csv':
        frame = pd.read_csv(path, encoding=spec.get('encoding', 'utf-8-sig'),
                            dtype=spec.get('dtypes'), keep_default_na=False, na_values=[''])
    elif suffix == '.xlsx':
        if not spec.get('sheet'):
            raise ValueError('Excel sheet must be explicitly named')
        frame = pd.read_excel(path, sheet_name=spec['sheet'], dtype=spec.get('dtypes'),
                              keep_default_na=False, na_values=[''], engine='openpyxl')
        metadata['sheet'] = spec['sheet']
        metadata['warning'] = 'Cached cell values only; Excel formulas are not recalculated.'
    elif suffix == '.dta':
        frame, meta = pyreadstat.read_dta(str(path), apply_value_formats=False, user_missing=True)
        metadata.update(variable_labels=meta.column_names_to_labels,
                        value_labels=meta.variable_value_labels,
                        original_formats=meta.original_variable_types,
                        tagged_missing=meta.missing_user_values)
        if meta.missing_user_values:
            raise ValueError('Tagged Stata missing values require an explicit reviewed recode')
        if spec.get('dtypes'):
            frame = frame.astype(spec['dtypes'])
    else:
        raise ValueError('Supported intake formats: .csv, .xlsx, .dta (not pickle/macros)')
    if frame.empty or frame.columns.duplicated().any():
        raise ValueError('Empty data or duplicate column names')
    if not all(isinstance(c, str) for c in frame.columns):
        raise ValueError('Column names must be strings')
    if spec.get('primary_key'):
        keys = spec['primary_key']
        if frame[keys].isna().any().any() or frame.duplicated(keys).any():
            raise ValueError('Declared primary key is missing or duplicated')
    metadata['columns'] = [{'name': c, 'dtype': str(frame[c].dtype),
                            'missing': int(frame[c].isna().sum())} for c in frame]
    metadata['rows'] = len(frame)
    return frame, metadata


def estimate(frame, spec, out):
    out.mkdir(parents=True, exist_ok=False)
    columns = list(dict.fromkeys([spec['outcome']] + spec['regressors'] +
                                 spec.get('fixed_effects', []) + ([spec['cluster']] if spec['covariance'] == 'cluster' else [])))
    sample = frame[columns].dropna()
    y = pd.to_numeric(sample[spec['outcome']], errors='raise').astype(float)
    X = sample[spec['regressors']].apply(pd.to_numeric, errors='raise').astype(float)
    for c in spec.get('fixed_effects', []):
        if sample[c].nunique() > 100:
            raise ValueError('More than 100 FE levels: use a reviewed absorbed-FE adapter')
        X = pd.concat([X, pd.get_dummies(sample[c], prefix='fe_' + c, drop_first=True, dtype=float)], axis=1)
    X.insert(0, 'const', 1.0)
    if X.columns.duplicated().any() or not np.isfinite(X.to_numpy()).all() or not np.isfinite(y).all():
        raise ValueError('Invalid design matrix: duplicate names or nonfinite values')
    if len(sample) <= X.shape[1] or np.linalg.matrix_rank(X.to_numpy()) != X.shape[1]:
        raise ValueError('Rank deficiency or insufficient residual degrees of freedom')
    kwargs = {}
    warnings = ['Association only; causal identification has not been validated.']
    groups = None
    if spec['covariance'] == 'cluster':
        groups = int(sample[spec['cluster']].nunique())
        if groups < 2:
            raise ValueError('At least two clusters required')
        if groups < 30:
            warnings.append('Fewer than 30 clusters: conventional cluster inference may be unreliable.')
        kwargs['cov_kwds'] = {'groups': sample[spec['cluster']], 'use_correction': True, 'df_correction': True}
    fit = sm.OLS(y, X).fit(cov_type=spec['covariance'], use_t=True, **kwargs)
    ci = fit.conf_int(alpha=0.05)
    table = pd.DataFrame({'term': fit.params.index, 'estimate': fit.params.values,
                          'std_error': fit.bse.values, 'p_value': fit.pvalues.values,
                          'ci_low': ci.iloc[:, 0].values, 'ci_high': ci.iloc[:, 1].values})
    if not np.isfinite(table.drop(columns='term').to_numpy()).all():
        raise ValueError('Nonfinite inference; inspect perfect fit or degenerate covariance')
    table.to_csv(out / 'coefficients.csv', index=False)
    write_coefficient_latex(table, out / 'coefficients.tex', spec['spec_id'])
    fit.cov_params().to_csv(out / 'covariance.csv', index=True)
    sample_ids = [int(i) for i in sample.index]
    write_json(out / 'sample.json', {'processed_row_indices': sample_ids})
    result = {'schema_version': 'empirical-model/1.0', 'spec': spec, 'n_input': len(frame),
              'n_used': int(fit.nobs), 'n_missing_excluded': len(frame)-len(sample),
              'sample_sha256': hashlib.sha256(json.dumps(sample_ids).encode()).hexdigest(),
              'clusters': groups, 'df_resid': float(fit.df_resid), 'r_squared': float(fit.rsquared),
              'inference': 'two-sided t; 95% confidence intervals; no multiplicity adjustment',
              'coefficients': table.to_dict(orient='records'), 'warnings': warnings}
    write_json(out / 'result.json', result)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    visible = table[table.term.isin(spec['regressors'])]
    fig, ax = plt.subplots(figsize=(7, max(2.5, .45 * len(visible))))
    for i, row in enumerate(visible.itertuples()):
        ax.plot([row.ci_low, row.ci_high], [i, i], color='#315f85')
        ax.plot(row.estimate, i, 'o', color='#315f85')
    ax.set_yticks(range(len(visible)), visible.term)
    ax.axvline(0, color='grey', linestyle='--'); ax.set_xlabel('Coefficient and 95% CI')
    ax.set_title(spec['spec_id']); fig.tight_layout()
    fig.savefig(out / 'coefficients.svg')
    fig.savefig(out / 'coefficients.pdf')
    plt.close(fig)
    return result


def stata_script(request, out):
    (out/'stata').mkdir(exist_ok=True)
    lines = ['* GENERATED, HASHED, AND EXECUTED ONLY WHEN engines includes stata', 'version 16.0', 'clear all',
             'set more off', 'capture log close _all', 'log using "stata/execution.log", text replace',
             'import delimited using "processed/analysis.csv", clear varnames(1) encoding(utf-8) asdouble',
             'save "processed/analysis-stata16.dta", replace']
    for spec in request['models']:
        names = [spec['outcome']] + spec['regressors'] + spec.get('fixed_effects', [])
        if spec.get('cluster'): names.append(spec['cluster'])
        if not all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,31}', n) for n in names):
            lines.append('* ' + spec['spec_id'] + ': manual variable mapping required'); continue
        if spec['covariance'] == 'HC3':
            lines.append('* ' + spec['spec_id'] + ': HC3 support/parity requires installed-version review'); continue
        rhs = ' '.join(spec['regressors'] + ['i.' + x for x in spec.get('fixed_effects', [])])
        vce = 'cluster ' + spec['cluster'] if spec['covariance'] == 'cluster' else 'robust'
        result='models/'+spec['spec_id']+'/stata-results'
        lines.extend(['* ' + spec['spec_id'], 'regress ' + spec['outcome'] + ' ' + rhs + ', vce(' + vce + ')',
          'tempname B V handle', 'matrix `B\' = e(b)\'', 'matrix `V\' = e(V)', 'local names : rownames `B\'', 'local k = rowsof(`B\')',
          'postfile `handle\' str80 term double estimate std_error using "'+result+'.dta", replace',
          'forvalues j=1/`k\' {', '  local term : word `j\' of `names\'',
          '  post `handle\' ("`term\'") (`B\'[`j\',1]) (sqrt(`V\'[`j\',`j\']))', '}', 'postclose `handle\'',
          'preserve', 'use "'+result+'.dta", clear', 'export delimited using "'+result+'.csv", replace', 'restore'])
    lines.extend(['file open done using "stata/STATA_COMPLETE.txt", write text replace',
                  'file write done "complete" _n', 'file close done', 'log close', 'exit, clear'])
    (out / 'code' / 'review.do').write_text('\n'.join(lines)+'\n', encoding='utf-8')


def verify(run_dir):
    root = Path(run_dir).resolve()
    bundle = read_json(root / 'bundle.json'); validate(bundle, 'bundle.schema.json')
    for artifact in bundle['artifacts']:
        file = safe_child(root, artifact['path'])
        if not file.is_file() or file.stat().st_size != artifact['bytes'] or sha(file) != artifact['sha256']:
            raise ValueError('Artifact missing or changed: ' + artifact['path'])
    return bundle


def run(request_path, output_root, stata_exe=None):
    request_path = Path(request_path).resolve()
    request = read_json(request_path); validate(request, 'request.schema.json')
    ids = [s['spec_id'] for s in request['models']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate model spec_id')
    sources = [(request_path.parent / item['path']).resolve() for item in request['inputs']]
    env = environment()
    engines=request.get('engines',['python'])
    if 'stata' in engines and not stata_exe: raise ValueError('Request selects Stata but --stata-exe was not supplied')
    signature = {'request': request, 'sources': [sha(p) for p in sources], 'engine': sha(__file__), 'environment': env,
                 'stata_executable': str(Path(stata_exe).resolve()) if stata_exe else None}
    fingerprint = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
    root = safe_child(output_root, request['run_id'])
    if root.exists():
        if not (root / 'bundle.json').is_file():
            raise ValueError('Interrupted run retained. Use a new run_id and parent_run_id.')
        previous = verify(root)
        if previous['fingerprint'] != fingerprint:
            raise ValueError('Run ID already used with different inputs/code/environment')
        return previous
    root.mkdir(parents=True)
    for folder in ['raw', 'metadata', 'processed', 'models', 'results', 'code']:
        (root / folder).mkdir()
    write_json(root / 'request.json', request)
    shutil.copy2(__file__, root / 'code' / 'empirical.py')
    shutil.copytree(SKILL / 'schemas', root / 'schemas')
    # Snapshot engine can find schemas from its run root (code/../schemas).
    state = {'status': 'running', 'stage': 'intake', 'models': [], 'started_at': datetime.now(timezone.utc).isoformat()}
    write_json(root / 'checkpoint.json', state)
    limits = [('Cloud not configured.' if 'stata' in engines else 'Stata not executed; cloud not configured.'), 'OLS/FE association is not proof of causality.',
              'Local artifacts may contain sensitive data; not approved for external release.']
    try:
        frame = None; cleaning = []
        for i, (source, spec) in enumerate(zip(sources, request['inputs'])):
            raw = root / 'raw' / (str(i) + source.suffix.lower())
            shutil.copy2(source, raw)
            if sha(raw) != signature['sources'][i]: raise ValueError('Input changed during intake')
            incoming, meta = load_data(raw, spec)
            write_json(root / 'metadata' / f'input-{i}.json', meta)
            if i == 0:
                if 'merge' in spec: raise ValueError('First input must not specify merge')
                frame = incoming
            else:
                merge = spec.get('merge')
                if not merge: raise ValueError('Every additional input requires an explicit merge')
                keys = merge['on']
                if frame[keys].isna().any().any() or incoming[keys].isna().any().any():
                    raise ValueError('Missing join keys are not allowed')
                if (set(frame) & set(incoming)) - set(keys): raise ValueError('Overlapping non-key columns')
                frame = frame.merge(incoming, on=keys, how='left', validate=merge['validate'], indicator=True)
                cleaning.append({'input': i, 'join_counts': {str(k): int(v) for k,v in frame['_merge'].value_counts().items()}})
                frame = frame.drop(columns='_merge')
        for col, codes in request.get('missing_codes', {}).items():
            count = int(frame[col].isin(codes).sum()); frame[col] = frame[col].mask(frame[col].isin(codes))
            cleaning.append({'column': col, 'missing_codes': codes, 'converted': count})
        for rule in request.get('filters', []):
            before = len(frame); mask = frame[rule['column']].isin(rule['values'])
            frame = frame.loc[mask if rule['op'] == 'keep' else ~mask].copy()
            cleaning.append({'filter': rule, 'before': before, 'after': len(frame)})
        frame = frame.reset_index(drop=True)
        if frame.empty: raise ValueError('No observations remain')
        write_json(root / 'metadata' / 'cleaning.json', cleaning)
        frame.to_csv(root / 'processed' / 'analysis.csv', index=False)
        # DTA export is numeric/string interchange; rich original metadata lives in raw/metadata.
        pyreadstat.write_dta(frame, str(root / 'processed' / 'analysis.dta'), version=15)
        frame.describe(include='all').to_csv(root / 'results' / 'descriptive.csv')
        state['stage'] = 'estimation'; write_json(root / 'checkpoint.json', state)
        for spec in request['models']:
            try:
                result = estimate(frame, spec, root / 'models' / spec['spec_id'])
                state['models'].append({'spec_id': spec['spec_id'], 'status': 'complete'})
            except Exception as exc:
                state['models'].append({'spec_id': spec['spec_id'], 'status': 'failed', 'error': str(exc)})
            write_json(root / 'checkpoint.json', state)
        stata_script(request, root)
        status = 'complete' if all(m['status'] == 'complete' for m in state['models']) else 'partial'
        if 'stata' in engines:
            from stata_bridge import run_review
            stata_receipt=run_review(stata_exe,root)
            env['stata']={'status':stata_receipt['status'],'mode':stata_receipt['mode'],
                          'comparisons':stata_receipt['comparisons']}
            if any(x['status']=='review-required' for x in stata_receipt['comparisons']):
                status='partial'; limits.append('At least one Python–Stata comparison requires review.')
        write_report_latex(request, state['models'], limits, root)
    except Exception as exc:
        status = 'failed'; state['error'] = str(exc)
    state.update(status=status, stage='finished'); write_json(root / 'checkpoint.json', state)
    write_json(root / 'environment.json', env)
    installed = sorted(f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions())
    (root / 'requirements-lock.txt').write_text('\n'.join(installed)+'\n', encoding='utf-8')
    artifacts = [{'path': str(p.relative_to(root)).replace('\\','/'), 'sha256': sha(p), 'bytes': p.stat().st_size}
                 for p in sorted(root.rglob('*')) if p.is_file()]
    bundle = {'schema_version': 'empirical-bundle/1.0', 'project_id': request['project_id'],
              'run_id': request['run_id'], 'status': status, 'fingerprint': fingerprint,
              'environment': env, 'models': state['models'], 'artifacts': artifacts, 'limitations': limits}
    validate(bundle, 'bundle.schema.json'); write_json(root / 'bundle.json', bundle)
    verify(root)
    return bundle


def backup(run_dir, destination):
    root = Path(run_dir).resolve(); bundle = verify(root)
    destination = Path(destination).resolve()
    if destination.is_relative_to(root): raise ValueError('Backup must be outside the run directory')
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / (bundle['run_id'] + '-' + sha(root/'bundle.json')[:12] + '.zip')
    # Exclusive creation: never overwrite a previous backup.
    files = [a['path'] for a in bundle['artifacts']] + ['bundle.json']
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name in files: z.write(safe_child(root, name), name)
    with zipfile.ZipFile(archive) as z:
        for name in files:
            if hashlib.sha256(z.read(name)).hexdigest() != sha(safe_child(root, name)):
                raise ValueError('Backup read-back mismatch')
    receipt = {'schema_version':'empirical-backup/1.0', 'status':'local-verified-not-cloud',
               'path':str(archive), 'sha256':sha(archive), 'encrypted':False, 'files':len(files)}
    write_json(archive.with_suffix('.receipt.json'), receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    r = sub.add_parser('run'); r.add_argument('--request', required=True); r.add_argument('--output-root', required=True); r.add_argument('--stata-exe')
    v = sub.add_parser('verify'); v.add_argument('--run-dir', required=True)
    b = sub.add_parser('backup'); b.add_argument('--run-dir', required=True); b.add_argument('--destination', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'doctor': result = {'python':environment(), 'stata':'deferred', 'cloud':'not-configured'}
        elif args.command == 'run':
            bundle = run(args.request,args.output_root,args.stata_exe); result = {k:bundle[k] for k in ['run_id','status','models']}
        elif args.command == 'verify': result = {'verified': True, 'status':verify(args.run_dir)['status']}
        else: result = backup(args.run_dir,args.destination)
        print(json.dumps(result,ensure_ascii=False)); return 1 if result.get('status') in ['failed','partial'] else 0
    except Exception as exc:
        print(json.dumps({'status':'error','error':str(exc)},ensure_ascii=False)); return 1


if __name__ == '__main__':
    sys.exit(main())
