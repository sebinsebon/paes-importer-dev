"""Paired synthetic PDF operations only; no AI, Gold adjudication or real imports."""
import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from dev_paths import DEV_ROOT, output_path, runtime_root


def worker(runtime, workspace):
    sys.path[:0]=[str(runtime/'scripts'),str(runtime/'shared/scripts'),str(DEV_ROOT/'examples')]
    import synthetic
    from lab import configure_workspace, write
    from pdf_assets import prepare_catalog, source_record
    from importer import source_text
    from visual_review import create_review
    configure_workspace(workspace)
    workspace.mkdir(parents=True,exist_ok=False)
    source=workspace/'synthetic.pdf'
    image='q 24 0 0 24 20 350 cm BI /W 1 /H 1 /BPC 8 /CS /RGB /F /AHx ID ff0000> EI Q '
    synthetic.pdf(source,[image+'BT /F1 12 Tf 20 320 Td (SYNTHETIC page '+str(i)+': x = 2) Tj ET 40 200 100 80 re S' for i in range(1,4)])
    sources=[source_record('exam',source)]
    folder=workspace/'.work/base'; folder.mkdir(parents=True)
    write(folder/'sources.json',sources); write(folder/'sources.local.json',{'exam':str(source)})
    import inspect
    lazy='materialize_images' in inspect.signature(prepare_catalog).parameters
    started=time.perf_counter()
    catalog=prepare_catalog(sources,{'exam':str(source)},folder,scale=.5,**({'materialize_images':False} if lazy else {}))
    preparation=time.perf_counter()-started
    expected={'id':'q1','source_id':'exam','number':'1','page':1,
              'regions':[{'page':1,'bbox':[0,0,400,400]}],'content_inventory':[]}
    from pipeline import empty_question
    question=empty_question(expected); question['regions']=expected['regions']
    data={'format':'paessed-benchmark','schema_version':'0.2.0','pipeline':'demo',
          'run':{'id':'synthetic-operations','cli':'synthetic','model':'none','created_at':'2026-01-01T00:00:00Z'},
          'exam':{'id':'synthetic','title':'Synthetic operations','scope':'demo',
                  'expected_questions':[{k:expected[k] for k in ('id','source_id','number')}]},
          'questions':[question],'sources':sources,'assets':[],'evidence':[]}
    write(folder/'candidate.json',data); write(folder/'selection.json',{'expected_questions':[expected]})
    write(folder/'run.json',{'id':'synthetic-operations','config':{'visual_review_protocol':'source-result-1'}})
    durations=[]; included=[]
    for _ in range(2):
        started=time.perf_counter(); result=create_review(folder)
        durations.append(time.perf_counter()-started); included.append(result.get('pages_rendered'))
    started=time.perf_counter(); query_bytes=0
    for _ in range(10):
        query_bytes+=len(json.dumps(source_text(folder,'exam',[1]),ensure_ascii=False).encode())
    query=time.perf_counter()-started
    return {'source_sha256':sources[0]['sha256'],'runtime_release_sha256':hashlib.sha256((runtime/'release.json').read_bytes()).hexdigest(),
            'prepare_seconds':preparation,'review_seconds':durations,'pages_rasterized':included,
            'ten_source_queries_seconds':query,'source_query_bytes':query_bytes,
            'asset_files':len(list((folder/'assets').rglob('*.png'))),
            'asset_bytes':sum(p.stat().st_size for p in (folder/'assets').rglob('*.png')),
            'lazy_candidates':len(catalog.get('asset_candidates',[])),
            'review_status':'pending','gold_adjudication':'not_performed'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',required=True,type=Path)
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--repetitions',type=int,default=3)
    parser.add_argument('--worker',action='store_true')
    args=parser.parse_args(); runtime=runtime_root(args.runtime)
    if args.worker:
        print(json.dumps(worker(runtime,args.output))); return
    if not args.baseline or args.repetitions<3: raise ValueError('Supply baseline and at least three paired repetitions')
    baseline=runtime_root(args.baseline)
    output=output_path(args.output,runtime=runtime,within_dev=True)
    output.mkdir(parents=True,exist_ok=False)
    pairs=[]
    for i in range(args.repetitions):
        row={'pair':i+1}
        # Alternate order to make warm host state visible in the record.
        for label,root in ([('baseline',baseline),('candidate',runtime)] if i%2==0 else [('candidate',runtime),('baseline',baseline)]):
            destination=output/(str(i+1)+'-'+label)
            try:
                result=subprocess.run([sys.executable,'-B',__file__,'--worker','--runtime',str(root),'--output',str(destination)],
                                      capture_output=True,text=True,encoding='utf-8',timeout=120,
                                      env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'})
                payload=json.loads(result.stdout) if result.returncode==0 else None
                if result.returncode==0 and not isinstance(payload,dict): raise ValueError('Worker result must be an object')
                row[label]={**payload,'status':'completed'} if payload is not None else {'status':'failed','error':result.stderr}
            except subprocess.TimeoutExpired as error:
                row[label]={'status':'interrupted','error':'worker_timeout','timeout_seconds':error.timeout}
            except (ValueError,OSError) as error:
                row[label]={'status':'failed','error':type(error).__name__+': '+str(error)}
        pairs.append(row)
        (output/'progress.json').write_text(json.dumps({'pairs':pairs},indent=2)+'\n',encoding='utf-8')
    summary={}
    for label in ('baseline','candidate'):
        completed=[r[label] for r in pairs if r[label]['status']=='completed']
        summary[label]={key:statistics.median(r[key] for r in completed) if completed else None
                        for key in ('prepare_seconds','ten_source_queries_seconds','asset_bytes','source_query_bytes')}
        summary[label]['second_review_median_seconds']=statistics.median(r['review_seconds'][1] for r in completed) if completed else None
    report={'format':'synthetic-operation-benchmark','pairs':pairs,'medians':summary,
            'scope':'Deterministic PDF preparation, unchanged review reuse and native queries; no model calls or real imports.',
            'time_to_acceptable_delivery':None,'real_import_improvement':'inconclusive',
            'conditions':{'python':sys.version,'repetitions':args.repetitions,'cache_policy':'fresh per run; second review reuses within-run state','operation_order':'alternating'}}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'report':str(output/'report.json'),'medians':summary,'real_import_improvement':'inconclusive'},indent=2))
    if any(r[label]['status']!='completed' for r in pairs for label in ('baseline','candidate')): raise SystemExit(1)


if __name__=='__main__': main()
