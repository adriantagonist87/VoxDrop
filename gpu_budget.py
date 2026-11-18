"""Cooperative CUDA work/idle pacing for this app's models, never driver limits."""
import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path


def validate_percent(value):
    if type(value) is not int or not 10 <= value <= 100:
        raise ValueError('Das GPU-Arbeitsbudget muss eine ganze Zahl von 10 bis 100 sein.')
    return value


class GpuBudget:
    """Insert idle time only after completed model work; refresh live settings."""
    def __init__(self, percent=100, config=None, *, clock=time.perf_counter,
                 sleep=time.sleep, synchronize=lambda: None):
        self.percent = validate_percent(percent)
        self.config = Path(config) if config else None
        self.clock, self.sleep, self.synchronize = clock, sleep, synchronize
        self.next_read = 0
        self.idle_seconds = 0.0
        self.work_seconds = 0.0
        self.local = threading.local()

    def current_percent(self):
        now = self.clock()
        if self.config and now >= self.next_read:
            self.next_read = now + .2
            try:
                saved = json.loads(self.config.read_text(encoding='utf-8'))
                self.percent = validate_percent(saved.get('gpu_budget_percent', 100))
            except (OSError, ValueError, TypeError, AttributeError):
                pass  # Keep the last valid budget during atomic replacement.
        return self.percent

    def rest(self, work):
        """No accumulated debt: increasing the slider also ends a long idle."""
        self.work_seconds += work
        started = self.clock()
        while True:
            percent = self.current_percent()
            remaining = work * (100 / percent - 1) - (self.clock() - started)
            if remaining <= 0:
                break
            self.sleep(min(.05, remaining))
        self.idle_seconds += self.clock() - started

    def call(self, operation, *args, **kwargs):
        # CTranslate2 returns completed results. Synchronize its CUDA device
        # before yielding as well; never sleep with our kernels still queued.
        percent = self.current_percent()
        if percent == 100:
            return operation(*args, **kwargs)
        self.synchronize()
        start = self.clock()
        result = operation(*args, **kwargs)
        self.synchronize()
        self.rest(self.clock() - start)
        return result

    def before_forward(self, module, args):
        depth = getattr(self.local, 'depth', 0)
        if depth == 0:
            self.local.active = self.current_percent() < 100
            if self.local.active:
                self.synchronize()
                self.local.started = self.clock()
        self.local.depth = depth + 1

    def after_forward(self, module, args, output):
        self.local.depth = max(0, getattr(self.local, 'depth', 1) - 1)
        if not getattr(self.local, 'active', False) or output is None:
            return  # Preserve exceptions from the original forward.
        # Check inside large forwards too (encoder, alignment and speakers).
        if self.local.depth and self.clock() - self.local.started < .02:
            return
        self.synchronize()
        self.rest(self.clock() - self.local.started)
        self.local.started = self.clock()


def cuda_budget():
    import torch
    return GpuBudget(config=os.environ.get('VOXDROP_GPU_BUDGET_CONFIG'),
                     synchronize=torch.cuda.synchronize)


@contextmanager
def pace_torch(*models, hardware, budget=None):
    if hardware != 'cuda':
        yield
        return
    budget = budget or cuda_budget()
    handles, seen = [], set()
    try:
        # Instance hooks only: no global Torch changes and no changed tensors,
        # precision, model parameters or transcription boundaries.
        for model in models:
            for module in model.modules():
                if id(module) in seen:
                    continue
                seen.add(id(module))
                handles.append(module.register_forward_pre_hook(budget.before_forward))
                handles.append(module.register_forward_hook(budget.after_forward, always_call=True))
        yield budget
    finally:
        for handle in handles:
            handle.remove()


class PacedWhisper:
    """Delegate the pinned native Whisper API without changing decoding."""
    def __init__(self, model, budget):
        self.model, self.budget = model, budget

    def __getattr__(self, name):
        attribute = getattr(self.model, name)
        if name in ('encode', 'generate', 'align', 'detect_language'):
            return lambda *args, **kwargs: self.budget.call(attribute, *args, **kwargs)
        return attribute


def pace_whisper(transcriber):
    whisper = transcriber._model
    whisper.model = PacedWhisper(whisper.model, cuda_budget())
    return transcriber
