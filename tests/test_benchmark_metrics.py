import json
import sys
import tempfile
import unittest
from pathlib import Path
from support import RUNTIME_ROOT as ROOT, DEV_ROOT, WORK_ROOT
sys.path.insert(0,str(ROOT/'shared/scripts'))
sys.path.insert(0,str(ROOT/'scripts'))
from metrics import aggregate_usage, measured_savings
from benchmark import evaluate, compare_reports

class MetricsTests(unittest.TestCase):
    def test_complete_and_partial_measurements(self):
        result=aggregate_usage([{'event_id':'a','input_tokens':10,'output_tokens':2},{'event_id':'b','input_tokens':5}])
        self.assertEqual(result['input_tokens'],15)
        self.assertIsNone(result['output_tokens'])
        self.assertEqual(result['known_subtotals']['output_tokens'],2)
        self.assertIsNone(result['cost'])
        self.assertIsNone(aggregate_usage([])['input_tokens'])
    def test_duplicate_overlapping_or_invalid_usage_rejected(self):
        for events in ([{'event_id':'same'},{'event_id':'same'}], [{'event_id':'a','aggregate':True}],
                       [{'event_id':'a','input_tokens':True}], [{'event_id':'a','input_tokens':2.5}],
                       [{'event_id':'a','cost':float('nan')}], [{'event_id':'a','cost':-1}]):
            with self.assertRaises(ValueError):aggregate_usage(events)
    def test_currency_must_match(self):
        with self.assertRaises(ValueError):aggregate_usage([{'event_id':'a','cost':1}])
        with self.assertRaises(ValueError):aggregate_usage([{'event_id':'a','cost':1,'currency':'USD'},{'event_id':'b','cost':1,'currency':'CLP'}])
        self.assertEqual(aggregate_usage([{'event_id':'a','cost':1,'currency':'USD'}])['currency'],'USD')
    def test_cost_savings_require_same_currency(self):
        before=aggregate_usage([{'event_id':'a','cost':100,'currency':'USD'}])
        after=aggregate_usage([{'event_id':'b','cost':80,'currency':'CLP'}])
        self.assertIsNone(measured_savings(before,after)['cost'])
        after=aggregate_usage([{'event_id':'b','cost':80,'currency':'USD'}])
        self.assertEqual(measured_savings(before,after)['cost'],.2)
    def test_report_savings_require_matched_conditions(self):
        row={'id':'a','status':'completed','metadata':{'host':'cli','model':'synthetic','effort':'test','capabilities_sha256':'a'*64,'generation_config_sha256':'b'*64},'input_hashes':{'gold':'reference'}}
        before={'runs':[row],'usage':{'input_tokens':100}}
        after={'runs':[row],'usage':{'input_tokens':80}}
        self.assertTrue(compare_reports(before,after)['conditions_matched'])
        self.assertEqual(compare_reports(before,after)['measured_savings']['input_tokens'],.2)
        after['runs']=[{**row,'metadata':{}}]
        self.assertIsNone(compare_reports(before,after)['measured_savings']['input_tokens'])
    def test_savings_require_capability_and_generation_settings(self):
        metadata={'host':'cli','model':'synthetic','effort':'test','capabilities_sha256':'a'*64,'generation_config_sha256':'b'*64}
        row={'id':'a','status':'completed','metadata':metadata,'input_hashes':{'gold':'reference'}}
        before={'runs':[row],'usage':{'input_tokens':100}}
        for key in ('capabilities_sha256','generation_config_sha256'):
            changed={**metadata,key:'c'*64};after={'runs':[{**row,'metadata':changed}],'usage':{'input_tokens':80}}
            self.assertFalse(compare_reports(before,after)['conditions_matched'])
            self.assertIsNone(compare_reports(before,after)['measured_savings']['input_tokens'])
    def test_savings_do_not_invent_missing_data(self):
        result=measured_savings({'input_tokens':100,'cost':None},{'input_tokens':80,'cost':1})
        self.assertEqual(result['input_tokens'],.2)
        self.assertIsNone(result['cost'])
    def test_interrupted_is_not_completed(self):
        result=evaluate({'runs':[{'id':'a','status':'interrupted','usage':[]}]},ROOT)
        self.assertEqual(result['counts']['completed'],0)
        self.assertIsNone(result['runs'][0]['comparison'])
        self.assertFalse(result['automatic_promotion'])
    def test_completed_evaluates_existing_outputs(self):
        (WORK_ROOT).mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=WORK_ROOT) as temporary:
            home=Path(temporary)
            from test_contract_compatibility import fixture
            data=fixture()
            (home/'reference.json').write_text(json.dumps(data))
            result=evaluate({'runs':[{'id':'a','status':'completed','gold':'reference.json','candidate':'reference.json',
                'usage':[{'event_id':'provider-call-a','input_tokens':5,'output_tokens':2}]}]},home)
            self.assertEqual(result['usage']['input_tokens'],5)
            self.assertEqual(result['runs'][0]['gold_certification'],'not_checked')
            self.assertEqual(result['runs'][0]['comparison']['certification'],'not_performed')
    def test_duplicate_events_across_runs_rejected(self):
        with self.assertRaises(ValueError):evaluate({'runs':[
            {'id':'a','status':'failed','usage':[{'event_id':'shared'}]},
            {'id':'b','status':'interrupted','usage':[{'event_id':'shared'}]}]},ROOT)

if __name__=='__main__':unittest.main()
