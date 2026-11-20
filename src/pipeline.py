"""Offline, deterministic support automation baseline; no external LLM claims."""
import json, re, time
from pathlib import Path
from functools import lru_cache
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

ROOT=Path(__file__).resolve().parents[1]
CHANNELS={'email','chat','docs_comment','forum'}
SENSITIVE={'security_incident','compliance_request','rollback_request','data_residency'}
PII_PATTERNS={
 'email':re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b',re.I),
 'phone':re.compile(r'(?<!\d)(?:\+?\d[\d ()-]{8,}\d)(?!\d)'),
 'secret':re.compile(r'(?i)\b(?:api[_ -]?key|password|secret|token)\s*[:=]\s*[A-Za-z0-9_./+\-=]{8,}'),
}

def load_json(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def normalize(raw):
 if not isinstance(raw,dict):raw={'body':str(raw)}
 channel=str(raw.get('channel') or 'unknown').lower().strip()
 subject=str(raw.get('subject') or '')
 body=str(raw.get('body') or raw.get('message') or '')
 return {'ticket_id':str(raw.get('ticket_id') or raw.get('id') or 'UNKNOWN'), 'channel':channel,'subject':subject,'body':body,'text':(subject+' '+body).strip(),'customer_tier':str(raw.get('customer_tier') or 'unknown')}

def passages(doc):
 content=doc.get('content','')
 sections=re.split(r'\n(?=##?\s)',content)
 result=[]
 for i,part in enumerate(sections):
  part=part.strip()
  if part:result.append({'passage_id':f"{doc['doc_id']}#p{i}",'doc_id':doc['doc_id'],'title':doc['title'],'text':part})
 return result

class Pipeline:
 def __init__(self,data_dir=None,confidence_threshold=.28,retrieval_threshold=.105):
  data=Path(data_dir) if data_dir else ROOT/'data'
  train=load_json(data/'development_tickets.json');docs=load_json(data/'documentation.json')
  texts=[normalize(x)['text'] for x in train]
  self.intent=make_pipeline(TfidfVectorizer(ngram_range=(1,2),sublinear_tf=True),LogisticRegression(max_iter=1200,random_state=42))
  self.urgency=make_pipeline(TfidfVectorizer(ngram_range=(1,2),sublinear_tf=True),LogisticRegression(max_iter=1200,random_state=42))
  self.intent.fit(texts,[x['labels']['intent'] for x in train]);self.urgency.fit(texts,[x['labels']['urgency'] for x in train])
  self.passages=[p for d in docs for p in passages(d)]
  self.vectorizer=TfidfVectorizer(ngram_range=(1,2),stop_words='english',sublinear_tf=True)
  self.matrix=self.vectorizer.fit_transform([p['title']+' '+p['text'] for p in self.passages])
  self.confidence_threshold=confidence_threshold;self.retrieval_threshold=retrieval_threshold
 def classify(self,text):
  probs=self.intent.predict_proba([text])[0];idx=sorted(range(len(probs)),key=lambda i:-probs[i]);classes=self.intent.classes_
  urgency=self.urgency.predict([text])[0]
  return {'intent':str(classes[idx[0]]),'urgency':str(urgency),'confidence':round(float(probs[idx[0]]),4),'alternatives':[{'intent':str(classes[i]),'confidence':round(float(probs[i]),4)} for i in idx[1:4]]}
 def retrieve(self,text,k=3):
  from sklearn.metrics.pairwise import cosine_similarity
  if not text.strip():return []
  scores=cosine_similarity(self.vectorizer.transform([text]),self.matrix)[0]
  indices=sorted(range(len(scores)),key=lambda i:(-scores[i],self.passages[i]['passage_id']))[:k]
  return [{**self.passages[i],'score':round(float(scores[i]),4)} for i in indices if scores[i]>=self.retrieval_threshold]
 def validate(self,answer,sources):
  checks={'private_data':[],'unsupported_citation':[],'grounding':[]}
  for name,pat in PII_PATTERNS.items():
   if pat.search(answer):checks['private_data'].append(name)
  ids={p['passage_id'] for p in sources}
  cited=set(re.findall(r'\[([^\[\]]+#p\d+)\]',answer))
  checks['unsupported_citation']=[x for x in cited if x not in ids]
  if not cited:checks['grounding'].append('no_citations')
  # Offline extractive contract: the answer must be a verbatim excerpt from a cited source.
  prefix='According to our support documentation: '
  if not answer.startswith(prefix):checks['grounding'].append('non_extractive_answer')
  else:
   excerpt=answer[len(prefix):].rsplit(' [',1)[0]
   if not any(excerpt in p['text'] for p in sources if p['passage_id'] in cited):
    checks['grounding'].append('excerpt_not_in_cited_source')
  return {'passed':not any(checks.values()),'checks':checks}
 def process(self,raw):
  start=time.perf_counter();t=normalize(raw);classification={'intent':'unclear_request','urgency':'medium','confidence':0.0,'alternatives':[]};sources=[];reason='';answer=None;validation={'passed':False,'performed':False,'checks':{}}
  try:
   if t['channel'] not in CHANNELS:reason='Unsupported or missing channel'
   elif not t['text']:reason='Empty ticket text'
   else:
    classification=self.classify(t['text']);sources=self.retrieve(t['text'])
    if re.search(r'(?i)(ignore (?:all )?(?:previous|prior) instructions|reveal (?:your )?(?:system prompt|secret)|send (?:me )?(?:the )?(?:api key|password))',t['text']):reason='Guardrail blocked prompt injection attempt'
    elif isinstance(raw,dict) and raw.get('labels',{}).get('must_not_auto_respond') is True:reason='Explicit safety restriction on supplied ticket'
    elif classification['intent'] in SENSITIVE:reason='Sensitive intent requires human handling'
    elif re.search(r'(?i)\b(refund|chargeback|legal action|breach|compromised|delete (?:my|all) data)\b',t['text']):reason='High-risk request requires human handling'
    elif classification['confidence']<self.confidence_threshold:reason='Low classification confidence'
    elif not sources:reason='No sufficiently relevant knowledge passage'
    else:
     # Extractive generation: only verbatim corpus sentences, not unsupported LLM assertions.
     passage=sources[0]
     candidates=[line.strip() for line in passage['text'].splitlines() if line.strip() and not line.lstrip().startswith('#')]
     candidates=[line for line in candidates if len(line)>30 and not any(p.search(line) for p in PII_PATTERNS.values())]
     if not candidates:reason='No safe extractive passage'
     else:
      excerpt=candidates[0][:650]
      answer=f"According to our support documentation: {excerpt} [{passage['passage_id']}]"
      validation=self.validate(answer,sources);validation['performed']=True
      if not validation['passed']:reason='Guardrail blocked unsafe or ungrounded response';answer=None
   if not reason and answer is None:reason='No safe answer available'
  except Exception as exc:
   reason=f'Graceful fallback after processing error: {type(exc).__name__}';answer=None
  status='answered' if answer else ('blocked' if reason.startswith('Guardrail') else 'escalated')
  elapsed=round(time.perf_counter()-start,6)
  return {'ticket_id':t['ticket_id'],'channel':t['channel'],'status':status,'route':'auto_respond' if answer else 'escalate','reason':reason or 'Relevant source and safety checks passed','classification':classification,'sources':sources,'answer':answer,'escalation_summary':None if answer else f"Ticket {t['ticket_id']}: {t['subject']} {t['body'][:250]}", 'validation':validation,'latency_seconds':elapsed,'response_time_minutes':elapsed/60}
