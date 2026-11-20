from fastapi import FastAPI
from pydantic import BaseModel,Field
from functools import lru_cache
from pathlib import Path
import json,os,threading
from datetime import datetime,timezone
from .pipeline import Pipeline
app=FastAPI(title='CloudServe Support Automation',version='0.1.0')
class Ticket(BaseModel):
 ticket_id:str='UNKNOWN'
 channel:str
 subject:str=''
 body:str=''
 message:str=''
 customer_tier:str='unknown'
@lru_cache(maxsize=1)
def engine():return Pipeline()
@app.get('/health')
def health():return {'status':'ok','mode':'offline-extractive'}
_log_lock=threading.Lock()
@app.post('/tickets/process')
def process(ticket:Ticket):
 payload=ticket.model_dump()
 if not payload['body']:payload['body']=payload.pop('message','')
 result=engine().process(payload)
 path=Path(os.environ.get('CLOUDSERVE_DECISION_LOG','evaluation/results/api_decisions.jsonl'))
 with _log_lock:
  path.parent.mkdir(parents=True,exist_ok=True)
  with path.open('a',encoding='utf-8') as log:
   log.write(json.dumps({'timestamp_utc':datetime.now(timezone.utc).isoformat(),**result},ensure_ascii=False)+'\n')
 return result
if __name__=='__main__':
 import uvicorn
 uvicorn.run('src.api:app',host='127.0.0.1',port=8000)
