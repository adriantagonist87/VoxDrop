"""Prepare locked, model-free Windows regressions; vendor code is hash verified."""
import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import sys
import tomllib
import unittest
from urllib.request import urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = 'https://github.com/adriantagonist87/VoxDrop/releases/download/v1.3.2-windows-preview.13/VoxDrop-1.3.1-Windows-x64-a5efd22a2413.zip'
REFERENCE_SHA = 'be621da30940ab64ff3dfe14ac2d29a9c18b5a05ee6b76edc8deb0cfa8cc9775'
# CI exercises synthetic media/SQLite/Qt/processes. CPU Torch supports synthetic
# speaker tests; no CUDA libraries or model weights are downloaded.
DEPENDENCIES = ('numpy','psutil','pyside6-essentials','av','faster-whisper',
                'platformdirs','pyannote-core','scipy','intervaltree','click')


def prepare():
    folder = ROOT / '.runtime/ci'
    folder.mkdir(parents=True, exist_ok=True)
    lock = tomllib.loads((ROOT/'windows/uv.lock').read_text(encoding='utf-8'))
    packages = {item['name']: item['version'] for item in lock['package']}
    assert len(packages) == len(lock['package'])
    (folder/'constraints.txt').write_text(''.join(f'{name}=={version}\n' for name,version in sorted(packages.items())
        if name not in ('voxdrop-windows','torch')), encoding='utf-8')
    torch_version=packages['torch'].split('+',1)[0]
    torch_wheel=f'https://download.pytorch.org/whl/cpu/torch-{torch_version}%2Bcpu-cp312-cp312-win_amd64.whl'
    (folder/'requirements.txt').write_text(''.join(f'{name}=={packages[name]}\n' for name in DEPENDENCIES)
        + f'torch @ {torch_wheel}\n',encoding='utf-8')
    archive = folder/'vendor.zip'
    if not archive.is_file():
        with urlopen(REFERENCE,timeout=90) as response, archive.open('wb') as output:
            while block := response.read(1024*1024): output.write(block)
    with archive.open('rb') as source:
        if hashlib.file_digest(source,'sha256').hexdigest() != REFERENCE_SHA:
            raise ValueError('CI vendor archive checksum mismatch')
    with ZipFile(archive) as zipped:
        for item in zipped.infolist():
            path = PurePosixPath(item.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in item.filename:
                raise ValueError('Unsafe CI vendor archive member')
            if item.filename.startswith(('VoxDrop/Engine/aTrain_core/','VoxDrop/DoverPackages/')):
                zipped.extract(item,folder)
    print('Pinned aTrain/DOVER sources verified; no model downloads.')


def run():
    sys.path.insert(0,str(ROOT))
    sys.path.extend([str(ROOT/'.runtime/ci/VoxDrop/Engine'),str(ROOT/'.runtime/ci/VoxDrop/DoverPackages')])
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    os.environ['MPLCONFIGDIR'] = str(ROOT/'.runtime/ci/matplotlib')
    os.chdir(ROOT)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover('tests'))
    return not result.wasSuccessful()


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    args=parser.parse_args()
    raise SystemExit(prepare() if args.action=='prepare' else run())
