"""Mac-specific regressions for native quit, MLX pacing and model lifetime."""
from contextlib import nullcontext
import gc
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace, ModuleType
import unittest
from unittest.mock import Mock, patch
import weakref

import numpy as np
import qwen_backend
from gpu_budget import GpuBudget, pace_mlx


class MacQwenTests(unittest.TestCase):
    def test_asr_weights_are_gone_before_loading_alignment_and_audio_timeline_is_preserved(self):
        refs = []
        class Model: pass
        def load(path):
            if path.name == qwen_backend.ALIGNER:
                gc.collect()
                self.assertIsNone(refs[0](), 'ASR and aligner weights overlap')
            model = Model(); refs.append(weakref.ref(model)); return model
        mx = SimpleNamespace(gpu='gpu', cpu='cpu', metal=SimpleNamespace(is_available=lambda:True),
            set_default_device=Mock(), synchronize=Mock(), clear_cache=Mock())
        modules = {'mlx':ModuleType('mlx'), 'mlx.core':mx,
                   'mlx_audio':ModuleType('mlx_audio'), 'mlx_audio.stt':SimpleNamespace(load=load),
                   'mlx_audio.stt.models':ModuleType('models'),
                   'mlx_audio.stt.models.qwen3_asr':ModuleType('qwen3_asr'),
                   'mlx_audio.stt.models.qwen3_asr.qwen3_asr':SimpleNamespace(split_audio_into_chunks=Mock())}
        with tempfile.TemporaryDirectory() as temporary, patch.dict(sys.modules, modules), \
             patch.object(qwen_backend, 'WINDOWS', False):
            root=Path(temporary); audio=np.zeros(16000); np.save(root/'audio.npy',audio)
            def recognize(asr, samples, language, split, report, consume):
                consume(samples, 'Text', 'German', 0, len(samples))
            with patch('qwen_backend.recognize_chunks',new=recognize), \
                 patch('qwen_backend.timed_words',return_value=[dict(word='Text',start=0,end=1)]) as timed, \
                 patch('gpu_budget.pace_mlx',new=lambda *a,**k:nullcontext()), patch('qwen_backend.emit'):
                qwen_backend.run(root, root, root/'audio.npy', root/'result.json','metal','de')
            self.assertEqual(timed.call_args.args[2:], ('Text','German',0,16000,16000))
            mx.synchronize.assert_called_once(); mx.clear_cache.assert_called_once()

    def test_mlx_blocks_finish_before_idle_and_restore_their_types_after_failure(self):
        events=[]
        class Block:
            def __call__(self, value):
                events.append('work'); clock[0]+=.04; return value+1
        encoder, layer=Block(),Block()
        model=SimpleNamespace(audio_tower=encoder,model=SimpleNamespace(layers=[layer]))
        clock=[0.]
        def sleep(seconds):events.append('idle');clock[0]+=seconds
        mx=SimpleNamespace(eval=lambda value:events.append('eval'),synchronize=lambda:events.append('sync'))
        budget=GpuBudget(50,clock=lambda:clock[0],sleep=sleep,synchronize=mx.synchronize)
        with patch.dict(sys.modules,{'mlx':ModuleType('mlx'),'mlx.core':mx}):
            with self.assertRaisesRegex(ValueError,'original'):
                with pace_mlx(model,hardware='metal',budget=budget):
                    self.assertEqual(layer(encoder(1)),3)
                    raise ValueError('original')
        self.assertIs(type(encoder),Block);self.assertIs(type(layer),Block)
        self.assertEqual(events[:5],['sync','work','eval','sync','idle'])
        self.assertAlmostEqual(budget.work_seconds,.08)
        self.assertAlmostEqual(budget.idle_seconds,.08)


@unittest.skipUnless(sys.platform=='darwin','Native macOS quit adapter')
class NativeQuitTests(unittest.TestCase):
    def test_native_quit_enters_shutdown_and_only_completed_shutdown_can_exit(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
        # The desktop directory is also a namespace package in the test runner.
        from desktop.desktop import QuitInterceptor
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QApplication
        app=QApplication.instance() or QApplication([])
        controller=Mock(shutdown_complete=False)
        gate=QuitInterceptor(controller,app)
        self.assertTrue(gate.eventFilter(app,QEvent(QEvent.Type.Quit)))
        controller.requestQuit.assert_called_once_with()
        controller.shutdown_complete=True
        self.assertFalse(gate.eventFilter(app,QEvent(QEvent.Type.Quit)))
