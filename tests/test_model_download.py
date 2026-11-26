import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from model_download import DownloadReport,ModelSpec,error_detail,inspect_server
from desktop.download_status import present,parse_event,merge_servers


class ModelDownloadTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.spec=ModelSpec('model','test/repo','pinned',('weights.bin',),self.root)
        self.now=0.
        self.events=[]
        self.report=DownloadReport([self.spec],self.events.append,clock=lambda:self.now)

    def test_remote_size_is_exact_and_unknown_size_is_not_a_percentage(self):
        api=Mock()
        api.model_info.return_value=SimpleNamespace(siblings=[SimpleNamespace(rfilename='weights.bin',size=100)])
        self.report.prepare(api=api)
        self.assertEqual(self.report.snapshot()['bytesTotal'],100)
        self.report.position('model','weights.bin',25,100)
        self.assertEqual(self.report.snapshot()['fraction'],.25)
        report=DownloadReport([self.spec],Mock())
        api.model_info.side_effect=OSError('DNS failed')
        report.prepare(api=api)
        self.assertIsNone(report.snapshot()['fraction'])
        self.assertEqual(report.snapshot()['servers'][0]['state'],'unconfirmed')

    def test_resume_credit_and_cache_do_not_inflate_current_network_speed(self):
        self.report.phase_changed('downloading','Download')
        self.report.position('model','weights.bin',40,100)
        self.assertEqual(self.report.snapshot()['networkTransferred'],0)
        self.now=1
        self.report.position('model','weights.bin',50,100)
        self.report.transfer(10,'model','weights.bin')
        result=self.report.snapshot()
        self.assertEqual((result['bytesCompleted'],result['bytesPerSecond']),(50,10))
        self.now=5
        self.assertEqual(self.report.snapshot()['bytesPerSecond'],0)
        self.assertEqual(self.report.snapshot()['fraction'],.5)

    def test_resume_rollback_changes_file_position_without_negative_transfer(self):
        self.report.phase_changed('downloading','Download')
        bar=self.report.bar_class('model','weights.bin')(total=100,initial=40)
        self.addCleanup(bar.close)
        bar.update(20);bar.update_transfer(20)
        self.assertEqual(self.report.snapshot()['bytesCompleted'],60)
        bar.update(-40);bar.update_transfer(-40)
        self.assertEqual(self.report.snapshot()['bytesCompleted'],20)
        self.assertEqual(self.report.snapshot()['networkTransferred'],20)

    def test_xet_reconstruction_and_transfer_are_separate_counters(self):
        from huggingface_hub.utils._xet_progress_reporting import XetDownloadProgressReporter
        self.report.phase_changed('downloading','Download')
        with XetDownloadProgressReporter(reconstruction_desc='weights',total=100,log_level=20,
            name='test.xet',tqdm_class=self.report.bar_class('model','weights.bin')) as progress:
            progress.update_progress(SimpleNamespace(total_bytes_completed=80,total_transfer_bytes_completed=25,
                total_bytes=100,total_bytes_completion_rate=80,total_transfer_bytes_completion_rate=25))
        result=self.report.snapshot()
        self.assertEqual(result['bytesCompleted'],80)
        self.assertEqual(result['networkTransferred'],25)

    def test_downloaded_bytes_are_not_reported_as_verified_model(self):
        path=self.root/'weights.bin';path.write_bytes(bytes(100))
        self.report.completed_file('model','weights.bin',path,transferred=False)
        self.assertTrue(self.report.snapshot()['files'][0]['cached'])
        self.assertEqual(self.report.snapshot()['fraction'],1)
        self.assertNotEqual(self.report.snapshot()['files'][0]['status'],'verified')
        self.report.verifying('model')
        self.assertEqual(self.report.snapshot()['bytesPerSecond'],0)
        self.report.verified('model')
        self.assertEqual(self.report.snapshot()['files'][0]['status'],'verified')
        self.assertNotEqual(self.report.snapshot()['phase'],'complete')

    def test_complete_local_setup_does_not_require_server_access(self):
        (self.root/'weights.bin').write_bytes(bytes(100))
        api=Mock(side_effect=AssertionError('must stay offline'))
        self.report.prepare(api=api)
        api.model_info.assert_not_called()
        self.assertIsNone(self.report.snapshot()['fraction'])
        self.report.verified('model')
        self.assertEqual(self.report.snapshot()['bytesTotal'],100)

    def test_error_messages_do_not_expose_signed_query_or_claim_server_outage(self):
        error=RuntimeError('Failed https://cdn.example/weights?secret=private')
        self.assertNotIn('private',error_detail(error))
        denied=OSError('Socket access denied');denied.winerror=10013
        wrapped=RuntimeError('connection failed');wrapped.__cause__=denied
        self.assertIn('Lokaler Netzwerkzugriff',error_detail(wrapped))

    def test_server_check_probes_weights_and_actual_file_route(self):
        import httpx
        response=Mock(url=SimpleNamespace(host='cdn.example'))
        response.iter_raw.return_value=iter([b'x'])
        client=Mock()
        client.stream.return_value.__enter__=Mock(return_value=response)
        client.stream.return_value.__exit__=Mock(return_value=False)
        events=[]
        with patch('huggingface_hub.get_hf_file_metadata',return_value=SimpleNamespace(location='https://cdn.example/file?sig=private',size=100)), \
             patch.object(httpx,'Client') as constructor:
            constructor.return_value.__enter__.return_value=client
            inspect_server(self.spec,events.append)
        self.assertEqual([event['state'] for event in events],['checking','reachable','checking','reachable'])
        self.assertEqual(events[-1]['host'],'cdn.example')
        self.assertNotIn('private',json.dumps(events))
        self.assertEqual(client.stream.call_args.kwargs['headers']['Range'],'bytes=0-0')

    def test_event_parser_and_server_merge_reject_stale_results(self):
        self.assertIsNone(parse_event('Traceback: broken'))
        self.assertIsNone(parse_event('voxdrop-download:{bad'))
        self.assertIsNone(parse_event('voxdrop-download:[]'))
        self.assertEqual(parse_event('voxdrop-download:{"phase":"complete"}'),{'phase':'complete'})
        newest=dict(id='api',checkedAt=20,state='reachable')
        old=dict(id='api',checkedAt=10,state='unconfirmed')
        self.assertEqual(merge_servers([newest],[old]),[newest])

    def test_failed_api_check_replaces_previous_file_reachability(self):
        events=[]
        with patch('huggingface_hub.get_hf_file_metadata',side_effect=OSError('DNS failed')):
            inspect_server(self.spec,events.append)
        self.assertEqual(events[-1]['role'],'files')
        self.assertEqual(events[-1]['state'],'unconfirmed')

    def test_presentation_has_real_fraction_and_no_stale_speed_during_verification(self):
        self.report.position('model','weights.bin',25,100)
        result=present(self.report.snapshot())
        self.assertEqual(result['fraction'],.25)
        self.assertIn('25%',result['summary'])
        self.report.verifying('model')
        self.assertEqual(present(self.report.snapshot())['rate'],'Kein laufender Transfer')

    def test_downloader_hooks_and_chunk_size_are_restored_after_failure(self):
        import importlib
        import huggingface_hub as hub
        from huggingface_hub import constants
        resources=importlib.import_module('aTrain_core.load_resources')
        snapshots=importlib.import_module('huggingface_hub._snapshot_download')
        before=(hub.snapshot_download,resources.snapshot_download,snapshots.hf_hub_download,constants.DOWNLOAD_CHUNK_SIZE)
        with self.assertRaisesRegex(RuntimeError,'fixture'):
            with self.report.track_hub():
                self.assertEqual(constants.DOWNLOAD_CHUNK_SIZE,65536)
                self.assertIsNot(hub.snapshot_download,before[0])
                raise RuntimeError('fixture')
        self.assertEqual(before,(hub.snapshot_download,resources.snapshot_download,snapshots.hf_hub_download,constants.DOWNLOAD_CHUNK_SIZE))
        self.assertTrue(self.report.stop.is_set())
