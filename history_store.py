"""History categories and coordination for an explicit local data reset."""
from contextlib import contextmanager
import os

from platform_io import lock_service


HISTORY_FILTERS = {
    'errors': "j.state IN ('blocked','failed')",
    'done': "(j.state='done' AND COALESCE(k.kind,'')!='reused')",
    'cancelled': "(j.state='cancelled' AND (j.attempt>0 OR j.started IS NOT NULL))",
    'existing': "(j.state IN ('existing','duplicate') OR (j.state='done' AND k.kind='reused'))",
}
HISTORY_FILTERS['all'] = '(' + ' OR '.join(HISTORY_FILTERS[key] for key in ('errors','done','cancelled')) + ')'
TRANSCRIPT_SCOPE = '(' + HISTORY_FILTERS['all'] + ' OR ' + HISTORY_FILTERS['existing'] + ')'


def media_path_key(path):
    return os.path.normcase(os.path.abspath(path))


def history_category(job):
    state=job['state']
    if state in ('blocked','failed'):
        return 'errors'
    if state in ('existing','duplicate') or (state=='done' and job.get('result_kind')=='reused'):
        return 'existing'
    if state=='done':
        return 'done'
    if state=='cancelled' and (job.get('attempt',0)>0 or job.get('started') is not None):
        return 'cancelled'
    return None


def storage_generation(db):
    row=db.execute('SELECT generation FROM storage_state WHERE id=1').fetchone()
    return row[0]


@contextmanager
def search_storage_lock(state):
    """A reset must never move an index that an owned search is still using."""
    with (state/'transcript-search.lock').open('a') as lock:
        try:
            lock_service(lock)
        except BlockingIOError as error:
            raise RuntimeError('Die Detailsuche läuft noch. Bitte zuerst beenden und erneut versuchen.') from error
        yield
