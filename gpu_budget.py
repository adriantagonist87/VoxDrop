"""Cooperative GPU work/idle pacing for this app's models, never driver limits."""
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
            if remaining <= 1e-6:
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


def metal_budget(*, synchronize=lambda: None):
    return GpuBudget(config=os.environ.get('VOXDROP_GPU_BUDGET_CONFIG'),
                     synchronize=synchronize)


@contextmanager
def pace_torch(*models, hardware, budget=None):
    if hardware not in ('cuda', 'metal'):
        yield
        return
    if budget is None:
        if hardware == 'metal':
            import torch
            budget = metal_budget(synchronize=torch.mps.synchronize)
        else:
            budget = cuda_budget()
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


def pace_whisper(transcriber, hardware='cuda'):
    whisper = transcriber._model
    # CTranslate2's synchronous Metal calls finish their work before returning.
    whisper.model = PacedWhisper(whisper.model, metal_budget() if hardware == 'metal' else cuda_budget())
    return transcriber


@contextmanager
def pace_mlx(model, *, hardware, budget=None):
    """Pace completed MLX encoder/decoder blocks without changing weights/cache.

    Special methods are resolved on the type. Use temporary per-instance types,
    never monkeypatch the shared MLX classes or alter the module/weight tree.
    """
    if hardware != 'metal':
        yield
        return
    import mlx.core as mx
    budget = budget or metal_budget(synchronize=mx.synchronize)
    internal = getattr(model, '_model', model)
    modules = [internal.audio_tower, *internal.model.layers]
    changed = []
    try:
        for module in modules:
            original = type(module)
            def call(self, *args, _call=original.__call__, **kwargs):
                if budget.current_percent() == 100:
                    return _call(self, *args, **kwargs)
                def completed():
                    result = _call(self, *args, **kwargs)
                    mx.eval(result)
                    return result
                return budget.call(completed)
            paced = type(original.__name__ + 'VoxDropBudget', (original,), {'__call__': call})
            object.__setattr__(module, '__class__', paced)
            changed.append((module, original))
        yield budget
    finally:
        for module, original in reversed(changed):
            object.__setattr__(module, '__class__', original)
