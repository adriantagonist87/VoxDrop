import json
import tempfile
import unittest
from pathlib import Path

import torch

from gpu_budget import GpuBudget, PacedWhisper, pace_torch, validate_percent


class Clock:
    def __init__(self):
        self.now, self.waits, self.syncs = 0., [], 0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds

    def sync(self):
        self.syncs += 1


class GpuBudgetTests(unittest.TestCase):
    def budget(self, percent=50, **kwargs):
        clock = Clock()
        return GpuBudget(percent, clock=clock, sleep=clock.sleep, synchronize=clock.sync, **kwargs), clock

    def test_work_budget_waits_after_completed_work_without_changing_results(self):
        for percent, expected in ((100, 0), (50, .04), (25, .12)):
            with self.subTest(percent=percent):
                budget, clock = self.budget(percent)
                def work():
                    clock.now += .04
                    return ['original result']
                self.assertEqual(budget.call(work), ['original result'])
                self.assertAlmostEqual(sum(clock.waits), expected)
                self.assertLessEqual(max(clock.waits, default=0), .05)
                self.assertEqual(clock.syncs, 0 if percent == 100 else 2)

    def test_live_config_updates_apply_and_invalid_replace_keeps_last_valid_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)/'settings.json'
            config.write_text(json.dumps({'gpu_budget_percent': 50}))
            budget, clock = self.budget(100, config=config)
            self.assertEqual(budget.current_percent(), 50)
            config.write_text('{')
            clock.now += .21
            self.assertEqual(budget.current_percent(), 50)
            config.write_text(json.dumps({'gpu_budget_percent': 100}))
            clock.now += .21
            self.assertEqual(budget.current_percent(), 100)

    def test_increasing_live_budget_ends_long_wait_and_does_not_carry_idle_debt(self):
        budget, clock = self.budget(10)
        def change_during_wait(seconds):
            clock.sleep(seconds)
            budget.percent = 100
        budget.sleep = change_during_wait
        budget.rest(2)
        self.assertAlmostEqual(sum(clock.waits), .05)
        budget.rest(1)
        self.assertEqual(len(clock.waits), 1)

    def test_instance_hooks_pace_nested_models_once_preserve_tensors_and_are_removed(self):
        budget, clock = self.budget()
        class Work(torch.nn.Module):
            def forward(self, value):
                clock.now += .01
                return value + 1
        model = torch.nn.Sequential(Work(), Work(), Work())
        with pace_torch(model, model[0], hardware='cuda', budget=budget):
            self.assertEqual(model(torch.tensor(2)).item(), 5)
        self.assertAlmostEqual(sum(clock.waits), .03)
        self.assertTrue(all(not m._forward_hooks and not m._forward_pre_hooks for m in model.modules()))

    def test_forward_exception_is_preserved_and_cpu_has_no_hooks_or_sync(self):
        budget, clock = self.budget()
        class Broken(torch.nn.Module):
            def forward(self, value):
                raise ValueError('original failure')
        model = Broken()
        with self.assertRaisesRegex(ValueError, 'original failure'):
            with pace_torch(model, hardware='cuda', budget=budget):
                model(torch.tensor(1))
        self.assertFalse(model._forward_hooks)
        self.assertEqual(budget.local.depth, 0)
        with pace_torch(model, hardware='cpu', budget=budget):
            self.assertFalse(model._forward_hooks)

    def test_whisper_proxy_preserves_native_arguments_attributes_and_results(self):
        budget, clock = self.budget()
        class Native:
            device = 'cuda'
            def generate(self, features, **kwargs):
                self.arguments = (features, kwargs)
                clock.now += .03
                return ['decoded']
        model = Native()
        paced = PacedWhisper(model, budget)
        self.assertEqual(paced.generate('features', beam_size=5), ['decoded'])
        self.assertEqual(model.arguments, ('features', {'beam_size': 5}))
        self.assertEqual(paced.device, 'cuda')
        self.assertAlmostEqual(sum(clock.waits), .03)

    def test_invalid_limits_do_not_silently_disable_pacing(self):
        for value in (None, True, '50', 0, 9, 101, 50.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_percent(value)
