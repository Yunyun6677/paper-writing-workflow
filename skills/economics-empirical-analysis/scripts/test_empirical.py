"""Behavioral tests with synthetic data only; no Stata or network required."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat
from openpyxl import Workbook

import empirical as e


class EmpiricalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        rng = np.random.default_rng(20260904)
        self.frame = pd.DataFrame({'id':np.arange(120), 'x':rng.normal(size=120),
                                   'group':np.repeat(np.arange(20),6)})
        self.frame['y'] = 1.0 + 2.0*self.frame.x + rng.normal(size=120)
        self.frame.to_csv(self.root/'input.csv',index=False)
        self.request = {'schema_version':'empirical-request/1.0','project_id':'test','run_id':'test',
                        'question':'Synthetic association test','sensitivity':'synthetic',
                        'inputs':[{'path':'input.csv','primary_key':['id']}],
                        'models':[{'spec_id':'base','purpose':'primary','rationale':'Declared before fit',
                                   'outcome':'y','regressors':['x'],'covariance':'HC1'}]}

    def tearDown(self): self.temp.cleanup()

    def execute(self, request=None):
        e.write_json(self.root/'request.json',request or self.request)
        return e.run(self.root/'request.json',self.root/'runs')

    def test_ols_matches_independent_lstsq_and_hc1(self):
        result = self.execute(); self.assertEqual(result['status'],'complete')
        table = pd.read_csv(self.root/'runs/test/models/base/coefficients.csv')
        X = np.column_stack([np.ones(120),self.frame.x]); y=self.frame.y.to_numpy()
        beta = np.linalg.lstsq(X,y,rcond=None)[0]; resid=y-X@beta
        inv=np.linalg.inv(X.T@X); cov=inv@(X.T@(resid[:,None]**2*X))@inv*120/118
        np.testing.assert_allclose(table.estimate,beta,rtol=1e-10)
        np.testing.assert_allclose(table.std_error,np.sqrt(np.diag(cov)),rtol=1e-10)

    def test_latex_deliverables_are_generated_and_hashed(self):
        bundle = self.execute()
        run = self.root/'runs/test'
        expected = ['results/report.tex', 'models/base/coefficients.tex', 'models/base/coefficients.pdf']
        artifact_paths = {item['path'] for item in bundle['artifacts']}
        for relative in expected:
            self.assertTrue((run/relative).is_file())
            self.assertIn(relative, artifact_paths)
        self.assertIn('\\documentclass', (run/'results/report.tex').read_text(encoding='utf-8'))

    def test_idempotent_verified_reuse(self):
        one=self.execute(); two=self.execute(); self.assertEqual(one,two)

    def test_changed_source_rejected(self):
        self.execute(); self.frame.assign(y=2).to_csv(self.root/'input.csv',index=False)
        with self.assertRaises(ValueError): self.execute()

    def test_tamper_rejected(self):
        self.execute(); (self.root/'runs/test/processed/analysis.csv').write_text('tampered')
        with self.assertRaises(ValueError): e.verify(self.root/'runs/test')

    def test_interruption_preserved(self):
        (self.root/'runs/test').mkdir(parents=True)
        with self.assertRaises(ValueError): self.execute()

    def test_duplicate_primary_key_fails(self):
        self.frame.assign(id=1).to_csv(self.root/'input.csv',index=False)
        self.assertEqual(self.execute()['status'],'failed')

    def test_missing_exclusion_and_recode(self):
        self.frame.loc[0,'x']=-999; self.frame.to_csv(self.root/'input.csv',index=False)
        self.request['missing_codes']={'x':[-999]}; self.execute()
        data=e.read_json(self.root/'runs/test/models/base/result.json')
        self.assertEqual(data['n_used'],119); self.assertEqual(data['n_missing_excluded'],1)

    def test_rank_deficiency_keeps_failed_spec(self):
        self.request['models'][0]['regressors']=['x','id']
        self.frame['x']=self.frame.id*2; self.frame.to_csv(self.root/'input.csv',index=False)
        bundle=self.execute(); self.assertEqual(bundle['status'],'partial')
        self.assertEqual(bundle['models'][0]['status'],'failed')

    def test_cluster_and_fe(self):
        self.request['models'][0].update(covariance='cluster',cluster='group',fixed_effects=['group'])
        self.assertEqual(self.execute()['status'],'complete')
        data=e.read_json(self.root/'runs/test/models/base/result.json')
        self.assertEqual(data['clusters'],20)

    def test_join_cardinality_fails(self):
        pd.DataFrame({'id':[1,1], 'z':[2,3]}).to_csv(self.root/'other.csv',index=False)
        self.request['inputs'].append({'path':'other.csv','merge':{'on':['id'],'validate':'many_to_one'}})
        self.assertEqual(self.execute()['status'],'failed')

    def test_valid_join_records_coverage(self):
        pd.DataFrame({'id':[1,2], 'z':[2,3]}).to_csv(self.root/'other.csv',index=False)
        self.request['inputs'].append({'path':'other.csv','merge':{'on':['id'],'validate':'many_to_one'}})
        self.assertEqual(self.execute()['status'],'complete')
        cleaning=e.read_json(self.root/'runs/test/metadata/cleaning.json')
        self.assertEqual(cleaning[0]['join_counts']['left_only'],118)

    def test_excel_input_and_leading_zero(self):
        # Test fixture only, not a publication workbook.
        book=Workbook(); sheet=book.active; sheet.title='Data'; sheet.append(['code','x','y','id'])
        for r in self.frame.itertuples(): sheet.append([f'{r.id:04}',r.x,r.y,r.id])
        book.save(self.root/'input.xlsx')
        self.request['inputs']=[{'path':'input.xlsx','sheet':'Data','dtypes':{'code':'str'}}]
        self.assertEqual(self.execute()['status'],'complete')
        data,_=e.load_data(self.root/'input.xlsx',self.request['inputs'][0])
        self.assertEqual(data.code.iloc[1],'0001')

    def test_excel_requires_sheet(self):
        book=Workbook(); book.save(self.root/'input.xlsx')
        with self.assertRaises(ValueError): e.load_data(self.root/'input.xlsx',{})

    def test_dta_preserves_original_and_labels(self):
        pyreadstat.write_dta(self.frame,str(self.root/'input.dta'),column_labels={'y':'Outcome'})
        self.request['inputs']=[{'path':'input.dta'}]; self.assertEqual(self.execute()['status'],'complete')
        self.assertEqual(e.sha(self.root/'input.dta'),e.sha(self.root/'runs/test/raw/0.dta'))
        self.assertEqual(e.read_json(self.root/'runs/test/metadata/input-0.json')['variable_labels']['y'],'Outcome')

    def test_no_code_formula_or_path_traversal(self):
        self.request['models'][0]['formula']='__import__("os")'
        with self.assertRaises(Exception): self.execute()
        with self.assertRaises(ValueError): e.safe_child(self.root,'../escape')

    def test_backup_readback_and_no_overwrite(self):
        self.execute(); receipt=e.backup(self.root/'runs/test',self.root/'backups')
        self.assertEqual(receipt['status'],'local-verified-not-cloud')
        with self.assertRaises(FileExistsError): e.backup(self.root/'runs/test',self.root/'backups')


if __name__=='__main__':
    unittest.main(verbosity=2)
