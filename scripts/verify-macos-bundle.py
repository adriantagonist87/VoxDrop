"""Create/verify the Mac bundle's first-party source manifest (no user data)."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app',type=Path)
    parser.add_argument('--write',action='store_true')
    parser.add_argument('--source',type=Path)
    args=parser.parse_args()
    resources=args.app/'Contents/Resources'
    manifest=resources/'build-info.json'
    if args.write:
        source=args.source.resolve()
        files=[path for folder in ('Desktop','Engine') for path in (resources/folder).rglob('*')
               if path.is_file() and '__pycache__' not in path.parts]
        files.extend(resources/name for name in ('VoxDropLogo.png','AppIcon.icns','LICENSE'))
        info=plistlib.loads((args.app/'Contents/Info.plist').read_bytes())
        data=dict(platform='macOS-arm64',version=info['CFBundleShortVersionString'],build=info['CFBundleVersion'],
            code_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip(),
            dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=source,text=True).strip()),
            atrain_commit='ea8a7057857220b4299c0ba0b2aaf6def2f35b87',
            files=[dict(path=str(path.relative_to(resources)),size=path.stat().st_size,sha256=digest(path)) for path in sorted(files)])
        manifest.write_text(json.dumps(data,indent=2)+'\n')
    data=json.loads(manifest.read_text())
    for item in data['files']:
        path=resources/item['path']
        if not path.resolve().is_relative_to(resources.resolve()) or path.stat().st_size!=item['size'] or digest(path)!=item['sha256']:
            raise ValueError(f'Bundle mismatch: {item["path"]}')
    print(json.dumps(dict(passed=True,version=data['version'],code_commit=data['code_commit'],dirty=data['dirty'],files=len(data['files']))))


if __name__=='__main__':main()
