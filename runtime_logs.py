"""Bound background diagnostics without dropping retained job history."""

import logging
from logging.handlers import RotatingFileHandler


class QuietRotatingHandler(RotatingFileHandler):
    def handleError(self, record):
        # stderr is redirected here. A full disk must not recurse into itself.
        pass


class RollingLog:
    encoding = "utf-8"

    def __init__(self, path, *, max_bytes=4 * 1024 * 1024, backups=2):
        self.handler = QuietRotatingHandler(path, maxBytes=max_bytes, backupCount=backups,
                                           encoding="utf-8")
        self.limit = min(64_000, max_bytes // 4)

    def write(self, text):
        if text.rstrip("\r\n"):
            message = text.rstrip("\r\n")
            if len(message) > self.limit:
                message = message[:self.limit] + " … [gekürzt]"
            self.handler.handle(logging.LogRecord("voxdrop", logging.INFO, "", 0,
                                                  message, (), None))
        return len(text)

    def flush(self):
        self.handler.flush()

    def isatty(self):
        return False

    def close(self):
        self.handler.close()
