"""Resume the actual download after a user grants Windows network access."""


class NetworkPermissionError(RuntimeError):
    pass


def retry_network_permission(operation, cancel, waiting, *, interval=5):
    try:
        while not cancel.is_set():
            try:
                return operation()
            except NetworkPermissionError:
                waiting(True)
                if cancel.wait(interval):
                    break
                # A retry is an active download/check, not a confirmed denial.
                # Clear the stale warning before it can transfer large models.
                waiting(False)
        raise RuntimeError("Modelleinrichtung abgebrochen. Sie kann später fortgesetzt werden.")
    finally:
        waiting(False)
