"""Verify a Mac bundle against synthetic de/en WAVs and existing local models.

Run with its bundled Python. Fixtures contain de.wav, en.wav and references.json
(language, required words, second_start_seconds). All reports remain private.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app',type=Path,required=True)
    parser.add_argument('--models',type=Path,required=True)
    parser.add_argument('--fixtures',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    resources=args.app.resolve()/'Contents/Resources'
    python=resources/'Python/bin/python3.12'
    references=json.loads((args.fixtures/'references.json').read_text())
    results=[]
    for model in ('qwen3-asr-1.7b','large-v3-turbo'):
        for reference in references:
            for skip,budget in ((False,100),(False,50),(True,50)):
                language=reference['language']
                case=args.output/f'{model}-{language}-skip{int(skip)}-budget{budget}'
                case.mkdir()
                media=args.fixtures.resolve()/f'{language}.wav'
                original=hashlib.sha256(media.read_bytes()).hexdigest()
                config=case/'budget.json'
                config.write_text(json.dumps(dict(gpu_budget_percent=budget)))
                command=[str(python),'-BEs','-Xutf8',str(resources/'Engine/voxdrop.py'),
                    '--data-dir',str(args.models.resolve()),'transcribe',str(media),
                    '--output-dir',str(case.resolve()),'--language',language,'--hardware','metal','--model',model]
                command+=['--skip-silence','--dover-lap'] if skip else ['--no-speakers']
                started=time.monotonic()
                with (case/'process.log').open('w') as log:
                    process=subprocess.run(command,stdout=log,stderr=log,
                        env={**os.environ,'VOXDROP_GPU_BUDGET_CONFIG':str(config.resolve())},timeout=300)
                textfile=case/f'{language}.txt'
                text=textfile.read_text() if textfile.is_file() else ''
                times=[int(h)*3600+int(m)*60+int(s) for h,m,s,paragraph in
                    re.findall(r'\[(\d+):(\d+):(\d+)\]([^\[]*)',text)
                    if ('freitag' if language=='de' else 'friday') in paragraph.casefold()]
                missing=[word for word in reference['required'] if word not in text.casefold()]
                result=dict(model=model,language=language,skip_silence=skip,budget=budget,
                    seconds=round(time.monotonic()-started,3),exit_code=process.returncode,
                    missing_words=missing,after_pause_timestamps=times,
                    original_unchanged=hashlib.sha256(media.read_bytes()).hexdigest()==original,
                    text_sha256=hashlib.sha256(text.encode()).hexdigest())
                result['passed']=process.returncode==0 and not missing and result['original_unchanged'] and bool(times) and min(times)>=reference['second_start_seconds']-3
                results.append(result)
                (args.output/'summary.json').write_text(json.dumps(results,indent=2))
                print(json.dumps(result),flush=True)
                if process.returncode:
                    raise RuntimeError(f'Model test failed; inspect {case}/process.log')
    for model in ('qwen3-asr-1.7b','large-v3-turbo'):
        for language in ('de','en'):
            pair=[row for row in results if row['model']==model and row['language']==language and not row['skip_silence']]
            if len({row['text_sha256'] for row in pair})!=1:
                raise RuntimeError(f'Budget changed the transcript: {model}/{language}')
    if not all(row['passed'] for row in results):
        raise RuntimeError('Content/timeline acceptance failed; inspect private summary.')


if __name__=='__main__':main()
