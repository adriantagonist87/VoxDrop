"""Use a fresh, disposable subfolder on an already mounted SMB share.

Only copies the supplied synthetic WAV. Never scans or changes the share's other
files. Profile, models and work storage stay local. Removes only its own folder.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('app','models','fixture','share','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    root=args.output.resolve();state=root/'service';config=root/'config.json'
    share=args.share.resolve();folder=Path(tempfile.mkdtemp(prefix='VoxDrop-Mac-Abnahme-',dir=share))
    resources=args.app.resolve()/'Contents/Resources';python=resources/'Python/bin/python3.12';engine=resources/'Engine/watch_service.py'
    report=dict(passed=False)
    def run(*arguments):
        result=subprocess.run([str(python),'-BEs','-Xutf8',str(engine),'--state-dir',str(state),
            '--model-data',str(args.models.resolve()),*map(str,arguments)],capture_output=True,text=True,timeout=120)
        with (root/'process.log').open('a') as log:log.write(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('SMB test command failed; inspect private process.log')
        return result.stdout
    try:
        nested=folder/'Unterordner';nested.mkdir()
        media=nested/'Prüfung + Test, Ä.wav';shutil.copyfile(args.fixture,media)
        original=hashlib.sha256(media.read_bytes()).hexdigest()
        config.write_text(json.dumps(dict(folders=[],monitoring=False,dropped_folders=[str(folder)],
            create_output_subfolder=True,output_subfolder='_FERTIGGESTELLT',model='qwen3-asr-1.7b',
            hardware='metal',language='de',speakers=False)))
        run('enqueue-folders',config);run('run',config,'--once')
        text=media.with_suffix('.txt');assert text.is_file() and 'sonnenschein' in text.read_text().casefold()
        assert hashlib.sha256(media.read_bytes()).hexdigest()==original
        assert not (nested/'_FERTIGGESTELLT').exists()
        report['recursive_smb_drop_exported_beside_unchanged_original']=True
        with sqlite3.connect(state/'jobs.sqlite3') as db:
            identifier=db.execute('SELECT id FROM jobs').fetchone()[0]
        saved=hashlib.sha256(text.read_bytes()).hexdigest()
        run('retranscribe',identifier,config);run('run',config,'--once')
        transcripts=[p for p in nested.glob('*.txt') if not p.name.startswith('.')]
        report['transcripts']=[p.name for p in transcripts]
        assert len(transcripts)==2 and hashlib.sha256(text.read_bytes()).hexdigest()==saved
        report['retranscription_preserved_existing_smb_txt']=True
        with sqlite3.connect(state/'jobs.sqlite3') as db:
            assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert not db.execute('PRAGMA foreign_key_check').fetchall()
            assert db.execute("SELECT count(*) FROM jobs WHERE state='done'").fetchone()[0]==2
        report['passed']=True
    finally:
        assert folder.parent==share and folder.name.startswith('VoxDrop-Mac-Abnahme-') and not folder.is_symlink()
        # SMB directory descriptors can expose server normalization differences.
        # Delete the named synthetic files explicitly before removing directories.
        for path in sorted(folder.rglob('*'),key=lambda p:len(p.parts),reverse=True):
            if path.is_dir():path.rmdir()
            else:path.unlink(missing_ok=True)
        folder.rmdir()
        report['own_test_folder_removed']=not folder.exists()
        (root/'summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))


if __name__=='__main__':main()
