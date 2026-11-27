import subprocess
import unittest
from datetime import datetime
from unittest.mock import patch
from xml.etree import ElementTree as ET

import platform_io as io


class GraphicsReportTests(unittest.TestCase):
    before = "2026-10-05T04:11:13.8184270Z"
    after = "2026-11-22T00:44:17.1723456Z"
    start = datetime.fromisoformat("2026-11-22T00:24:00+00:00").timestamp()
    old_id = "11111111-1111-1111-1111-111111111111"
    new_id = "22222222-2222-2222-2222-222222222222"

    def setUp(self):
        self.enterContext(patch.object(io, "WINDOWS", True))
        self.enterContext(patch("time.time", return_value=self.start + 1250))
        io._first_wer_time.cache_clear()
        self.addCleanup(io._first_wer_time.cache_clear)

    def event(self, number=1001, report_id="", dump="", stamp=None, code="141"):
        root = ET.Element(io.EVENT_NS + "Event")
        system = ET.SubElement(root, io.EVENT_NS + "System")
        ET.SubElement(system, io.EVENT_NS + "EventID").text = str(number)
        ET.SubElement(system, io.EVENT_NS + "TimeCreated", SystemTime=stamp or self.after)
        payload = ET.SubElement(root, io.EVENT_NS + "EventData")
        for key, value in (("ReportId", report_id), ("AttachedFiles", dump), ("P1",code)):
            ET.SubElement(payload, io.EVENT_NS + "Data", Name=key).text = value
        return root

    def test_historical_dump_and_reissued_undated_report_do_not_stop_worker(self):
        reports = [self.event(report_id=self.new_id, dump=r"C:\Windows\WATCHDOG-20261030-1450.dmp"),
                   self.event(report_id=self.old_id)]
        with patch.object(io, "_windows_events", side_effect=[
            [], reports, [self.event(stamp=self.before)], [], reports
        ]) as query:
            self.assertIsNone(io.graphics_timeout_since(self.start))
            self.assertIsNone(io.graphics_timeout_since(self.start))
        self.assertEqual(query.call_args_list[2].kwargs, {"oldest": True, "one": True})
        self.assertIn(self.old_id, query.call_args_list[2].args[1])
        self.assertEqual(query.call_count, 5)

    def test_current_report_behind_replays_is_detected(self):
        reports = [self.event(report_id=self.old_id), self.event(report_id=self.new_id)]
        with patch.object(io, "_windows_events", side_effect=[
            [], reports, [self.event(stamp=self.before)], [self.event(stamp=self.after)]
        ]):
            self.assertIn("141/117", io.graphics_timeout_since(self.start))

    def test_failure_to_read_one_report_does_not_hide_later_report(self):
        reports = [self.event(report_id="'"), self.event(report_id=self.old_id), self.event(report_id=self.new_id)]
        with patch.object(io, "_windows_events", side_effect=[
            [], reports, subprocess.TimeoutExpired("wevtutil", 2), [self.event(stamp=self.after)]
        ]):
            self.assertIn("141/117", io.graphics_timeout_since(self.start))

    def test_current_graphics_live_dump_193_is_detected_without_calling_it_a_bugcheck(self):
        report=self.event(report_id=self.new_id,code='193')
        with patch.object(io,'_windows_events',side_effect=[[],[report],[self.event(stamp=self.after)]]) as query:
            self.assertEqual(io.graphics_timeout_since(self.start),'Grafik-Watchdog (Windows-Fehlerbericht 193)')
        self.assertIn("Data[@Name='P1']='193'",query.call_args_list[1].args[1])

    def test_replayed_193_reports_still_require_current_dump_and_first_submission(self):
        reports=[self.event(report_id=self.new_id,code='193',dump=r'C:\Windows\WATCHDOG-20261030-1450.dmp'),
                 self.event(report_id=self.old_id,code='193')]
        with patch.object(io,'_windows_events',side_effect=[[],reports,[self.event(stamp=self.before)]]):
            self.assertIsNone(io.graphics_timeout_since(self.start))

    def test_direct_driver_events_remain_effective_in_long_running_job(self):
        for number in (153, 4101):
            with self.subTest(number=number), patch.object(io, "_windows_events",
                    return_value=[self.event(number)]) as query:
                self.assertIn(str(number), io.graphics_timeout_since(self.start - 72*3600))
                self.assertEqual(query.call_count, 1)
                self.assertEqual(query.call_args.args[0], "System")
                self.assertIn("2026-11-20T00:44:50", query.call_args.args[1])

    def test_real_wevtutil_output_framing_and_order_options(self):
        wrapped = ET.Element("Events")
        wrapped.append(self.event(report_id=self.old_id, stamp=self.before))
        result = subprocess.CompletedProcess([], 0, ET.tostring(wrapped, encoding="utf-16"))
        with patch.object(io, "process_options", return_value={}), patch("subprocess.run", return_value=result) as run:
            self.assertLess(io._first_wer_time(self.old_id), self.start)
        command = run.call_args.args[0]
        for option in ("/rd:false", "/c:1", "/e:Events", "/uni:true"):
            self.assertIn(option, command)
