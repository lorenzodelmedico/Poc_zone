"""Tests d'orchestration et d'indexation avec services synthétiques.

Le moteur Aurelio n'est pas simulé comme s'il avait été testé : ses tests natifs
restent dans test_synthetic.py et nécessitent le paquet réellement installé.
"""
import ast
import asyncio
from contextlib import contextmanager, asynccontextmanager
from copy import deepcopy
import hashlib
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.skills import (get_skill_state, set_document_search, select_source,
                        queue_source, update_source, document_scope, clear_skills)
from app.source_jobs import enqueue_source_sync, get_source_job, validate_source_url
from app.source_scope import restrict_document_catalog
from app.embedding_observer import observe_embeddings
from app.context_cache import get_context
from app.chat_generation import GENERAL_PROMPT, NO_DOCUMENTS_PREFIX, NO_DOCUMENTARY_ANSWER, generate_general
from app.response_policy import (PROFILE_PROMPT, profile_catalog, render_profile, select_supported,
                                 check_proofs, extract_blocks, context_fingerprint)

DOC = {'doc_id': 'D1', 'title': 'Source synthétique', 'source_version': '1',
       'text': 'Information documentaire confirmée.'}

@contextmanager
def timed_step(steps, name, kind, **kwargs):
    row = {'name': name, 'kind': kind, 'started_at_ns': time.time_ns()}
    steps.append(row)
    started = time.perf_counter()
    try:
        yield row
    except BaseException as exc:
        row['error'] = type(exc).__name__
        raise
    finally:
        row['duration_s'] = time.perf_counter() - started

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

class Access:
    def __init__(self, settings, store, api): self.api = api
    def user_context(self, uid):
        return {'user_id': uid, 'tables': {'profile': {'position_title': 'Poste synthétique'}}}
    def visible_messages(self, *a, **k): return []
    def current_docs(self, uid): return deepcopy(self.api.authorized)

def check_current(access, evidence):
    ids = {d['doc_id'] for d in access.current_docs('synthetic')}
    if any(d['doc_id'] not in ids for d in evidence): raise PermissionError('Accès retiré')

def citation_checks(answer, evidence):
    used = sorted({int(x) for x in re.findall(r'\[(\d+)\]', answer)})
    return {'references_valid': all(x in {d['citation'] for d in evidence} for x in used),
            'references_used': used}

embed_ns = dict(math=math, os=os, time=time, endpoint=lambda name: 'synthetic')
exec(compile((ROOT/'patches/clients_embed.py').read_text(), 'clients_embed.py', 'exec'), embed_ns)
verify_ns = dict(json=json, re=re, hashlib=hashlib, os=os, time=time, Access=Access,
    check_proofs=check_proofs, extract_blocks=extract_blocks, context_fingerprint=context_fingerprint,
    profile_catalog=profile_catalog, timed_step=timed_step, utcnow=lambda:'2026-01-01T00:00:00+00:00',
    safe_error=lambda exc:type(exc).__name__)
exec(compile((ROOT/'patches/verification_functions.py').read_text(), 'verification_functions.py', 'exec'), verify_ns)

# Extraction de la fonction de politique pure, sans importer ni remplacer Aurelio.
tree = ast.parse((ROOT/'app/routing.py').read_text())
node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'choose_workflow')
policy_ns = {}
exec(compile(ast.Module(body=[node], type_ignores=[]), 'routing.py', 'exec'), policy_ns)
choose_workflow = policy_ns['choose_workflow']

class API:
    embed = embed_ns['embed']
    def __init__(self, intent='documents', **kwargs):
        self.intent = intent
        self.authorized = [deepcopy(DOC)]
        self.docs = [deepcopy(DOC)]
        self.calls = []
        self.tool_args = []
        self.behavior = kwargs
    def call(self, *a, **kwargs):
        if self.behavior.get('embedding_error'): raise RuntimeError('EmbeddingFailed')
        rows = [{'index': i, 'embedding': [0.1, 0.2]} for i, _ in enumerate(kwargs['json']['input'])]
        result = {'data': list(reversed(rows))}
        if not self.behavior.get('missing_usage'):
            result['usage'] = {'prompt_tokens': len(rows)*7, 'total_tokens': len(rows)*7}
        return result
    def llm(self, messages, **kwargs):
        prompt = messages[0]['content']
        self.calls.append(prompt)
        payload = json.loads(messages[1]['content'])
        if prompt == GENERAL_PROMPT:
            text = 'Une prévision météo nécessite une source actualisée ; aucun outil de prévisions n’est disponible.'
        elif prompt == PROFILE_PROMPT:
            text = '{"field_ids":["P1"]}'
        elif prompt.startswith('Vérifier des affirmations'):
            if self.behavior.get('judge_error'): raise RuntimeError('JudgeFailed')
            claims = []
            for c in payload['claims']:
                proof = [{'citation':1, 'quote':'Information documentaire confirmée.'}]
                if self.intent == 'mixed' and c['id'] == 'C1':
                    proof = [{'context_path':'/tables/profile/position_title', 'value':'Poste synthétique'}]
                if self.behavior.get('partial') and c['id'] == 'C13':
                    proof = [{'citation':1, 'quote':'Citation absente'}]
                claims.append({'id':c['id'], 'verdict':'supported', 'evidence':proof, 'reason':'Preuve synthétique'})
            text = json.dumps({'claims':claims})
        elif self.behavior.get('abstain'):
            text = NO_DOCUMENTARY_ANSWER
        elif self.intent == 'mixed':
            text = '- Poste synthétique\n- Information documentaire confirmée. [1]'
        elif self.behavior.get('partial'):
            text = '\n'.join(f'- Information {i}. [1]' for i in range(1,14))
        else:
            text = '- Information documentaire confirmée. [1]'
        return {'text':text, 'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}}

class Store:
    def __init__(self): self.runs={}; self.messages=[]; self.exports=0
    def user(self, uid): pass
    def save_user_message(self, *a): return 'M0'
    def start_answer_run(self, uid, kind, mode, prompt, question, selected, cid):
        self.runs['R']={'question':question,'status':'running','result':{}}
        return 'R'
    def answer_run(self, uid, rid): return self.runs[rid]
    def finish_answer_run(self, uid, rid, result, status, duration, message_id):
        self.runs[rid].update(status=status, result=deepcopy(result))
    def save_assistant_message(self, *a): self.messages.append(a); return 'M1'
    def save_verification(self, uid, rid, review): self.runs[rid]['result']['verification']=review

def complete(api, messages, steps, name, **kwargs):
    with timed_step(steps,name,'llm') as step:
        reply=api.llm(messages)
        step['usage']=reply['usage']
        return reply['text']

@asynccontextmanager
async def session(settings, uid): yield settings.api

async def call_tool(api, name, args, steps):
    api.tool_args.append(deepcopy(args))
    if api.behavior.get('retrieval_error'): raise RuntimeError('RetrievalFailed')
    docs = deepcopy(api.docs)
    if not api.behavior.get('ignore_scope'):
        docs = restrict_document_catalog(docs, args.get('document_ids'))
    steps.append({'name':name,'kind':'mcp','server':'synthetic'})
    return {'documents':docs}

async def route(api, question, history, steps, complete, *, document_search_enabled=False):
    return {'route':choose_workflow(api.intent,document_search_enabled), 'query':question,
            'method':'synthetic_test_boundary', 'intent_route':api.intent}

def export_run(store, uid, rid): store.exports+=1; return ''

agent_ns=dict(json=json,os=os,re=re,time=time,hashlib=hashlib,Access=Access,digest=digest,
    utcnow=lambda:'2026-01-01T00:00:00+00:00',get_context=get_context,
    context_fingerprint=context_fingerprint,timed_step=timed_step,route_question=route,
    routing_metrics=lambda *a:{},complete=complete,profile_catalog=profile_catalog,
    render_profile=render_profile,PROFILE_PROMPT=PROFILE_PROMPT,mcp_session=session,
    call_tool=call_tool,check_current=check_current,safe_answer=lambda x:x,
    citation_checks=citation_checks,verify_answer=verify_ns['verify_answer'],select_supported=select_supported,
    cited_sources=lambda answer,docs:[d for d in docs if d['citation'] in citation_checks(answer,docs)['references_used']],
    identify_theme=lambda q:'synthetic',safe_error=lambda exc:type(exc).__name__,export_run=export_run,
    PROMPTS={'actuel':'Consigne synthétique','renforce':'Consigne synthétique'})
exec(compile((ROOT/'patches/agent_functions.py').read_text(),'agent_functions.py','exec'),agent_ns)

def run_chat(api, *, enabled=False):
    store=Store()
    set_document_search(api,'A','C',enabled)
    answer=asyncio.run(agent_ns['ask'](types.SimpleNamespace(method='hybrid',api=api),store,api,'A','C','Question synthétique'))
    return answer,store

class Workflows(unittest.TestCase):
    def test_unique_embedding_contract_batches_and_usage(self):
        events=[]; result=API().embed(['Texte']*17,on_batch=events.append)
        self.assertEqual(len(result['vectors']),17)
        self.assertEqual([x['batch_size'] for x in events],[16,1])
        self.assertEqual(result['usage']['prompt_tokens'],119)
        with self.assertRaises(TypeError): API().embed(['Texte'],return_metadata=True)

    def test_missing_embedding_usage_is_unknown(self):
        result=API(missing_usage=True).embed(['Texte'])
        self.assertEqual(result['usage'],{})
        self.assertEqual(result['usage_batches'],0)

    def test_embedding_error_remains_observable(self):
        events=[]
        with self.assertRaises(RuntimeError), observe_embeddings(events,purpose='test'):
            API(embedding_error=True).embed(['Texte'])
        self.assertEqual(events[0]['error'],'RuntimeError')

    def test_unknown_intent_obeys_document_skill(self):
        self.assertEqual(choose_workflow(None,True),'documents')
        self.assertEqual(choose_workflow(None,False),'general')
        self.assertEqual(choose_workflow('profile',True),'profile')
        self.assertEqual(choose_workflow('mixed',True),'mixed')

    def test_profile_stays_verified_without_document_search(self):
        api=API('profile'); result,store=run_chat(api)
        self.assertEqual(result['answer_scope'],'profile')
        self.assertEqual(result['verification']['method'],'api_field_binding')
        self.assertEqual(len(api.calls),1); self.assertFalse(api.tool_args)

    def test_general_disabled_skill_calls_llm_once(self):
        api=API(None); result,store=run_chat(api)
        self.assertEqual(result['answer_scope'],'general')
        self.assertEqual(result['retrieval_status'],'not_requested')
        self.assertNotIn(NO_DOCUMENTS_PREFIX,result['answer'])
        self.assertEqual(len(api.calls),1); self.assertFalse(api.tool_args)
        self.assertEqual(store.exports,1)

    def test_general_history_does_not_relabel_document_answers_as_general_knowledge(self):
        payloads=[]
        def capture(api,messages,steps,name,**kwargs):
            payloads.append(json.loads(messages[1]['content']))
            return 'Réponse générale'
        generate_general(API(),'Question',[{'role':'user','content':'Question précédente'},
            {'role':'assistant','content':'Information issue du document'}],[],capture,reason='document_skill_disabled')
        self.assertEqual(payloads[0]['previous_exchanges'],[{'role':'user','content':'Question précédente'}])

    def test_empty_search_calls_general_with_prefix(self):
        api=API(None); api.docs=[]; result,store=run_chat(api,enabled=True)
        self.assertTrue(result['answer'].startswith(NO_DOCUMENTS_PREFIX))
        self.assertEqual(result['retrieval_status'],'completed')
        self.assertEqual(result['verification']['status'],'not_applicable')
        self.assertEqual(result['sources'],[])
        self.assertEqual(len(api.calls),1)

    def test_generation_abstention_also_returns_general(self):
        api=API(abstain=True); result,_=run_chat(api,enabled=True)
        self.assertEqual(result['fallback_reason'],'generation_abstention')
        self.assertEqual(len(api.calls),2)
        self.assertTrue(result['answer'].startswith(NO_DOCUMENTS_PREFIX))

    def test_partial_twelve_of_thirteen_are_kept(self):
        api=API(partial=True); result,_=run_chat(api,enabled=True)
        self.assertEqual(result['answer_status'],'partial')
        self.assertEqual(result['verification']['counts']['supported'],12)
        self.assertNotIn('Information 13.',result['answer'])
        self.assertEqual(result['checks']['references_used'],[1])

    def test_judge_failure_does_not_trigger_general(self):
        api=API(judge_error=True); result,_=run_chat(api,enabled=True)
        self.assertEqual(result['answer_status'],'blocked')
        self.assertNotIn(GENERAL_PROMPT,api.calls)
        self.assertNotIn('Information documentaire confirmée.',result['answer'])

    def test_retrieval_error_is_not_empty_search(self):
        api=API(retrieval_error=True)
        with self.assertRaises(RuntimeError): run_chat(api,enabled=True)
        self.assertEqual(api.calls,[])

    def test_not_ready_source_does_not_claim_no_information(self):
        api=API(); queue_source(api,'A','C','https://sharepoint.example.invalid/site','job')
        result,_=run_chat(api,enabled=True)
        self.assertEqual(result['retrieval_status'],'not_ready')
        self.assertFalse(api.calls); self.assertFalse(api.tool_args)

    def test_selected_empty_source_never_searches_everything(self):
        api=API(); sid,_,_=queue_source(api,'A','C','https://sharepoint.example.invalid/site','job')
        update_source(api,'A','C',sid,status='completed',document_ids=[])
        result,_=run_chat(api,enabled=True)
        self.assertEqual(result['answer_scope'],'general'); self.assertFalse(api.tool_args)

    def test_scope_is_passed_and_unexpected_result_is_blocked(self):
        api=API(ignore_scope=True); sid,_,_=queue_source(api,'A','C','https://sharepoint.example.invalid/site','job')
        update_source(api,'A','C',sid,status='completed',document_ids=['OTHER'])
        with self.assertRaises(PermissionError): run_chat(api,enabled=True)
        self.assertEqual(api.tool_args[0]['document_ids'],['OTHER'])
        self.assertFalse(api.calls)

    def test_withdrawn_access_prevents_generation(self):
        api=API(); api.authorized=[]
        with self.assertRaises(PermissionError): run_chat(api,enabled=True)
        self.assertFalse(api.calls)

    def test_mixed_verifier_receives_api_context(self):
        api=API('mixed'); result,_=run_chat(api,enabled=True)
        self.assertEqual(result['verification']['counts']['supported'],2)
        self.assertEqual(result['verification']['scope'],'mixed')

    def test_recorded_general_response_is_not_document_checked(self):
        api=API(None); result,store=run_chat(api)
        before=len(api.calls)
        review=verify_ns['verify_answer'](None,store,api,'A','R')
        self.assertEqual(review['scope'],'general')
        self.assertEqual(len(api.calls),before)

    def test_backend_state_isolated_by_user_conversation_and_client(self):
        a,b=API(),API(); set_document_search(a,'A','C',True)
        self.assertFalse(get_skill_state(a,'B','C')['document_search'])
        self.assertFalse(get_skill_state(a,'A','OTHER')['document_search'])
        self.assertFalse(get_skill_state(b,'A','C')['document_search'])

    def test_source_selection_cannot_cross_conversations(self):
        api=API(); sid,_,_=queue_source(api,'A','C','https://sharepoint.example.invalid/site','job')
        with self.assertRaises(PermissionError): select_source(api,'A','OTHER',sid,True)

    def test_pre_search_filter_uses_intersection_and_empty_stays_empty(self):
        self.assertEqual(restrict_document_catalog([DOC],['OTHER']),[])
        self.assertEqual(restrict_document_catalog([DOC],[]),[])
        self.assertEqual(restrict_document_catalog([DOC],None),[DOC])

    def test_source_url_is_bounded_by_configured_root(self):
        root=['https://sharepoint.example.invalid/sites/example']
        validate_source_url(root[0]+'/folder',root)
        for url in ['https://evil.example.invalid/sites/example','https://sharepoint.example.invalid/sites/example-other',
                    'https://sharepoint.example.invalid/sites/example/%2e%2e/private',
                    'https://sharepoint.example.invalid/sites/example/Forms/AllItems.aspx?id=%2Fsites%2Fprivate']:
            with self.assertRaises(PermissionError): validate_source_url(url,root)

    def test_source_job_reuses_indexer_and_deduplicates_active_job(self):
        api=API(); entered=threading.Event(); release=threading.Event(); exported=threading.Event(); calls=[]
        def index(uid,url,report):
            calls.append((uid,url)); entered.set()
            if not release.wait(2): raise TimeoutError('Test timeout')
            api.embed(['Texte synthétique'])
            report('Traitement synthétique',1,1)
            return {'document_ids':['D1']}
        traces=[]
        def export(job): traces.append(job); exported.set(); return 'TRACE'
        kwargs={'index_existing':index,'allowed_roots':['https://sharepoint.example.invalid/sites/example'],'export_job':export}
        jid=enqueue_source_sync(api,'A','C',kwargs['allowed_roots'][0],**kwargs)
        try:
            self.assertTrue(entered.wait(2))
            self.assertEqual(enqueue_source_sync(api,'A','C',kwargs['allowed_roots'][0],**kwargs),jid)
            with self.assertRaises(PermissionError): get_source_job(api,'B','C',jid)
        finally:
            release.set()
        self.assertTrue(exported.wait(2))
        job=get_source_job(api,'A','C',jid)
        self.assertEqual(job['status'],'completed'); self.assertEqual(len(calls),1)
        self.assertEqual(document_scope(api,'A','C')['document_ids'],['D1'])
        self.assertEqual(len(traces[0]['steps']),1)
        self.assertNotIn('url',traces[0])

    def test_chat_and_indexing_traces_preserve_scope_and_tokens(self):
        from datetime import datetime
        rows=[]
        class Span:
            trace_id='TRACE'
            def __init__(self,name,kwargs): self.name=name; self.kwargs=kwargs; self.attributes={}; self.outputs=None
            def set_attribute(self,k,v): self.attributes[k]=v
            def end(self,**kwargs): self.outputs=kwargs.get('outputs')
        class MLflow:
            def start_span_no_context(self,name,**kwargs):
                row=Span(name,kwargs); rows.append(row); return row
            def get_trace(self,trace_id): return True
        ns={'datetime':datetime}
        exec(compile((ROOT/'patches/tracking_trace.py').read_text(),'tracking_trace.py','exec'),ns)
        run={'started_at':'2026-01-01T00:00:00+00:00','duration':1,'run_id':'R',
             'mode':'full','prompt_variant':'renforce','status':'completed','question':'Question','selected':{}}
        result={'route':'documents','active_skills':['document_search'],'retrieval_status':'completed',
                'answer_scope':'general','fallback_reason':'no_relevant_evidence'}
        ns['_trace'](MLflow(),run,result,'1')
        self.assertEqual(rows[0].outputs['answer_scope'],'general')
        self.assertEqual(rows[0].attributes['retrieval_status'],'completed')
        rows.clear()
        job={'started_at_ns':1,'duration_s':1,'job_id':'J','source_id':'S','status':'completed',
             'documents_indexed':1,'progress':'PRIVATE URL','steps':[{'name':'Embedding','started_at_ns':2,
             'duration_s':.1,'inputs':{'batch_size':1},'details':{'embedding_model':'synthetic'},
             'usage':{'prompt_tokens':7,'total_tokens':7}}]}
        ns['source_job_trace'](MLflow(),job,'1')
        self.assertEqual(rows[1].attributes['mlflow.chat.tokenUsage']['input_tokens'],7)
        self.assertNotIn('PRIVATE URL',str(rows[0].outputs))

    def test_invalid_indexer_result_does_not_mark_source_ready(self):
        api=API(); finished=threading.Event()
        def export(job): finished.set(); return 'TRACE'
        jid=enqueue_source_sync(api,'A','C','https://sharepoint.example.invalid/site',
            allowed_roots=['https://sharepoint.example.invalid/site'],
            index_existing=lambda *a:None,export_job=export)
        self.assertTrue(finished.wait(2))
        self.assertEqual(get_source_job(api,'A','C',jid)['status'],'failed')
        self.assertFalse(document_scope(api,'A','C')['ready'])

if __name__ == '__main__': unittest.main(verbosity=2)
