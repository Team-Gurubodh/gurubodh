class ProgressReporter:
    def __init__(self, enabled=True):
        self.enabled = enabled

    def report(self, message):
        if self.enabled:
            print(message, flush=True)


DEFAULT_PROGRESS_REPORTER = ProgressReporter()
