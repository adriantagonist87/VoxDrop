"""Byte-accurate, process-local reporting for the pinned Hub downloaders."""
import argparse
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
import importlib
import json
import os
from pathlib import Path
import re
import sys
from threading import Event, RLock, Thread
import time
from urllib.parse import urlsplit

EVENT = 'voxdrop-download:'


@dataclass
class ModelSpec:
    key: str
    repo: str
    revision: str
    files: tuple
    directory: Path


def selected_models(data_dir, model, speakers):
    from voxdrop import configured_models, DEFAULT_MODEL
    specs = [ModelSpec(name, entry['repo_id'], entry['revision'], tuple(entry['files']), directory)
             for name, directory, entry in configured_models(speakers, model)]
    if model == DEFAULT_MODEL:
        from qwen_backend import model_manifest
        specs.extend(ModelSpec(key, entry['repo'], entry['revision'], tuple(entry['files']),
                               data_dir/'models'/key) for key, entry in model_manifest().items())
    return specs


def error_detail(error):
    chain, seen = [error], set()
    while chain:
        current = chain.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if getattr(current, 'winerror', None) == 10013 or '10013' in str(current):
            return 'Lokaler Netzwerkzugriff verweigert (WinError 10013).'
        chain.extend(item for item in (current.__cause__, current.__context__) if item is not None)
    status = getattr(getattr(error, 'response', None), 'status_code', None)
    if status:
        return f'Server antwortet mit HTTP {status}.'
    if 'timeout' in type(error).__name__.lower():
        return 'Zeitlimit der Verbindung erreicht; Erreichbarkeit nicht bestätigt.'
    # Signed CDN URLs can occur in library exceptions. Never put their query in UI events.
    return re.sub(r'https?://[^\s\)\"\']+', lambda match: 'https://'+urlsplit(match[0]).netloc,
                  str(error))[:700] or type(error).__name__


def server_result(spec, role, state, detail, *, host='huggingface.co', latency=None):
    return dict(id=f'{spec.key}/{role}', model=spec.key, role=role, host=host,
                state=state, detail=detail, checkedAt=time.time(), latencyMs=latency)


def inspect_server(spec, emit, *, metadata=None):
    """Probe the selected pinned file, including its redirect/CDN, from this Python."""
    import httpx
    from huggingface_hub import get_hf_file_metadata, hf_hub_url
    emit(server_result(spec, 'api', 'checking', 'Modellzugriff wird geprüft …'))
    started = time.monotonic()
    try:
        # Prefer weights: a small README on the Hub would not test the weights' CDN.
        def priority(name):
            path=spec.directory/name
            return ((metadata or {}).get(name,0), path.stat().st_size if path.is_file() else 0,
                    Path(name).suffix in ('.bin','.safetensors','.gguf','.npz'))
        filename = max(spec.files, key=priority)
        info = get_hf_file_metadata(hf_hub_url(spec.repo, filename, revision=spec.revision),
                                    token=False, timeout=5)
        emit(server_result(spec, 'api', 'reachable', 'Gepinnte Modelldatei erreichbar.',
                           latency=round((time.monotonic()-started)*1000)))
    except Exception as error:
        emit(server_result(spec, 'api', 'unconfirmed', error_detail(error)))
        emit(server_result(spec, 'files', 'unconfirmed',
                           'Dateiabruf wegen des fehlgeschlagenen Modellzugriffs nicht erneut prüfbar.'))
        return
    host = urlsplit(info.location).hostname or 'Modell-Dateiserver'
    emit(server_result(spec, 'files', 'checking', 'Dateiabruf über den Downloadpfad wird geprüft …', host=host))
    started = time.monotonic()
    try:
        with httpx.Client(follow_redirects=True, timeout=5) as client:
            with client.stream('GET', info.location, headers={'Range':'bytes=0-0', 'Accept-Encoding':'identity'}) as response:
                response.raise_for_status()
                if not next(response.iter_raw(chunk_size=1), b'') and info.size:
                    raise OSError('Der Dateiserver liefert keine Daten.')
                host = response.url.host
        emit(server_result(spec, 'files', 'reachable', 'Dateiabruf von diesem PC erfolgreich.',
                           host=host, latency=round((time.monotonic()-started)*1000)))
    except Exception as error:
        emit(server_result(spec, 'files', 'unconfirmed', error_detail(error), host=host))


class DownloadReport:
    def __init__(self, specs, emit, *, clock=time.monotonic):
        self.specs = {spec.key:spec for spec in specs}
        self.emit = emit
        self.clock = clock
        self.lock = RLock()
        self.files = {}
        self.servers = {}
        self.phase = 'preparing'
        self.message = 'Dateien und Größen werden ermittelt …'
        self.current_model = ''
        self.transferred = 0
        self.last_data = None
        self.samples = deque([(clock(), 0)])
        self.last_emit = -1.
        self.closed = False
        self.stop = Event()
        for spec in specs:
            for filename in spec.files:
                self.file(spec.key, filename)

    def file(self, model, name):
        key = model+'/'+name
        if key not in self.files:
            self.files[key] = dict(id=key, model=model, name=name, size=None, done=0,
                                   status='waiting', cached=False, networkBytes=0)
        return self.files[key]

    def snapshot(self):
        now = self.clock()
        self.samples.append((now, self.transferred))
        while len(self.samples)>2 and self.samples[1][0] <= now-3:
            self.samples.popleft()
        oldest = self.samples[0]
        rate = (self.transferred-oldest[1])/max(.001, now-oldest[0])
        if self.last_data is None or now-self.last_data>=3 or self.phase!='downloading':
            rate = 0.
        files = [dict(item) for item in self.files.values()]
        known = bool(files) and all(item['size'] is not None for item in files)
        total = sum(item['size'] or 0 for item in files) if known else None
        done = sum(item['done'] for item in files)
        servers=[dict(server) for server in self.servers.values()]
        for server in servers:
            if server['role']=='transfer' and (self.phase!='downloading' or self.last_data is None or now-self.last_data>=3):
                server.update(state='last-received',detail='Datenempfang beim Download bestätigt; zuletzt '+time.strftime('%H:%M:%S',time.localtime(server['checkedAt'])))
        return dict(phase=self.phase, message=self.message, currentModel=self.current_model,
            files=files, servers=servers, bytesTotal=total, bytesCompleted=done,
            fraction=min(1.,done/total) if total else None, bytesPerSecond=round(rate),
            networkTransferred=self.transferred,
            waitingSeconds=round(now-self.last_data,1) if self.last_data is not None else None)

    def publish(self, *, force=False):
        with self.lock:
            if self.closed or (not force and self.clock()-self.last_emit<.2):
                return
            self.last_emit = self.clock()
            self.emit(self.snapshot())

    def phase_changed(self, phase, message):
        with self.lock:
            if phase=='downloading' and self.phase!='downloading':
                self.samples=deque([(self.clock(),self.transferred)])
                self.last_data=None
            self.phase, self.message = phase, message
            self.publish(force=True)

    def server(self, result):
        with self.lock:
            self.servers[result['id']] = result
            self.publish(force=True)

    def prepare(self, *, api=None):
        """Remote sizes for a missing model; a fully local setup remains offline-capable."""
        missing = any(not (spec.directory/name).is_file() for spec in self.specs.values() for name in spec.files)
        self.publish(force=True)
        if not missing:
            self.phase_changed('verifying', 'Vorhandene Dateien werden geprüft …')
            return
        if api is None:
            from huggingface_hub import HfApi
            api = HfApi(token=False)
        for spec in self.specs.values():
            self.server(server_result(spec, 'api', 'checking', 'Dateigrößen werden abgefragt …'))
            started = self.clock()
            try:
                info = api.model_info(spec.repo, revision=spec.revision, files_metadata=True, timeout=8)
                sizes = {item.rfilename:item.size for item in info.siblings if item.size is not None}
                with self.lock:
                    for name in spec.files:
                        record = self.file(spec.key, name)
                        record['size'] = sizes.get(name)
                        path = spec.directory/name
                        if path.is_file() and record['size'] == path.stat().st_size:
                            record.update(done=record['size'], cached=True, status='present')
                self.server(server_result(spec, 'api', 'reachable', 'Dateiliste und Größen erreichbar.',
                                          latency=round((self.clock()-started)*1000)))
            except Exception as error:
                # The download itself may still work from cache or through a different route.
                self.server(server_result(spec, 'api', 'unconfirmed', error_detail(error)))

    def model(self, key):
        with self.lock:
            self.current_model = key
        self.phase_changed('verifying', f'{key}: vorhandene Dateien prüfen …')

    def verifying(self, key, *, installing=False):
        with self.lock:
            self.current_model = key
        self.phase_changed('installing' if installing else 'verifying',
            f'{key}: Dateien im Modellspeicher ablegen …' if installing else f'{key}: Prüfsummen werden geprüft …')

    def verified(self, key):
        with self.lock:
            spec = self.specs[key]
            for name in spec.files:
                size = (spec.directory/name).stat().st_size
                record = self.file(key,name)
                record.update(size=size, done=size, status='verified', cached=record['networkBytes']==0)
            self.publish(force=True)

    def position(self, key, name, position, size=None):
        with self.lock:
            record = self.file(key,name)
            if size is not None:
                record['size'] = int(size)
            position=max(0,int(position))
            if position<record['done']:
                self.message=f'{name}: Teiltransfer wird erneut begonnen …'
            record['done'] = position
            record['status'] = 'downloading'
            self.publish()

    def transfer(self, amount, key=None, name=None):
        if amount<=0:
            return  # A resume rollback changes file progress, not bytes already transferred.
        with self.lock:
            self.transferred += int(amount)
            self.last_data = self.clock()
            if key is not None:
                self.file(key,name)['networkBytes'] += int(amount)
                self.servers[f'{key}/transfer']=server_result(self.specs[key],'transfer','receiving',
                    'Der Downloadprozess empfängt Daten.',host='Hugging Face / Xet')
            self.publish()

    def completed_file(self, key, name, path, *, transferred):
        with self.lock:
            size = Path(path).stat().st_size
            record = self.file(key,name)
            record.update(size=size,done=size,status='downloaded',cached=not transferred)
            self.publish(force=True)

    def bar_class(self, key, name):
        from tqdm.auto import tqdm
        report = self
        class NullOutput:
            def write(self, text):return len(text)
            def flush(self):pass
        class FileProgress(tqdm):
            def __init__(self,*args,**kwargs):
                kwargs.pop('name',None)
                kwargs.update(file=NullOutput(),disable=False,mininterval=.2)
                super().__init__(*args,**kwargs)
                report.position(key,name,self.n,self.total)
            def update(self,n=1):
                result=super().update(n)
                report.position(key,name,self.n,self.total)
                return result
            def update_transfer(self,n=1):report.transfer(n,key,name)
            def set_transfer_postfix_str(self,*args,**kwargs):pass
        FileProgress.set_lock(RLock())
        return FileProgress

    @contextmanager
    def track_hub(self):
        """Use public per-file tqdm callbacks without changing vendor sources or pins."""
        import huggingface_hub as hub
        from huggingface_hub import constants
        from tqdm.auto import tqdm
        snapshots = importlib.import_module('huggingface_hub._snapshot_download')
        resources = importlib.import_module('aTrain_core.load_resources')
        original_file = snapshots.hf_hub_download
        original_snapshot = hub.snapshot_download
        original_vendor = resources.snapshot_download
        original_chunk_size = constants.DOWNLOAD_CHUNK_SIZE
        report = self
        class QuietProgress(tqdm):
            def __init__(self,*args,**kwargs):
                kwargs.pop('name',None);kwargs['disable']=True
                super().__init__(*args,**kwargs)
        QuietProgress.set_lock(RLock())
        def snapshot(*args,**kwargs):
            kwargs['tqdm_class']=QuietProgress
            report.phase_changed('downloading', 'Dateien herunterladen oder aus dem Cache übernehmen …')
            return original_snapshot(*args,**kwargs)
        def file(repo_id,*args,**kwargs):
            name=kwargs.get('filename',args[0] if args else '')
            spec=next((item for item in report.specs.values() if item.repo==repo_id),None)
            if spec is None:
                return original_file(repo_id,*args,**kwargs)
            kwargs['tqdm_class']=report.bar_class(spec.key,name)
            result=original_file(repo_id,*args,**kwargs)
            if isinstance(result,(str,Path)):
                report.completed_file(spec.key,name,result,transferred=report.file(spec.key,name)['networkBytes']>0)
            return result
        snapshots.hf_hub_download=file
        hub.snapshot_download=resources.snapshot_download=snapshot
        constants.DOWNLOAD_CHUNK_SIZE=64*1024
        self.stop.clear()
        def heartbeat():
            while not self.stop.wait(.5):self.publish(force=True)
        ticker=Thread(target=heartbeat,daemon=True);ticker.start()
        try:
            yield
        finally:
            self.stop.set();ticker.join(2)
            snapshots.hf_hub_download=original_file
            hub.snapshot_download=original_snapshot
            resources.snapshot_download=original_vendor
            constants.DOWNLOAD_CHUNK_SIZE=original_chunk_size


def emit_event(payload):
    print(EVENT+json.dumps(payload,ensure_ascii=True,separators=(',',':')),flush=True)


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=('setup-models','check-model-server'))
    parser.add_argument('--model-data',type=Path,required=True)
    parser.add_argument('--model',default='qwen3-asr-1.7b')
    parser.add_argument('--no-speakers',action='store_true')
    args=parser.parse_args(argv)
    from voxdrop import configure_runtime,setup_models
    configure_runtime(args.model_data,setup=True)
    report=DownloadReport(selected_models(args.model_data,args.model,not args.no_speakers),emit_event)
    try:
        if args.command=='check-model-server':
            for spec in report.specs.values():inspect_server(spec,report.server)
            report.phase_changed('checked','Serverprüfung beendet.')
        else:
            with report.track_hub():
                report.prepare()
                setup_models(args.model_data,args.model,speakers=not args.no_speakers,report=report)
                report.phase_changed('complete','Alle Modelle heruntergeladen und verifiziert.')
        return 0
    except Exception as error:
        detail=error_detail(error)
        report.phase_changed('error',detail)
        print('Fehler: '+detail,file=sys.stderr)
        return 1
    finally:
        report.closed=True


if __name__=='__main__':
    raise SystemExit(main())
