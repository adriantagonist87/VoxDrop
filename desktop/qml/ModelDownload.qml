import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Frame {
    id: panel
    required property QtObject api
    required property var status
    required property bool downloading
    required property bool checking
    property bool expanded: false
    component DownloadBar: ProgressBar {
        id: progress
        implicitHeight: 8
        padding: 0
        background: Rectangle { color: "#3b403d"; radius: 3 }
        contentItem: Item {
            clip: true
            Rectangle {
                id: fill
                width: parent.width * (progress.indeterminate ? 0.28 : progress.visualPosition)
                height: parent.height
                radius: 3
                color: "#8ac6a5"
                NumberAnimation on x {
                    running: progress.visible && progress.indeterminate
                    from: -fill.width; to: progress.availableWidth
                    duration: 1450; loops: Animation.Infinite
                }
            }
        }
        onIndeterminateChanged: { if (!indeterminate) fill.x = 0 }
    }
    padding: 10
    background: Rectangle { color: "#202322"; radius: 6; border.color: "#3b403d" }
    contentItem: ColumnLayout {
        spacing: 7
        Label {
            objectName: "modelDownloadPhase"
            visible: panel.status.phase !== "idle"
            text: panel.status.message
            color: panel.status.error ? "#e8ae8e" : "#ededed"
            wrapMode: Text.Wrap; Layout.fillWidth: true
        }
        DownloadBar {
            objectName: "modelDownloadProgress"
            Layout.fillWidth: true
            visible: panel.downloading || panel.status.hasProgress
            indeterminate: panel.status.fraction === null || panel.status.fraction === undefined
            value: panel.status.fraction || 0
        }
        Label {
            objectName: "modelDownloadSummary"
            visible: panel.downloading || panel.status.hasProgress
            text: panel.status.summary
            color: "#ededed"; wrapMode: Text.Wrap; Layout.fillWidth: true
        }
        Label {
            objectName: "modelDownloadRate"
            visible: panel.downloading || panel.status.hasProgress
            text: "Download: " + panel.status.rate + " · " + panel.status.network
            color: "#aab0ad"; wrapMode: Text.Wrap; Layout.fillWidth: true
        }
        Label {
            objectName: "modelDownloadCurrent"
            text: panel.status.current || ""
            visible: text.length > 0
            color: "#aab0ad"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true
        }
        Label {
            text: panel.status.waiting || ""
            visible: text.length > 0
            color: "#e8ae8e"; Layout.fillWidth: true; wrapMode: Text.Wrap
        }
        Button {
            objectName: "modelDownloadFilesButton"
            text: (panel.expanded ? "Dateien ausblenden" : "Dateien anzeigen") + " (" + panel.status.files.length + ")"
            visible: panel.status.hasProgress
            onClicked: panel.expanded = !panel.expanded
        }
        ScrollView {
            id: filesScroll
            visible: panel.expanded && panel.status.hasProgress
            Layout.fillWidth: true; Layout.preferredHeight: 200
            contentWidth: availableWidth
            ColumnLayout {
                width: filesScroll.availableWidth
                Repeater {
                    model: panel.status.files
                    delegate: ColumnLayout {
                        required property var modelData
                        required property int index
                        objectName: "modelDownloadFile" + index
                        Layout.fillWidth: true; spacing: 3
                        Label { text: modelData.model + " / " + modelData.name; color: "#ededed"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
                        Label { text: modelData.amount + " · " + modelData.status; color: "#aab0ad"; wrapMode: Text.Wrap; Layout.fillWidth: true }
                        DownloadBar { Layout.fillWidth: true; value: modelData.fraction || 0; indeterminate: modelData.fraction === null || modelData.fraction === undefined }
                    }
                }
            }
        }
        Label { text: "Modellserver"; color: "#ededed"; font.bold: true }
        Label {
            objectName: "modelServerUnchecked"
            text: "Noch nicht von diesem PC geprüft."
            visible: panel.status.servers.length === 0
            color: "#aab0ad"; wrapMode: Text.Wrap; Layout.fillWidth: true
        }
        Repeater {
            model: panel.status.servers
            delegate: Label {
                required property var modelData
                text: modelData.text + (modelData.checked ? " · " + modelData.checked : "") +
                      (modelData.latency ? " · " + modelData.latency : "")
                color: modelData.error ? "#e8ae8e" : "#aab0ad"
                wrapMode: Text.Wrap; Layout.fillWidth: true
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Button {
                objectName: "checkModelServerButton"
                text: panel.checking ? "Prüfung abbrechen" : "Server prüfen"
                enabled: panel.api.state.ready && (!panel.api.state.busy || panel.downloading)
                onClicked: panel.checking ? panel.api.cancelModelServerCheck() : panel.api.checkModelServer()
            }
            Button {
                objectName: "cancelModelDownloadButton"
                text: "Download abbrechen"
                visible: panel.downloading && !panel.api.state.waitingForNetwork
                onClicked: panel.api.cancelNetworkWait()
            }
        }
    }
}
