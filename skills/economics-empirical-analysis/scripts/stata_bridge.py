"""Stata bridge: Stata 16 batch mode now; official PyStata for a later 17+ install."""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, time
from pathlib import Path
import numpy as np
import pyreadstat

def write_json(path, value):
    path=Path(path); tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); tmp.replace(path)

def file_hash(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()

def stata_path(value=None):
    configured=value or os.environ.get('STATA_EXE')
    if not configured:
        raise ValueError('Set STATA_EXE or pass --stata-exe with a verified Stata executable')
    path=Path(configured).resolve()
    allowed={'statase-64.exe','statamp-64.exe','statabe-64.exe','stata-64.exe'}
    if not path.is_file() or path.name.lower() not in allowed:
        raise ValueError('Set STATA_EXE to a verified Stata executable')
    return path

def stata_quote(path):
    text=Path(path).resolve().as_posix()
    if any(c in text for c in ['"','`','$','\n','\r']): raise ValueError('Unsupported character in Stata path')
    return text

def run_batch(exe, do_file, cwd, timeout):
    started=time.time()
    process=subprocess.run([str(exe),'/e','do',str(Path(do_file).resolve())],cwd=str(cwd),
                           timeout=timeout,check=False,capture_output=True,text=True)
    return {'returncode':process.returncode,'elapsed_seconds':round(time.time()-started,3)}

def smoke(exe, output, timeout):
    out=Path(output).resolve()
    if out.exists(): raise FileExistsError('Smoke output already exists; use a new directory')
    out.mkdir(parents=True)
    result=out/'smoke-results.dta'; log=out/'smoke-execution.log'; marker=out/'SMOKE_COMPLETE.txt'; do=out/'smoke.do'
    do.write_text(f'''version 16.0
clear all
set more off
capture log close _all
log using "{stata_quote(log)}", text replace
set obs 100
generate double x = _n
generate double y = 1 + 2*x
regress y x, vce(robust)
assert abs(_b[x]-2)<1e-10
scalar bx = _b[x]
scalar sx = _se[x]
clear
set obs 1
generate double coefficient = bx
generate double standard_error = sx
generate str12 engine = "Stata 16"
save "{stata_quote(result)}", replace
file open done using "{stata_quote(marker)}", write text replace
file write done "complete" _n
file close done
log close
exit, clear
''',encoding='utf-8')
    execution=run_batch(exe,do,out,timeout)
    if execution['returncode']!=0 or not marker.is_file() or marker.read_text().strip()!='complete':
        raise RuntimeError('Stata batch did not produce a verified completion marker; inspect smoke-execution.log')
    frame,_=pyreadstat.read_dta(str(result)); coefficient=float(frame.coefficient.iloc[0]); se=float(frame.standard_error.iloc[0])
    if not np.isfinite([coefficient,se]).all() or abs(coefficient-2)>1e-10:
        raise RuntimeError('Stata smoke numerical assertion failed')
    receipt={'schema_version':'stata-execution/1.0','status':'complete','mode':'batch','version_target':'16.0',
             'edition_target':'se','executable_name':exe.name,'do_file':str(do),'do_sha256':file_hash(do),
             'log':str(log),'log_sha256':file_hash(log),'result':str(result),'result_sha256':file_hash(result),
             'coefficient':coefficient,'standard_error':se,**execution}
    write_json(out/'receipt.json',receipt); return receipt

def run_review(exe_value, run_dir, timeout=300):
    exe=stata_path(exe_value); root=Path(run_dir).resolve(); do=root/'code'/'review.do'
    if not do.is_file() or not (root/'processed'/'analysis.dta').is_file():
        raise ValueError('Run directory lacks review.do or analysis.dta')
    execution=run_batch(exe,do,root,timeout); marker=root/'stata'/'STATA_COMPLETE.txt'; log=root/'stata'/'execution.log'
    if execution['returncode']!=0 or not marker.is_file() or marker.read_text().strip()!='complete':
        raise RuntimeError('Stata review did not complete; inspect stata/execution.log')
    comparisons=[]
    request=json.loads((root/'request.json').read_text(encoding='utf-8'))
    for spec in request['models']:
        target=root/'models'/spec['spec_id']/'stata-results.csv'
        if spec['covariance']=='HC3':
            comparisons.append({'spec_id':spec['spec_id'],'status':'not-supported','reason':'Stata 16 HC3 parity not implemented'})
            continue
        if not target.is_file(): raise RuntimeError('Missing Stata result: '+str(target))
        import pandas as pd
        stata=pd.read_csv(target).set_index('term'); python=pd.read_csv(root/'models'/spec['spec_id']/'coefficients.csv').set_index('term')
        terms=['_cons' if x=='const' else x for x in python.index]
        common=[x for x in terms if x in stata.index]
        if not common: raise RuntimeError('No comparable Stata/Python coefficients')
        pyvals=np.array([python.loc['const' if x=='_cons' else x,'estimate'] for x in common],float)
        stvals=np.array([stata.loc[x,'estimate'] for x in common],float)
        pyse=np.array([python.loc['const' if x=='_cons' else x,'std_error'] for x in common],float)
        stse=np.array([stata.loc[x,'std_error'] for x in common],float)
        coefficient_delta=float(np.max(np.abs(pyvals-stvals))); se_delta=float(np.max(np.abs(pyse-stse)))
        status='matched' if coefficient_delta<1e-8 and se_delta<1e-8 else 'review-required'
        comparisons.append({'spec_id':spec['spec_id'],'status':status,'terms':len(common),
                            'max_abs_coefficient_delta':coefficient_delta,'max_abs_standard_error_delta':se_delta})
    receipt={'schema_version':'stata-execution/1.0','status':'complete','mode':'batch','executable_name':exe.name,
             'do_sha256':file_hash(do),'log_sha256':file_hash(log),'comparisons':comparisons,**execution}
    write_json(root/'stata'/'receipt.json',receipt); return receipt

def main():
    p=argparse.ArgumentParser(); mode=p.add_mutually_exclusive_group(required=True); mode.add_argument('--smoke',action='store_true'); mode.add_argument('--run-dir')
    p.add_argument('--stata-exe'); p.add_argument('--output'); p.add_argument('--timeout',type=int,default=120); args=p.parse_args()
    try:
        if args.smoke:
            if not args.output: raise ValueError('--output is required with --smoke')
            r=smoke(stata_path(args.stata_exe),args.output,args.timeout)
        else: r=run_review(args.stata_exe,args.run_dir,args.timeout)
        print(json.dumps({'status':r['status'],'mode':r['mode'],'result_sha256':r['result_sha256']})); return 0
    except Exception as exc:
        print(json.dumps({'status':'error','error':str(exc)},ensure_ascii=False)); return 1

if __name__=='__main__': raise SystemExit(main())
