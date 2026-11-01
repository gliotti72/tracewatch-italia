import json, os, re, subprocess, threading, time, html
from collections import Counter
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path('/config')
ROOT.mkdir(parents=True, exist_ok=True)
STATE_FILE = ROOT / 'state.json'
OPTIONS = Path('/data/options.json')
lock = threading.RLock()

def now(): return datetime.now(timezone.utc).isoformat()
def load():
    if STATE_FILE.exists():
        try: return json.loads(STATE_FILE.read_text())
        except Exception: pass
    return {'mode':'idle','baseline':{},'samples':{},'events':[],'last':{},'started':None,'deadline':None,'ignored':[]}
state = load()
def save():
    tmp = STATE_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_FILE)
def options():
    try: return json.loads(OPTIONS.read_text())
    except Exception: return {'targets':['1.1.1.1','8.8.8.8'],'interval_seconds':300,'acquisition_minutes':60}

def trace(target):
    try:
        p = subprocess.run(['traceroute','-n','-m','25','-w','1','-q','1',target], capture_output=True,text=True,timeout=45)
        hops=[]
        for line in p.stdout.splitlines()[1:]:
            m=re.match(r'^\s*\d+\s+(\S+)',line)
            if m: hops.append(m.group(1))
        return {'time':now(),'hops':hops,'error':p.stderr.strip() if p.returncode and not hops else None}
    except Exception as e: return {'time':now(),'hops':[],'error':str(e)}

def signature(hops): return '|'.join(hops)
def worker():
    while True:
        opts=options()
        with lock:
            mode=state['mode']
            if mode=='acquiring' and state.get('deadline') and time.time() >= state['deadline']:
                finish_acquisition()
                mode=state['mode']
        if mode in ('acquiring','monitoring'):
            for target in opts.get('targets',['1.1.1.1','8.8.8.8']):
                result=trace(target)
                with lock:
                    state['last'][target]=result
                    if result['error'] or not result['hops']:
                        state['events'].append({'time':now(),'target':target,'type':'trace_error','details':result['error'] or 'No hops'})
                    elif state['mode']=='acquiring':
                        samples=state['samples'].setdefault(target,[])
                        samples.append(result['hops'])
                        state['samples'][target]=samples[-1000:]
                    elif state['mode']=='monitoring' and target in state['baseline']:
                        known=state['baseline'][target]
                        if signature(result['hops']) not in known and signature(result['hops']) not in state['ignored']:
                            state['events'].append({'time':now(),'target':target,'type':'change','hops':result['hops'],'baseline':list(known.keys())[:5]})
                    state['events']=state['events'][-500:]
                    save()
        time.sleep(max(30,int(opts.get('interval_seconds',300))))

def finish_acquisition():
    for target,samples in state['samples'].items():
        counts=Counter(signature(x) for x in samples if x)
        if counts: state['baseline'][target]=dict(counts)
    state['samples']={}
    state['mode']='monitoring' if state['baseline'] else 'idle'
    state['deadline']=None
    save()

class Handler(BaseHTTPRequestHandler):
    def send(self,code,content,kind='application/json'):
        b=content.encode();self.send_response(code);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
    def do_GET(self):
        path=urlparse(self.path).path
        if path.endswith('/api/status'):
            with lock: self.send(200,json.dumps(state));return
        if path.endswith('/') or path.endswith('/index.html'):
            self.send(200,PAGE,'text/html');return
        self.send(404,'{}')
    def do_POST(self):
        path=urlparse(self.path).path
        with lock:
            if path.endswith('/api/start'):
                state['mode']='acquiring';state['samples']={};state['started']=now();state['deadline']=time.time()+int(options().get('acquisition_minutes',60))*60
            elif path.endswith('/api/stop'):
                if state['mode']=='acquiring':finish_acquisition()
                else: self.send(409,'{"error":"Not acquiring"}');return
            elif path.endswith('/api/pause'): state['mode']='idle'
            elif path.endswith('/api/resume'): state['mode']='monitoring' if state['baseline'] else 'idle'
            else: self.send(404,'{}');return
            save();self.send(200,json.dumps({'mode':state['mode']}))
    def log_message(self,*args): pass

PAGE='''<!doctype html><html lang="it"><meta name="viewport" content="width=device-width,initial-scale=1"><meta charset="utf-8"><title>TraceWatch Italia</title><style>body{font:16px system-ui;margin:24px auto;padding:0 16px;max-width:900px;background:#101923;color:#edf3fa}button{padding:12px;margin:5px;border:0;border-radius:8px;background:#42a5f5;color:#071522;cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#1b2938;padding:15px;border-radius:8px}h1{font-size:25px}.muted{color:#aebfd0}</style><h1>TraceWatch Italia</h1><p class="muted">Monitoraggio percorsi Internet · Nessun blocco firewall attivo</p><button onclick="act('start')">Avvia / Riacquisisci</button><button onclick="act('stop')">Stop acquisizione</button><button onclick="act('pause')">Pausa sorveglianza</button><button onclick="act('resume')">Riprendi</button><h2>Stato e percorsi</h2><pre id="status">Caricamento…</pre><h2>Ultimi eventi</h2><pre id="events"></pre><script>async function act(a){await fetch('api/'+a,{method:'POST'});await refresh()}async function refresh(){try{let s=await(await fetch('api/status')).json();document.getElementById('status').textContent=JSON.stringify({modalita:s.mode,acquisizione_avviata:s.started,percorsi_originali:s.baseline,ultimi_traceroute:s.last},null,2);document.getElementById('events').textContent=JSON.stringify(s.events.slice(-20).reverse(),null,2)}catch(e){document.getElementById('status').textContent=String(e)}}refresh();setInterval(refresh,10000)</script></html>'''

threading.Thread(target=worker,daemon=True).start()
ThreadingHTTPServer(('0.0.0.0',8099),Handler).serve_forever()
