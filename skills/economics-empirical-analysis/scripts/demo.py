"""Create and execute a reproducible synthetic village-panel demonstration."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import empirical as e


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--destination',required=True); args=parser.parse_args()
    root=Path(args.destination).resolve(); root.mkdir(parents=True,exist_ok=False)
    rng=np.random.default_rng(20260904)
    village=np.repeat(np.arange(40),6); year=np.tile(np.arange(2010,2016),40)
    trade=rng.uniform(0,1,len(village)); income=rng.normal(8,1,len(village))
    turnout=.4+.12*trade+.01*income+rng.normal(0,.06,len(village))
    frame=pd.DataFrame({'village':village,'year':year,'trade':trade,'income':income,'turnout':turnout})
    frame.to_csv(root/'synthetic.csv',index=False)
    request={'schema_version':'empirical-request/1.0','project_id':'synthetic-rural-demo','run_id':'round-01',
             'parent_run_id':None,'literature_project_id':None,'question':'Synthetic only: demonstrate workflow, not evidence about rural China.',
             'sensitivity':'synthetic','inputs':[{'path':'synthetic.csv','primary_key':['village','year']}],
             'models':[
                 {'spec_id':'baseline','purpose':'primary','rationale':'Synthetic demonstration baseline',
                  'outcome':'turnout','regressors':['trade','income'],'covariance':'HC1'},
                 {'spec_id':'village-year-fe','purpose':'robustness','rationale':'Demonstrate declared FE and clustered inference',
                  'outcome':'turnout','regressors':['trade','income'],'fixed_effects':['village','year'],
                  'covariance':'cluster','cluster':'village'}]}
    e.write_json(root/'request.json',request)
    first=e.run(root/'request.json',root/'runs')
    request['run_id']='round-02'; request['parent_run_id']='round-01'
    request['models']=[{'spec_id':'hc3-check','purpose':'robustness','rationale':'Predetermined alternative covariance example',
                        'outcome':'turnout','regressors':['trade','income'],'covariance':'HC3'}]
    e.write_json(root/'request-round-02.json',request)
    second=e.run(root/'request-round-02.json',root/'runs')
    receipt=e.backup(root/'runs/round-01',root/'backups')
    e.write_json(root/'demo-status.json',{'seed':20260904,'synthetic':True,'runs':[first['status'],second['status']], 'backup':receipt})
    print(first['status'],second['status'])


if __name__=='__main__': main()
