import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QObject, Qt, QUrl, QPoint, QPointF
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from desktop.window_state import WindowPresenter

DESKTOP = Path(__file__).resolve().parents[1] / "desktop"


class DesktopWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        QQuickStyle.setStyle("Basic")
        sys.path.insert(0, str(DESKTOP))
        import controller
        cls.controller_module = controller

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.enterContext(patch.object(self.controller_module, "PROFILE", Path(directory.name)))
        self.enterContext(patch.object(self.controller_module, "MODEL_DATA", Path(directory.name) / "data"))
        self.controller = self.controller_module.Controller(preview=True)
        self.engine = QQmlApplicationEngine()
        self.engine.setInitialProperties({"api": self.controller})
        self.engine.load(QUrl.fromLocalFile(str(DESKTOP / "qml/Main.qml")))
        self.assertTrue(self.engine.rootObjects())
        self.window = self.engine.rootObjects()[0]
        self.presenter = WindowPresenter(self.window)
        self.addCleanup(self.window.close)

    def test_full_qml_fullscreen_survives_minimization_and_native_activation(self):
        self.presenter.show()
        QTest.qWait(300)
        self.window.showFullScreen()
        QTest.qWait(300)
        self.window.showMinimized()
        QTest.qWait(300)
        self.presenter.show()
        QTest.qWait(300)
        self.assertEqual(self.window.windowState(), Qt.WindowState.WindowFullScreen)
        self.assertTrue(self.window.isVisible())

    def test_network_wait_offers_cancel_and_recursive_mode_locks_archive_option(self):
        self.presenter.show()
        self.controller.downloading = True
        self.controller.network_permission_changed(True)
        self.controller.setSetting("include_subfolders", True)
        QTest.qWait(50)
        cancel = self.window.findChild(QObject, "cancelNetworkWait")
        self.assertTrue(cancel.property("visible"))
        self.assertTrue(cancel.property("enabled"))
        self.assertFalse(self.window.findChild(QObject, "createOutputSubfolder").property("enabled"))
        self.controller.cancelNetworkWait()
        self.assertTrue(self.controller.network_cancel.is_set())
        self.controller.network_permission_changed(False)
        QTest.qWait(50)
        self.assertFalse(cancel.property("visible"))

    def queue_fixture(self,count=3):
        jobs=[dict(id=i,source=str(self.controller_module.PROFILE/f'Aufnahme {i} mit langem Namen.wav'),
            completed_dir=str(self.controller_module.PROFILE),size=123456,mtime_ns=1,
            state='ready',detected=100,updated=100,started=None,finished=None,error=None,
            origin_job_id=None,settings=json.dumps(self.controller_module.DEFAULTS)) for i in range(1,count+1)]
        self.controller.snapshot=dict(queue=jobs,jobs=[],waiting=count,current=None,queue_paused=False)
        self.controller.update_queue();self.controller.changed.emit()
        self.presenter.show();QTest.qWait(200)
        return jobs

    def visual(self,name):
        def visit(item):
            if item.objectName()==name:return item
            for child in item.childItems():
                found=visit(child)
                if found:return found
            return None
        return visit(self.window.contentItem())

    def test_queue_is_visible_and_not_limited_to_250_history_rows(self):
        jobs=self.queue_fixture(301)
        view=self.window.findChild(QObject,'queueList')
        self.assertEqual(view.property('count'),301)
        self.assertEqual(len(self.controller.queue),301)
        self.assertTrue(view.property('visible'))
        self.assertIsNotNone(self.visual('removeQueue1'))
        self.controller.showDetails(jobs[-1]['id'])
        self.assertEqual(self.controller.selected['id'],301)

    def test_real_qml_drag_emits_persistent_move_command(self):
        self.queue_fixture(3)
        handle=self.visual('queueDragHandle1');target=self.visual('queueRow2')
        self.assertIsNotNone(handle);self.assertIsNotNone(target)
        start=handle.mapToScene(QPointF(14,15)).toPoint()
        end=target.mapToScene(QPointF(20,target.height()-8)).toPoint()
        with patch.object(self.controller_module,'command',return_value='') as command, patch.object(self.controller,'action',side_effect=lambda operation,message:operation()):
            QTest.mousePress(self.window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,start)
            for step in range(1,13):
                point=QPoint(start.x(),round(start.y()+(end.y()-start.y())*step/12))
                QTest.mouseMove(self.window,point,30)
            QTest.mouseRelease(self.window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,end)
            QTest.qWait(50)
        command.assert_called_once_with('move-queue',1,3)
        self.assertFalse(self.controller.queue_dragging)

    def test_programmatic_folder_edit_updates_saved_draft(self):
        self.controller.paths=[str(self.controller_module.PROFILE/'old')]
        self.controller.foldersChanged.emit();QTest.qWait(50)
        field=self.visual('folderField0')
        self.assertIsNotNone(field)
        new=str(self.controller_module.PROFILE/'new')
        field.setProperty('text',new)
        QTest.qWait(20)
        self.assertEqual(self.controller.config()['folders'],[new])

    def test_open_transcript_uses_local_file_url_with_os_default_application(self):
        jobs=self.queue_fixture(1);job=jobs[0];job['state']='done'
        path=Path(job['source']).with_suffix('.txt');path.write_text('Synthetic transcript',encoding='utf-8')
        self.controller.selected=job
        with patch.object(self.controller_module.QDesktopServices,'openUrl',return_value=True) as opened, patch.object(self.controller,'submit',side_effect=lambda operation,callback:callback(operation(),None)):
            self.controller.openTranscript()
        opened.assert_called_once_with(QUrl.fromLocalFile(str(path)))
        self.assertTrue(self.controller.detail['openTranscript'])

    def test_imported_results_do_not_claim_a_model_or_new_inference(self):
        job=self.queue_fixture(1)[0]
        job.update(state='existing',result_kind='existing')
        self.controller.selected=job
        rows={row['label']:row['value'] for row in self.controller.detail['rows']}
        self.assertEqual(rows['Modell verwendet'],'Nicht bekannt (Bestandsdatei)')
        self.assertEqual(rows['Dauer Spracherkennung'],'Nicht erneut ausgeführt')
        self.assertEqual(rows['Verfahren der Sprecherzuordnung'],'Nicht neu bestimmt')
        self.assertEqual(rows['Rechengerät'],'Keine neue Inferenz')
        for kind in ('reused','duplicate'):
            job['result_kind']=kind
            rows={row['label']:row['value'] for row in self.controller.detail['rows']}
            self.assertEqual(rows['Modell verwendet'],'Siehe Ursprungsauftrag')
