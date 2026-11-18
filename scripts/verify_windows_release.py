"""Verify the published Windows ZIP and optional installation against its manifest."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from urllib.request import urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source,'sha256').hexdigest()


def verify(manifest, archive=None, installation=None):
    expected = {item['path']:item for item in manifest['files']}
    if len(expected) != len(manifest['files']):
        raise ValueError('Duplicate manifest paths')
    for name in expected:
        path=PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
            raise ValueError('Unsafe manifest path')
    if archive is not None:
        if digest(archive) != manifest['archive_sha256']:
            raise ValueError('Archive checksum mismatch')
        with ZipFile(archive) as zipped:
            members={}
            for item in zipped.infolist():
                path=PurePosixPath(item.filename)
                if path.is_absolute() or '..' in path.parts or '\\' in item.filename or ':' in item.filename or not path.parts or path.parts[0]!='VoxDrop':
                    raise ValueError('Unsafe archive member')
                if item.is_dir():continue
                relative='/'.join(path.parts[1:])
                if relative in members:raise ValueError('Duplicate archive member')
                members[relative]=item
            if members.keys() != expected.keys():
                raise ValueError('Packaged files differ from manifest')
            for name,item in members.items():
                with zipped.open(item) as source:
                    actual=hashlib.file_digest(source,'sha256').hexdigest()
                if actual!=expected[name]['sha256'] or item.file_size!=expected[name]['size']:
                    raise ValueError('Packaged file mismatch: '+name)
    if installation is not None:
        for name,item in expected.items():
            path=installation/name
            if not path.is_file() or path.stat().st_size!=item['size'] or digest(path)!=item['sha256']:
                raise ValueError('Installed file mismatch: '+name)
    return dict(passed=True,code_commit=manifest['code_commit'],files_verified=len(expected),
        archive_verified=archive is not None,installation_verified=installation is not None)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=ROOT/'releases/v1.4.0/windows-release.json')
    parser.add_argument('--zip',type=Path)
    parser.add_argument('--app-dir',type=Path)
    parser.add_argument('--download',action='store_true')
    args=parser.parse_args()
    if not (args.zip or args.app_dir or args.download):parser.error('Choose --zip, --app-dir or --download')
    manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
    archive=args.zip
    if args.download:
        folder=ROOT/'.runtime/release-verification';folder.mkdir(parents=True,exist_ok=True)
        archive=folder/manifest['archive_name']
        with urlopen(manifest['download_url'],timeout=90) as response,archive.open('wb') as output:
            while block:=response.read(1024*1024):output.write(block)
    print(json.dumps(verify(manifest,archive,args.app_dir),indent=2))


if __name__=='__main__':main()
