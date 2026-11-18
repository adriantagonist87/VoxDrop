"""Run installed CLI on separate German/English pause fixtures, never user media.

Usage with installed Python: APP FIXTURE_DIRECTORY NEW_PRIVATE_REPORT_DIRECTORY
Generate fixtures with create-windows-acceptance-audio.ps1 and assemble-acceptance-audio.py.
Reports include paths/transcripts; keep them outside the public repository.
"""
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import psutil

app, fixtures, reports = [Path(p).resolve() for p in sys.argv[1:]]
reports.mkdir(parents=True, exist_ok=False)
references = json.loads((fixtures / 'references.json').read_text(encoding='utf-8'))
python = app / ('Laufzeit/' + json.loads((app / 'build-info.json').read_text())['runtime'] + '/Scripts/python.exe')
code = json.loads((app / 'build-info.json').read_text())['code_commit']
flags = subprocess.CREATE_NO_WINDOW

def gpu():
    result = subprocess.run([r'C:\Windows\System32\nvidia-smi.exe', '--query-gpu=memory.used,utilization.gpu', '--format=csv,noheader,nounits'], capture_output=True, text=True, check=True, creationflags=flags)
    return [int(v.strip()) for v in result.stdout.strip().split(',')]

results = []
for model in ('qwen3-asr-1.7b', 'large-v3-turbo'):
    for reference in references:
        for skip in (False, True):
            language = reference['language']
            case = reports / f'{model}-{language}-skip-{int(skip)}'
            case.mkdir()
            media = fixtures / f'{language}.wav'
            original = hashlib.sha256(media.read_bytes()).hexdigest()
            arguments = [str(python), '-BEs', '-Xutf8', str(app / 'Engine/voxdrop.py'), '--data-dir', str(app / 'Modelle'), 'transcribe', str(media), '--output-dir', str(case), '--language', language, '--hardware', 'cuda', '--model', model]
            arguments += ['--skip-silence', '--dover-lap'] if skip else ['--no-speakers']
            baseline, _ = gpu()
            peak_gpu = baseline
            peak_util = peak_rss = 0
            started = time.monotonic()
            with (case / 'process.log').open('w', encoding='utf-8') as log:
                process = subprocess.Popen(arguments, stdout=log, stderr=log, creationflags=flags)
                while process.poll() is None:
                    used, util = gpu()
                    peak_gpu, peak_util = max(peak_gpu, used), max(peak_util, util)
                    try:
                        parent = psutil.Process(process.pid)
                        rss = sum(p.memory_info().rss for p in [parent, *parent.children(recursive=True)] if p.is_running())
                        peak_rss = max(peak_rss, rss)
                    except psutil.Error:
                        pass
                    time.sleep(1)
            textfile = case / media.with_suffix('.txt').name
            text = textfile.read_text(encoding='utf-8') if textfile.exists() else ''
            missing = [word for word in reference['required'] if word not in text.casefold()]
            marker = 'freitag' if language == 'de' else 'friday'
            marker_times = []
            for hours, minutes, seconds, paragraph in re.findall(r'\[(\d+):(\d+):(\d+)\]([^\[]*)', text):
                if marker in paragraph.casefold():
                    marker_times.append(int(hours) * 3600 + int(minutes) * 60 + int(seconds))
            timestamps_ok = bool(marker_times) and min(marker_times) >= reference['second_start_seconds'] - 3
            unchanged = hashlib.sha256(media.read_bytes()).hexdigest() == original
            end_gpu, _ = gpu()
            result = dict(code_commit=code, model=model, language=language, skip_silence=skip, speakers=skip, dover_lap=skip, seconds=round(time.monotonic()-started,3), exit_code=process.returncode, original_unchanged=unchanged, missing_words=missing, after_pause_timestamps=marker_times, after_pause_timestamps_ok=timestamps_ok, gpu_baseline_mib=baseline, gpu_peak_sampled_mib=peak_gpu, gpu_after_mib=end_gpu, gpu_util_peak=peak_util, process_tree_peak_rss_bytes=peak_rss, text_length=len(text))
            result['passed'] = process.returncode == 0 and unchanged and not missing and timestamps_ok
            results.append(result)
            (reports / 'summary.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
            print(json.dumps(result), flush=True)
if not all(item['passed'] for item in results):
    raise SystemExit('One or more language/long-pause acceptance cases failed; inspect private reports.')
