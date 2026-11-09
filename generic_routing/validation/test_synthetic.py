import asyncio
from contextlib import asynccontextmanager, contextmanager
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import threading
import time
import types
import unittest
from unittest.mock import patch

if importlib.util.find_spec('semantic_router') is None:
    raise unittest.SkipTest('Tests du framework natif : semantic-router non installé. Exécuter test_workflows.py pour les autres contrôles.')

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

@contextmanager
def timed_step(steps, name, kind, **kwargs):
    step = {'name': name, 'kind': kind, 'started_at_ns': time.time_ns()}
    steps.append(step)
    start = time.perf_counter()
    try:
        yield step
    except BaseException as exc:
        step['error'] = type(exc).__name__
        raise
    finally:
        step['duration_s'] = time.perf_counter() - start

tracking = types.ModuleType('app.tracking')
tracking.timed_step = timed_step
sys.modules['app.tracking'] = tracking
from app.context_cache import get_context, invalidate_context
from app.response_policy import check_proofs, profile_catalog, render_profile, select_supported
from app.response_policy import PROFILE_PROMPT, extract_blocks, context_fingerprint
from app.routing import route_question, routing_metrics, warm_router, evaluate_routing

os.environ['EMBEDDING_MODEL'] = 'synthetic-embedding'
ROUTES = json.loads((ROOT / 'app/routes.json').read_text())
EXAMPLES = json.loads((ROOT / 'app/routing_examples.json').read_text())
_norm = lambda text: re.sub(r'[\W_]+', ' ', text.casefold()).strip()
LABELS = {_norm(text): name for name, row in ROUTES['routes'].items() for text in row['utterances']}
LABELS.update({_norm(row['text']): row['route'] for group in ('calibration', 'evaluation') for row in EXAMPLES[group]})
embed_globals = dict(math=math, os=os, time=time, endpoint=lambda name: 'synthetic')
exec(compile((ROOT / 'patches/clients_embed.py').read_text(), 'clients_embed.py', 'exec'), embed_globals)

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()

def utcnow():
    return '2026-01-01T00:00:00+00:00'

class Access:
    def __init__(self, settings, store, api): self.api = api
    def user_context(self, user_id):
        self.api.context_calls += 1
        return {'user_id': user_id, 'tables': {'profile': {'legal_name_first_name': 'Personne', 'position_title': 'Poste synthétique'}, 'jobs': []}}
    def visible_messages(self, *args, **kwargs): return []
    def current_docs(self, user_id): return [{'doc_id': 'D1'}]

verification_globals = dict(json=json, re=re, hashlib=hashlib, os=os, time=time,
    Access=Access, check_proofs=check_proofs, extract_blocks=extract_blocks, context_fingerprint=context_fingerprint,
    profile_catalog=profile_catalog, timed_step=timed_step, utcnow=utcnow,
    safe_error=lambda exc: type(exc).__name__)
exec(compile((ROOT/'patches/verification_functions.py').read_text(), 'verification_functions.py', 'exec'), verification_globals)
parse_review = verification_globals['parse_review']
verify_answer = verification_globals['verify_answer']

class API:
    def __init__(self, mode='documents'):
        self.mode = mode
        self.context_calls = 0
        self.model_calls = 0
        self.embedding_calls = 0
        self.verifier_context = None
    embed = embed_globals['embed']
    def call(self, method, url, auth=None, json=None):
        self.embedding_calls += 1
        if getattr(self, 'embedding_error', False):
            raise RuntimeError('SyntheticEmbeddingError')
        vectors = {'profile':[1.,0.,0.,0.], 'documents':[0.,1.,0.,0.],
                   'mixed':[0.,0.,1.,0.], None:[0.,0.,0.,1.]}
        rows = [{'index':i, 'embedding':vectors[LABELS.get(_norm(text))]}
                for i, text in enumerate(json['input'])]
        data = {'data':list(reversed(rows))}
        if not getattr(self, 'no_usage', False):
            data['usage'] = {'prompt_tokens':7 * len(rows), 'total_tokens':7 * len(rows)}
        return data
    def llm(self, messages, return_metadata=True):
        self.model_calls += 1
        system = messages[0]['content']
        payload = json.loads(messages[1]['content'])
        if system == PROFILE_PROMPT:
            text = json.dumps({'field_ids': ['P1', 'P2']})
        elif system.startswith('Vérifier des affirmations'):
            self.verifier_context = payload['user_context']
            claims = []
            for c in payload['claims']:
                if self.mode == 'mixed' and c['id'] == 'C1':
                    proof = [{'context_path':'/tables/profile/position_title','value':'Poste synthétique'}]
                else:
                    proof = [{'citation':1,'quote':'source synthétique' if c['id'] != 'C13' else 'passage absent'}]
                claims.append({'id':c['id'],'verdict':'supported','evidence':proof,'reason':'Justification synthétique.'})
            text = json.dumps({'claims':claims})
        elif system.startswith('Classer une demande par capacité'):
            text = json.dumps({'route': 'profile' if self.mode == 'profile' else self.mode, 'query': 'Requête autonome'})
        elif self.mode == 'mixed':
            text = '- Poste actuel : Poste synthétique.\n- La règle documentaire est disponible. [1]'
        else:
            text = '\n'.join(f'- Information {i}. [99]' for i in range(1,14))
        return {'text':text,'usage':{'total_tokens':1}}

class Store:
    def __init__(self): self.runs={}; self.messages=[]; self.exports=0
    def user(self, uid): pass
    def save_user_message(self, *args): return 'M0'
    def start_answer_run(self, uid, kind, mode, prompt, question, selection, cid):
        self.runs['R1']={'question':question,'status':'running','result':{}}
        return 'R1'
    def answer_run(self, uid, rid): return self.runs[rid]
    def finish_answer_run(self, uid, rid, result, status, duration, message_id):
        self.runs[rid].update(status=status,result=deepcopy(result))
    def save_assistant_message(self, *args): self.messages.append(args); return 'M1'
    def save_verification(self, uid, rid, result): self.runs[rid]['result']['verification']=result

def complete(api, messages, steps, name, **kwargs):
    with timed_step(steps,name,'llm'):
        return api.llm(messages)['text']

@asynccontextmanager
async def mcp_session(*args):
    yield object()

async def call_tool(session,name,arguments,steps):
    steps.append({'kind':'mcp','name':name,'server':'synthetic'})
    return {'documents':[{'doc_id':'D1','title':'Source synthétique','text':'La source synthétique est disponible.', 'source_version':'V1'}]}

def citation_checks(answer,evidence):
    used=sorted(set(map(int,re.findall(r'\[(\d+)\]',answer))))
    known={d['citation'] for d in evidence}
    return {'references_used':used,'references_valid':all(n in known for n in used)}

def export_run(store,uid,rid): store.exports+=1; return ''

agent_globals=dict(asyncio=asyncio,json=json,os=os,re=re,time=time,hashlib=hashlib,
    digest=digest,utcnow=utcnow,Access=Access,timed_step=timed_step,get_context=get_context,
    route_question=route_question,routing_metrics=routing_metrics,complete=complete,profile_catalog=profile_catalog,
    render_profile=render_profile,select_supported=select_supported,PROFILE_PROMPT=PROFILE_PROMPT,
    context_fingerprint=context_fingerprint,
    mcp_session=mcp_session,call_tool=call_tool,check_current=lambda *x:None,
    safe_answer=lambda text:text,citation_checks=citation_checks,verify_answer=verify_answer,
    cited_sources=lambda answer,evidence:[d for d in evidence if d['citation'] in citation_checks(answer,evidence)['references_used']],
    identify_theme=lambda query:'synthetic',safe_error=lambda exc:type(exc).__name__,export_run=export_run,
    PROMPTS={'renforce':'Consignes de génération.','actuel':'Consignes de génération.'})
exec(compile((ROOT/'patches/agent_functions.py').read_text(), 'agent_functions.py','exec'), agent_globals)
ask_impl=agent_globals['ask']
from app.skills import set_document_search
async def ask(settings, store, api, user_id, cid, question, **kwargs):
    set_document_search(api, user_id, cid, True)
    return await ask_impl(settings, store, api, user_id, cid, question, **kwargs)

_route_question = route_question
async def route_question(api, question, history, steps, complete, **kwargs):
    return await _route_question(api, question, history, steps, complete,
                                document_search_enabled=kwargs.get('document_search_enabled', True))

class Tests(unittest.TestCase):
    def test_cache_separates_users_and_copies(self):
        api=API(); count=[]
        def load(uid): count.append(uid); return {'user_id':uid,'tables':{'profile':{'value':uid}}}
        a,hit=get_context(api,'A',lambda:load('A'))
        self.assertFalse(hit)
        a['tables']['profile']['value']='modified'
        b,hit=get_context(api,'A',lambda:load('A'))
        self.assertTrue(hit); self.assertEqual(b['tables']['profile']['value'],'A')
        get_context(api,'B',lambda:load('B')); self.assertEqual(count,['A','B'])
        invalidate_context(api,'A'); get_context(api,'A',lambda:load('A'))
        self.assertEqual(count,['A','B','A'])

    def test_cache_expiration_and_incomplete_context(self):
        api=API(); count=[]
        def loader(): count.append(1); return {'user_id':'A','tables':{}}
        with patch('app.context_cache.monotonic',return_value=10): get_context(api,'A',loader,ttl_s=2)
        with patch('app.context_cache.monotonic',return_value=13): get_context(api,'A',loader,ttl_s=2)
        self.assertEqual(len(count),2)
        with self.assertRaises(ValueError): get_context(api,'B',lambda:{'user_id':'B'})
        with self.assertRaises(ValueError): get_context(api,'B',lambda:{'user_id':'C','tables':{}})

    def test_cache_same_key_single_flight(self):
        from concurrent.futures import ThreadPoolExecutor
        api=API(); count=[]; started=threading.Event(); release=threading.Event()
        def loader():
            count.append(1); started.set(); self.assertTrue(release.wait(2)); return {'user_id':'A','tables':{}}
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(get_context,api,'A',loader)
            self.assertTrue(started.wait(2))
            second=pool.submit(get_context,api,'A',loader)
            release.set(); first.result(); second.result()
        self.assertEqual(len(count),1)

    def test_profile_binds_values_and_escapes_api_text(self):
        facts=profile_catalog({'tables':{'profile':{'position_title':'<script> **Texte**'}}})
        answer,review=render_profile('{"field_ids":["P1"]}',facts)
        self.assertIn('\\<script\\>',answer)
        self.assertEqual(review['method'],'api_field_binding')
        self.assertNotIn('value',review['claims'][0]['evidence'][0])
        with self.assertRaises(ValueError): render_profile('{"field_ids":["P999"]}',facts)

    def test_doc_quotes_multiple_and_noncontiguous(self):
        docs=[{'citation':1,'text':'Premier passage. Intermédiaire. Dernier passage.'}]
        proofs=[{'citation':1,'quote':'Premier passage.'},{'citation':1,'quote':'Dernier passage.'}]
        valid,errors=check_proofs(proofs,docs,{})
        self.assertEqual(len(valid),2); self.assertFalse(errors)
        _,errors=check_proofs([{'citation':1,'quote':'Premier passage. Dernier passage.'}],docs,{})
        self.assertEqual(errors,['quote_not_found'])

    def test_api_proof_requires_exact_value_and_type(self):
        context={'tables':{'profile':{'flag':False}}}
        good={'context_path':'/tables/profile/flag','value':False}
        self.assertFalse(check_proofs([good],[],context)[1])
        good['value']=0
        self.assertEqual(check_proofs([good],[],context)[1],['profile_value_mismatch'])

    def test_missing_duplicate_and_unknown_claims(self):
        claims=[{'id':'C1','text':'A'},{'id':'C2','text':'B'}]
        raw={'claims':[{'id':'C1','verdict':'insufficient','evidence':[]}]}
        result=parse_review(json.dumps(raw),claims,[])
        self.assertEqual(result['counts']['indeterminate'],1)
        raw['claims'].append(raw['claims'][0])
        with self.assertRaises(ValueError): parse_review(json.dumps(raw),claims,[])

    def test_profile_flow_reuses_warm_cache_one_llm_no_mcp(self):
        api=API('profile'); store=Store(); access=Access(None,store,api)
        get_context(api,'A',lambda:access.user_context('A'))
        progress=[]
        result=asyncio.run(ask(types.SimpleNamespace(method='hybrid'),store,api,'A','C','QUI SUIS JE',on_progress=progress.append))
        self.assertEqual(api.context_calls,1)
        self.assertEqual(result['metrics']['llm_calls'],1)
        self.assertEqual(result['metrics']['mcp_calls'],0)
        self.assertEqual(store.exports,1)
        self.assertEqual(result['verification']['method'],'api_field_binding')
        self.assertEqual(progress[-1],'Export de la trace')

    def test_document_partial_twelve_of_thirteen_and_final_sources(self):
        api=API(); store=Store()
        result=asyncio.run(ask(types.SimpleNamespace(method='hybrid'),store,api,'A','C','Quelle est la politique de télétravail ?'))
        self.assertEqual(result['answer_status'],'partial')
        self.assertEqual(result['verification']['counts']['supported'],12)
        self.assertEqual(result['verification']['counts']['indeterminate'],1)
        self.assertNotIn('Information 13.',result['answer'])
        self.assertNotIn('[99]',result['answer'])
        self.assertEqual(result['checks']['references_used'],[1])
        self.assertFalse(result['draft_checks']['references_valid'])
        self.assertEqual(store.runs['R1']['status'],'completed')
        self.assertEqual(api.verifier_context,{})
        self.assertEqual(store.exports,1)

    def test_mixed_flow_sends_api_to_verifier(self):
        api=API('mixed'); store=Store()
        result=asyncio.run(ask(types.SimpleNamespace(method='hybrid'),store,api,'A','C',ROUTES['routes']['mixed']['utterances'][0]))
        self.assertEqual(result['routing']['route'],'mixed')
        self.assertTrue(api.verifier_context['tables']['profile'])
        self.assertEqual(result['verification']['counts']['supported'],2)
        self.assertEqual(result['answer_status'],'full')
        self.assertEqual(result['verification']['claims'][0]['evidence'][0]['source'],'user_context')

    def test_guest_profile_does_not_load_api(self):
        api=API('profile'); store=Store()
        result=asyncio.run(ask(types.SimpleNamespace(method='hybrid'),store,api,'A','C','QUI SUIS JE',profile_enabled=False))
        self.assertEqual(api.context_calls,0)
        self.assertEqual(api.model_calls,0)
        self.assertEqual(result['answer_status'],'unavailable')

    def test_unmatched_autonomous_query_uses_enabled_document_skill(self):
        api=API('mixed'); steps=[]
        result=asyncio.run(route_question(api,'Ce cas personnel nécessite quelle règle ?',[],steps,complete))
        self.assertEqual(result['route'],'documents')
        self.assertEqual(result['query'],'Ce cas personnel nécessite quelle règle ?')
        self.assertEqual(api.model_calls,0)

    def test_semantic_routes_and_caches_examples(self):
        api=API()
        first=asyncio.run(route_question(api,'Affiche la fonction que j’occupe aujourd’hui',[],[],complete))
        initial_calls=api.embedding_calls
        second=asyncio.run(route_question(api,'Parle-moi de ma carrière connue dans le dossier',[],[],complete))
        self.assertEqual(first['route'],'profile')
        self.assertEqual(second['method'],'semantic')
        self.assertTrue(second['router_reused'])
        self.assertTrue(second['calibrated'])
        self.assertEqual(api.embedding_calls,initial_calls+1)
        self.assertEqual(api.model_calls,0)

    def test_framework_threshold_abstention_falls_back(self):
        api=API('mixed')
        config=deepcopy(ROUTES)
        for row in config['routes'].values(): row['confidence_threshold']=1.0
        with patch('app.routing._configuration',return_value=(config,EXAMPLES)):
            result=asyncio.run(route_question(api,'Qui suis-je ?',[],[],complete))
        self.assertEqual(result['method'],'policy')
        self.assertEqual(result['fallback_reason'],'below_threshold')
        self.assertEqual(result['semantic_candidates'][0]['name'],'profile')

    def test_semantic_core_is_the_upstream_framework(self):
        import semantic_router
        import app.routing as routing
        api=API()
        asyncio.run(warm_router(api))
        entry=next(entry for key, entry in routing._entries.items() if key[0] is api)
        self.assertIs(type(entry.router),semantic_router.IndexedRouter)
        self.assertEqual(type(entry.router.index).__name__,'LocalIndex')

    def test_native_router_two_reads_make_one_dynamic_query_embedding(self):
        api=API();asyncio.run(warm_router(api));before=api.embedding_calls
        steps=[]
        result=asyncio.run(route_question(api,'Comment suis-je présenté dans les données du profil ?',[],steps,complete))
        self.assertEqual(api.embedding_calls,before+1)
        self.assertEqual(routing_metrics(steps,result)['routing_embedding_batches'],1)
        self.assertEqual(routing_metrics(steps,result)['routing_embedding_prompt_tokens_observed'],7)

    def test_literal_utterance_reuses_approved_static_vector(self):
        api=API();asyncio.run(warm_router(api));before=api.embedding_calls
        result=asyncio.run(route_question(api,'Qui suis-je ?',[],[],complete))
        self.assertEqual(api.embedding_calls,before)
        self.assertEqual(result['route'],'profile')

    def test_embedding_contract_is_unique(self):
        api=API()
        self.assertIsInstance(api.embed(['Un texte synthétique']),dict)
        events=[]
        result=api.embed(['Un texte synthétique']*17,on_batch=events.append)
        self.assertEqual(len(result['vectors']),17)
        self.assertEqual([e['batch_size'] for e in events],[16,1])
        self.assertEqual(result['usage']['prompt_tokens'],119)

    def test_missing_usage_is_not_invented(self):
        api=API();api.no_usage=True
        steps=[]
        result=asyncio.run(route_question(api,'Comment suis-je présenté dans les données du profil ?',[],steps,complete))
        metrics=routing_metrics(steps,result)
        self.assertGreater(metrics['routing_embedding_batches_without_prompt_usage'],0)
        self.assertFalse(any('prompt_tokens' in x.get('usage',{}) for x in steps))

    def test_embedding_failure_is_visible_and_recovers_through_llm(self):
        api=API('documents');api.embedding_error=True;steps=[]
        result=asyncio.run(route_question(api,'Une question générale',[],steps,complete))
        self.assertEqual(result['fallback_reason'],'semantic_error')
        self.assertEqual(result['method'],'policy')
        self.assertTrue(any(x.get('kind')=='embedding' and x.get('error')=='RuntimeError' for x in steps))

    def test_history_resolution_does_not_trigger_second_rewrite(self):
        api=API('mixed');steps=[]
        result=asyncio.run(route_question(api,'Et pour moi ?',[
            {'role':'user','content':'Question synthétique précédente'}],steps,complete))
        self.assertEqual(result['fallback_reason'],'history_required')
        self.assertEqual(result['query'],'Requête autonome')
        self.assertEqual(api.model_calls,1)
        self.assertEqual(api.embedding_calls,0)

    def test_malformed_llm_route_is_clarified(self):
        api=API();steps=[]
        def malformed(api,messages,steps,name,**kwargs):return '{"route": [], "query":"question"}'
        result=asyncio.run(route_question(api,'Et pour moi ?',[
            {'role':'user','content':'Contexte synthétique'}],steps,malformed))
        self.assertEqual(result['route'],'clarify')
        self.assertEqual(result['classification_error'],'invalid_llm_response')

    def test_missing_rewritten_query_is_clarified(self):
        api=API();steps=[]
        def incomplete(api,messages,steps,name,**kwargs):return '{"route":"mixed"}'
        result=asyncio.run(route_question(api,'Et pour moi ?',[
            {'role':'user','content':'Contexte synthétique'}],steps,incomplete))
        self.assertEqual(result['route'],'clarify')

    def test_routing_telemetry_has_nested_ids_without_profile_payload(self):
        api=API();steps=[]
        result=asyncio.run(route_question(api,'Comment suis-je présenté dans les données du profil ?',[],steps,complete))
        root=steps[0]
        self.assertEqual(root['name'],'Routage')
        ids={x.get('step_id') for x in steps}
        self.assertTrue(all(x.get('parent_step_id') in ids for x in steps[1:]))
        self.assertTrue(all(x['inputs']['purpose'] in {'query','setup_examples','setup_calibration'}
            for x in steps if x.get('kind')=='embedding'))
        self.assertNotIn('user_context',json.dumps(result))

    def test_concurrent_requests_keep_their_telemetry_separate(self):
        api=API();left=[];right=[]
        async def both():
            return await asyncio.gather(
                route_question(api,'Comment suis-je présenté dans les données du profil ?',[],left,complete),
                route_question(api,ROUTES['routes']['mixed']['utterances'][0],[],right,complete))
        results=asyncio.run(both())
        self.assertEqual([x['route'] for x in results],['profile','mixed'])
        for steps in (left,right):
            ids={x['step_id'] for x in steps}
            self.assertTrue(all(x.get('parent_step_id') in ids for x in steps[1:]))
        self.assertFalse({x['step_id'] for x in left} & {x['step_id'] for x in right})

    def test_calibration_and_evaluation_are_separate_and_framework_evaluates(self):
        api=API();report=asyncio.run(evaluate_routing(api))
        self.assertEqual(report['n'],len(EXAMPLES['evaluation']))
        self.assertEqual(report['mixed_to_profile_errors'],0)
        self.assertEqual(report['accuracy'],1.0)

    def test_mlflow_patch_preserves_parent_ids_and_outcomes(self):
        from datetime import datetime
        created=[]
        class Span:
            trace_id='synthetic-trace'
            def __init__(self,name,kwargs):self.name,self.kwargs,self.ended=name,kwargs,None;self.attributes={}
            def end(self,**kwargs):self.ended=kwargs
            def set_attribute(self,key,value):self.attributes[key]=value
        class MLflow:
            def start_span_no_context(self,name,**kwargs):
                span=Span(name,kwargs);created.append(span);return span
            def get_trace(self,trace_id):return True
        namespace={'datetime':datetime}
        exec(compile((ROOT/'patches/tracking_trace.py').read_text(),'tracking_trace.py','exec'),namespace)
        run={'started_at':'2026-01-01T00:00:00+00:00','duration':1,'question':'Question synthétique',
             'mode':'full','selected':{},'run_id':'R1','prompt_variant':'renforce','status':'completed'}
        steps=[{'name':'Routage','kind':'routing','step_id':'P','duration_s':0.2},
               {'name':'Embedding','kind':'embedding','step_id':'C','parent_step_id':'P',
                'duration_s':0.1,'usage':{'prompt_tokens':7,'total_tokens':7},
                'details':{'embedding_model':'synthetic-embedding'}}]
        trace=namespace['_trace'](MLflow(),run,{'steps':steps,'routing':{'route':'profile'}},'1')
        self.assertEqual(trace,'synthetic-trace')
        self.assertIs(created[2].kwargs['parent_span'],created[1])
        self.assertEqual(created[2].kwargs['span_type'],'EMBEDDING')
        self.assertEqual(created[0].ended['outputs']['routing']['route'],'profile')
        self.assertEqual(created[2].attributes['mlflow.chat.tokenUsage'],{
            'input_tokens':7,'output_tokens':0,'total_tokens':7})
        self.assertEqual(created[2].attributes['mlflow.llm.model'],'synthetic-embedding')

    def test_rule_with_unverified_condition_is_removed_as_a_block(self):
        review={'status':'completed','claims':[
            {'id':'C1','statement':'- Règle sous réserve d’une condition. [1]',
             'verdict':'insufficient','evidence':[]},
            {'id':'C2','statement':'- Une autre information sûre. [1]',
             'verdict':'supported','evidence':[{'citation':1,'quote':'Autre information'}]}]}
        result=select_supported(review)
        self.assertNotIn('Règle',result['answer'])
        self.assertEqual(result['answer_status'],'partial')

    def test_no_supported_or_verifier_error_blocks(self):
        review={'status':'completed','claims':[{'id':'C1','verdict':'insufficient'}]}
        self.assertEqual(select_supported(review)['answer_status'],'blocked')
        review={'status':'error','claims':[{'id':'C1','verdict':'supported'}]}
        self.assertTrue(select_supported(review)['needs_review'])

    def test_manual_review_uses_draft_and_cached_version(self):
        api=API();store=Store()
        result=asyncio.run(ask(types.SimpleNamespace(method='hybrid'),store,api,'A','C','Quelle est la politique de télétravail ?'))
        previous_calls=api.model_calls
        review=verify_answer(None,store,api,'A','R1')
        self.assertEqual(api.model_calls,previous_calls)
        self.assertEqual(review['counts']['supported'],12)
        self.assertEqual(len(review['requested_claims']),13)

if __name__ == '__main__': unittest.main(verbosity=2)
