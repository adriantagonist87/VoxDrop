"""Locate a history entry's files without relying on its success state.

The desktop runs this probe in a cancellable process: an offline share must
not block the GUI or prevent the application from closing.
"""
import json
from pathlib import Path
import sys

if __package__:
    from .transcript_search import transcript_path
else:
    from transcript_search import transcript_path


def original_candidates(job):
    source = Path(job["source"])
    archived = Path(job["completed_dir"]) / source.name
    settings = job.get("settings", {})
    if isinstance(settings, str):
        settings = json.loads(settings)
    moved = not settings.get("watch_path") or settings.get("move_media")
    paths = (archived, source) if moved and job["state"] == "done" and not job.get("origin_job_id") else (source, archived)
    return list(dict.fromkeys(paths))


def locate_files(job):
    candidates = original_candidates(job)
    original = candidates[0]
    original_found = False
    errors = []
    for path in candidates:
        try:
            if path.is_file():
                original, original_found = path, True
                break
        except OSError as error:
            errors.append(f"Originaldatei nicht erreichbar: {error.strerror or error}")
    transcript = Path(job["known_transcript_path"]) if job.get("known_transcript_path") else transcript_path(job)
    try:
        transcript_found = transcript.is_file()
    except OSError as error:
        transcript_found = False
        errors.append(f"Transkript nicht erreichbar: {error.strerror or error}")
    return dict(original=str(original.absolute()), originalAvailable=original_found,
                transcript=str(transcript.absolute()), transcriptAvailable=transcript_found,
                error="\n".join(dict.fromkeys(errors)))


if __name__ == "__main__":
    print(json.dumps(locate_files(json.loads(sys.argv[1])), ensure_ascii=True))
