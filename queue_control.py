"""Persistent queue ordering and cancellation; never delete source recordings."""
import sqlite3
import time
from contextlib import closing


class JobCancelled(Exception):
    pass


PENDING = "(j.state IN ('seen','ready') OR (j.state='failed' AND r.job_id IS NOT NULL))"


def initialise_queue(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS queue_state (
            id INTEGER PRIMARY KEY CHECK(id=1), paused INTEGER NOT NULL DEFAULT 0
        );
        INSERT OR IGNORE INTO queue_state VALUES (1,0);
        CREATE TABLE IF NOT EXISTS queue_positions (
            job_id INTEGER PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
            position INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS queue_position_order ON queue_positions(position,job_id);
        CREATE TABLE IF NOT EXISTS cancel_requests (
            job_id INTEGER PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
            requested REAL NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS queue_insert AFTER INSERT ON jobs BEGIN
            INSERT INTO queue_positions VALUES(new.id,
                COALESCE((SELECT MAX(position) FROM queue_positions),0)+1);
        END;
        CREATE TRIGGER IF NOT EXISTS queue_restore AFTER UPDATE OF state ON jobs
        WHEN new.state='ready' AND old.state='cancelled' BEGIN
            UPDATE queue_positions SET position=
                COALESCE((SELECT MAX(position) FROM queue_positions),0)+1 WHERE job_id=new.id;
            DELETE FROM cancel_requests WHERE job_id=new.id;
        END;
    """)
    with db:
        # Preserve the previous detected/id order when opening an older profile.
        db.execute("""INSERT OR IGNORE INTO queue_positions(job_id,position)
            SELECT id, COALESCE((SELECT MAX(position) FROM queue_positions),0)
                + ROW_NUMBER() OVER (ORDER BY detected,id)
            FROM jobs WHERE id NOT IN (SELECT job_id FROM queue_positions)""")


def queue_jobs(db):
    return db.execute(f"""SELECT j.*, q.position AS queue_position,
        a.seconds AS audio_seconds,r.retry_at,
        EXISTS(SELECT 1 FROM cancel_requests c WHERE c.job_id=j.id) AS cancel_requested
        FROM jobs j JOIN queue_positions q ON q.job_id=j.id
        LEFT JOIN job_retries r ON r.job_id=j.id
        LEFT JOIN audio_durations a ON a.job_id=j.id
        WHERE {PENDING} ORDER BY q.position,j.id""").fetchall()


def queue_paused(db):
    return bool(db.execute('SELECT paused FROM queue_state WHERE id=1').fetchone()[0])


def set_queue_paused(db, paused):
    with db:
        db.execute('UPDATE queue_state SET paused=? WHERE id=1',(int(paused),))


def move_queue_item(db, job_id, before_id=0):
    with db:
        db.execute('BEGIN IMMEDIATE')
        ids=[row['id'] for row in queue_jobs(db)]
        if job_id not in ids or (before_id and before_id not in ids):
            raise ValueError('Die Warteschlange hat sich geändert. Bitte erneut verschieben.')
        if job_id==before_id:
            return
        ids.remove(job_id)
        ids.insert(ids.index(before_id) if before_id else len(ids),job_id)
        db.executemany('UPDATE queue_positions SET position=? WHERE job_id=?',
                       [(index,identifier) for index,identifier in enumerate(ids,1)])


def _cancel(db, job_id):
    row=db.execute('SELECT state,publication_started FROM jobs WHERE id=?',(job_id,)).fetchone()
    if not row:
        raise ValueError('Auftrag nicht gefunden.')
    if row['state'] in ('seen','ready') or (row['state']=='failed' and db.execute(
        'SELECT 1 FROM job_retries WHERE job_id=?',(job_id,)).fetchone()):
        now=time.time()
        db.execute("""UPDATE jobs SET state='cancelled',updated=?,finished=?,error=NULL,
            phase=NULL,progress=NULL WHERE id=?""",(now,now,job_id))
        db.execute('DELETE FROM job_retries WHERE job_id=?',(job_id,))
        return 'cancelled'
    if row['state'] in ('copying','transcribing') and not row['publication_started']:
        db.execute('INSERT OR IGNORE INTO cancel_requests VALUES (?,?)',(job_id,time.time()))
        return 'requested'
    if row['state']=='cancelled':
        return 'cancelled'
    raise ValueError('Dieser Auftrag kann nicht mehr abgebrochen werden. Ein begonnener Export wird sicher fertiggestellt.')


def cancel_job(db, job_id):
    with db:
        db.execute('BEGIN IMMEDIATE')
        return _cancel(db,job_id)


def cancel_queue(db):
    with db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('UPDATE queue_state SET paused=1 WHERE id=1')
        ids={row['id'] for row in queue_jobs(db)}
        ids.update(row[0] for row in db.execute("""SELECT id FROM jobs
            WHERE state IN ('copying','transcribing') AND publication_started=0"""))
        for job_id in ids:
            _cancel(db,job_id)
        return len(ids)


def cancellation_requested(db, job_id):
    return db.execute('SELECT 1 FROM cancel_requests WHERE job_id=?',(job_id,)).fetchone() is not None


def poll_cancellation(state, job_id):
    # Called by the subprocess monitor on a separate thread/connection.
    try:
        with closing(sqlite3.connect((state/'jobs.sqlite3').as_uri()+'?mode=ro',uri=True,timeout=.2)) as db:
            return cancellation_requested(db,job_id)
    except sqlite3.Error:
        return False
