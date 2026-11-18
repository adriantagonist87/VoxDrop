"""Join SAPI fixture parts with a known pause; use after the companion PS1."""
import json
import sys
import wave
from pathlib import Path

root = Path(sys.argv[1]).resolve()
cases = json.loads((root / 'references.json').read_text(encoding='utf-8-sig'))
for case in cases:
    chunks = []
    for index in range(2):
        with wave.open(str(root / f'{case["language"]}-{index}.wav'), 'rb') as source:
            params = source.getparams()
            chunks.append(source.readframes(source.getnframes()))
    stride = params.framerate * params.nchannels * params.sampwidth
    pause = bytes(stride * case['pause_seconds'])
    case['second_start_seconds'] = len(chunks[0]) / stride + case['pause_seconds']
    case['duration_seconds'] = (sum(map(len, chunks)) + len(pause)) / stride
    with wave.open(str(root / f'{case["language"]}.wav'), 'wb') as out:
        out.setparams(params)
        out.writeframes(chunks[0] + pause + chunks[1])
(root / 'references.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding='utf-8')
