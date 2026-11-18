"""Measure Windows model boundaries using installed models and synthetic audio.

Run with the installed runtime: APP SYNTHETIC_WAV NEW_OUTPUT_DIRECTORY [--model MODEL].
Keeps the transcript private; the report contains metadata and whole-GPU VRAM only.
Other desktop apps contribute to those totals. This is not a language-quality test.
"""
import argparse,gc,hashlib,json,re,subprocess,sys,time
from pathlib import Path
if sys.platform != 'win32':raise SystemExit('Windows CUDA check required')
cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('app',type=Path);cli.add_argument('media',type=Path);cli.add_argument('output',type=Path);cli.add_argument('--model',choices=('large-v3-turbo','qwen3-asr-1.7b'),default='large-v3-turbo');args=cli.parse_args()
args.app=args.app.resolve();args.media=args.media.resolve();args.output.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(args.app/'Engine'))
import voxdrop
voxdrop.configure_runtime(args.app/'Modelle')
from aTrain_core import engine
points=[];started=time.monotonic()
def point(label):
    r=subprocess.run([r'C:\Windows\System32\nvidia-smi.exe','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    item=dict(seconds=round(time.monotonic()-started,3),phase=label,gpu_total_mib=int(r.stdout.strip()));points.append(item);print(json.dumps(item),flush=True)
load=voxdrop.load_whisper
def whisper(*a,**k):
    p=load(*a,**k);point('whisper_loaded');close=p.close
    def release():
        point('before_whisper_close');close();gc.collect();point('after_whisper_close')
    p.close=release
    return p
voxdrop.load_whisper=whisper
load_speaker=engine.load_diarizer
def speaker(*a,**k):
    point('before_speaker_load');p=load_speaker(*a,**k);point('speaker_loaded');return p
engine.load_diarizer=speaker
qwen=voxdrop.qwen_backend.transcribe
def speech(*a,**k):
    out=qwen(*a,**k);point('qwen_process_exited');return out
voxdrop.qwen_backend.transcribe=speech
sha=hashlib.sha256(args.media.read_bytes()).hexdigest();measurements={}
point('baseline')
text=voxdrop.transcribe(args.media,model=args.model,hardware='cuda',language='auto-detect',speakers=True,speaker_count=2,dover_lap=True,skip_silence=True,report=lambda phase,fraction: None,measurements=measurements)
gc.collect()
import torch
torch.cuda.empty_cache()
point('job_models_released')
assert hashlib.sha256(args.media.read_bytes()).hexdigest()==sha
result=dict(code_commit=json.loads((args.app/'build-info.json').read_text())['code_commit'],model=args.model,points=points,measurements=measurements,original_unchanged=True,text_length=len(text),speaker_labels=sorted(set(re.findall(r'Sprecher \d+',text))))
(args.output/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2),flush=True)

order=[p['phase'] for p in points]
if args.model=='large-v3-turbo':
    assert order.index('after_whisper_close')<order.index('before_speaker_load'), 'Whisper still loaded at speaker entry'
else:
    assert order.index('qwen_process_exited')<order.index('before_speaker_load'), 'Qwen still running at speaker entry'
