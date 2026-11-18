"""Track existing results and byte-identical recordings independently of names."""
from pathlib import Path


class MediaBusy(OSError):
    pass


def initialise_media_history(db):
    db.executescript("""
        CREATE INDEX IF NOT EXISTS processed_media_hash ON jobs(media_hash)
            WHERE media_hash IS NOT NULL;
        CREATE TABLE IF NOT EXISTS known_results (
            job_id INTEGER PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            prior_job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
            transcript_path TEXT,
            transcript_hash TEXT
        );
    """)


def remember_result(db, job_id, kind, transcript, text_hash=None, prior_job_id=None):
    db.execute('INSERT OR REPLACE INTO known_results VALUES (?,?,?,?,?)',
               (job_id,kind,prior_job_id,str(transcript) if transcript else None,text_hash))


def previously_transcribed(db, media_hash, job_id):
    return db.execute("""SELECT * FROM jobs WHERE media_hash=? AND id!=?
        AND state='done' ORDER BY finished DESC,id DESC LIMIT 1""",(media_hash,job_id)).fetchone()
