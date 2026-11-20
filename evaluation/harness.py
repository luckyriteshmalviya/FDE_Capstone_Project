"""Single-command, unattended evaluation; one record per input even on failure."""
import argparse,json,statistics,sys,traceback
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
from src.pipeline import Pipeline,load_json,normalize,ROOT

def pct(n,d):return round(100*n/d,2) if d else None
def percentile(values,p):
 if not values:return None
 a=sorted(values);return round(a[min(len(a)-1,max(0,int((len(a)-1)*p+0.999999)))],6)
def evaluate(input_path,output_path,data_dir=None):
 output=Path(output_path);output.mkdir(parents=True,exist_ok=True)
 tickets=load_json(input_path)
 if not isinstance(tickets,list):raise ValueError('Input must be a JSON array of tickets')
 engine=Pipeline(data_dir)
 results=[]
 with (output/'decisions.jsonl').open('w',encoding='utf-8') as log:
  for i,ticket in enumerate(tickets):
   try:r=engine.process(ticket)
   except Exception as e:
    n=normalize(ticket);r={'ticket_id':n['ticket_id'],'channel':n['channel'],'status':'escalated','route':'escalate','reason':f'Uncaught failure safely escalated: {type(e).__name__}','classification':{'intent':'unclear_request','urgency':'medium','confidence':0,'alternatives':[]},'sources':[],'answer':None,'escalation_summary':n['text'][:250],'validation':{'passed':False,'checks':{}},'latency_seconds':0,'response_time_minutes':0}
   r['input_index']=i;results.append(r);log.write(json.dumps(r,ensure_ascii=False)+'\n');log.flush()
 metrics=make_metrics(tickets,results)
 (output/'metrics.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False),encoding='utf-8')
 (output/'results.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
 return metrics

def make_metrics(tickets,results):
 n=len(results);statuses=Counter(r['status'] for r in results);times=[r['latency_seconds'] for r in results]
 metrics={'run_utc':datetime.now(timezone.utc).isoformat(),'tickets_processed':n,'answered_automatically':statuses['answered'],'escalated':statuses['escalated'],'blocked_by_guardrails':statuses['blocked'],'first_contact_resolution_pct':None,'automatic_answer_rate_pct':pct(statuses['answered'],n),'escalation_rate_pct':pct(statuses['escalated']+statuses['blocked'],n),'mean_response_time_minutes':round(statistics.mean([r['response_time_minutes'] for r in results]),6) if n else None,'median_response_time_minutes':round(statistics.median([r['response_time_minutes'] for r in results]),6) if n else None,'latency_median_seconds':round(statistics.median(times),6) if n else None,'latency_p95_seconds':percentile(times,.95),'retrieval_hit_rate_pct':pct(sum(bool(r['sources']) for r in results),n),'decisions_logged':n,'guardrail_activations_by_type':dict(Counter(r['reason'] for r in results if r['status']=='blocked')),'private_data_detections':sum(len(r['validation'].get('checks',{}).get('private_data',[])) for r in results),'citation_resolution_pct':pct(sum(bool(r['answer']) and bool(r['validation'].get('passed')) for r in results),statuses['answered']),'limitations':['Response time is local processing latency, not actual customer delivery time.','First-contact resolution cannot be measured without customer outcome data; automatic_answer_rate_pct is reported separately.','No human hallucination or satisfaction review has been conducted.']}
 y_true=[];y_pred=[];route_pairs=[]
 for ticket,result in zip(tickets,results):
  labels=ticket.get('labels',{}) if isinstance(ticket,dict) else {}
  if 'intent' in labels:y_true.append(labels['intent']);y_pred.append(result['classification']['intent'])
  if 'expected_route' in labels:route_pairs.append((labels['expected_route'],result['route']))
 if y_true:
  from sklearn.metrics import classification_report,confusion_matrix
  metrics['classification_report']=classification_report(y_true,y_pred,output_dict=True,zero_division=0)
  metrics['classification_precision_recall_per_class']={k:{'precision':round(v['precision'],4),'recall':round(v['recall'],4),'support':int(v['support'])} for k,v in metrics['classification_report'].items() if isinstance(v,dict) and 'support' in v}
  metrics['classification_accuracy_pct']=pct(sum(a==b for a,b in zip(y_true,y_pred)),len(y_true))
  metrics['confusion_matrix_labels']=sorted(set(y_true+y_pred));metrics['confusion_matrix']=confusion_matrix(y_true,y_pred,labels=metrics['confusion_matrix_labels']).tolist()
  bins=defaultdict(list)
  for truth,pred,r in zip(y_true,y_pred,results):bins[min(4,int(r['classification']['confidence']*5))].append((r['classification']['confidence'],int(truth==pred)))
  metrics['calibration_bands']=[{'band':f'{i*20}-{(i+1)*20}%','count':len(v),'mean_confidence':round(statistics.mean(x[0] for x in v),4),'observed_accuracy':round(statistics.mean(x[1] for x in v),4)} for i,v in sorted(bins.items())]
 if route_pairs:metrics['routing_agreement_pct']=pct(sum(a==b for a,b in route_pairs),len(route_pairs))
 if len(tickets)==n:metrics['complete_run']=True
 return metrics

def main():
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--data-dir',default=None)
 a=p.parse_args();m=evaluate(a.input,a.output,a.data_dir)
 print(json.dumps({k:m[k] for k in ['tickets_processed','answered_automatically','escalated','blocked_by_guardrails','complete_run']},indent=2))
if __name__=='__main__':main()
