import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Dialog {
    id: dialog
    required property var api
    readonly property var plan: api.dropPlan
    readonly property var counts: plan.counts || {}
    readonly property bool finished: Boolean(plan.resolved)
    readonly property int actionable: (counts.new || 0) + (counts.queued || 0) + (counts.done || 0) + (counts.existing || 0) + (counts.problem || 0)
    readonly property var rows: (plan.items || []).concat((plan.warnings || []).map(text => ({source: text, status: 'Nicht lesbar / übersprungen', kind: 'problem'})))
    objectName: 'dropConflictDialog'
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(680, parent.width - 40)
    height: Math.min(640, parent.height - 40)
    title: finished ? 'Ergebnis des Drops' : 'Abgelegte Aufnahmen prüfen'
    modal: true
    closePolicy: api.state.busy ? Popup.NoAutoClose : Popup.CloseOnEscape
    onRejected: api.dismissDrop()
    background: Rectangle { radius: 8; color: '#292929'; border.color: '#454545' }

    component Decision: Button {
        id: decision
        Layout.fillWidth: true
        implicitHeight: 32
        font.pixelSize: 12
        contentItem: Text { text: decision.text; font: decision.font; color: decision.enabled ? '#ededee' : '#888'; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: 5; color: decision.down ? '#456653' : decision.hovered ? '#353535' : '#242424'; border.color: decision.activeFocus ? '#8ac6a5' : '#454545' }
    }
    contentItem: ColumnLayout {
        spacing: 8
        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: '#ededee'
            text: dialog.finished ? (dialog.plan.message || '') :
                'Neu: ' + (dialog.counts.new || 0) + ' · Bereits wartend: ' + (dialog.counts.queued || 0) +
                ' · Gerade aktiv: ' + (dialog.counts.active || 0) + '\nBereits transkribiert: ' + (dialog.counts.done || 0) +
                ' · TXT vorhanden: ' + (dialog.counts.existing || 0) + ' · Fehlgeschlagen/abgebrochen: ' + (dialog.counts.problem || 0)
        }
        Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; color: '#c4c4c8'; visible: !dialog.finished; text: 'Die Auswahl gilt für den gesamten Drop. Überlappende Ordner und mehrfach abgelegte Dateien werden zusammengefasst. Originale und bestehende TXT bleiben erhalten.' }
        Label { Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; color: '#ffb4ad'; text: dialog.plan.error || ''; visible: text.length > 0 }
        Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; color: '#d9bd83'; text: dialog.plan.notice || ''; visible: text.length > 0 }
        ListView {
            objectName: 'dropConflictList'
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 5
            model: dialog.rows
            ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                required property var modelData
                width: ListView.view.width - 12
                implicitHeight: info.implicitHeight + 16
                radius: 5
                color: '#242424'
                border.color: '#3b3b3b'
                ColumnLayout {
                    id: info
                    x: 8; y: 8; width: parent.width - 16
                    Label { Layout.fillWidth: true; text: modelData.status; color: modelData.kind === 'problem' ? '#ffb4ad' : '#8ac6a5'; font.bold: true }
                    Label { Layout.fillWidth: true; text: modelData.source; color: '#ededee'; wrapMode: Text.WrapAnywhere; maximumLineCount: 3; elide: Text.ElideMiddle }
                }
            }
        }
    }
    footer: ColumnLayout {
        spacing: 7
        Label {
            Layout.fillWidth: true
            Layout.leftMargin: 12; Layout.rightMargin: 12
            visible: !dialog.finished
            font.pixelSize: 11
            color: '#c4c4c8'
            wrapMode: Text.WordWrap
            text: 'An 1. Stelle: Wartende/neue Aufträge vorziehen, fertige ignorieren. Neu transkribieren: separate TXT erzeugen. Sofort: Auswahl vorziehen und laufende Berechnung kontrolliert unterbrechen; der unterbrochene Auftrag beginnt anschließend neu. Ein begonnener Export wird fertiggestellt. Bei pausierter Queue bleibt der Rest pausiert. Ignorieren: nur neue Aufnahmen einreihen.'
        }
        GridLayout {
            Layout.fillWidth: true
            Layout.margins: 12
            columns: 2
            visible: !dialog.finished
            Decision { objectName: 'dropFrontButton'; text: 'An 1. Stelle einreihen'; enabled: !dialog.api.state.busy && (dialog.counts.new || 0) + (dialog.counts.queued || 0) + (dialog.counts.problem || 0) > 0; onClicked: dialog.api.resolveDrop('front') }
            Decision { objectName: 'dropRetranscribeButton'; text: 'Neu transkribieren'; enabled: !dialog.api.state.busy && dialog.actionable > 0; onClicked: dialog.api.resolveDrop('retranscribe') }
            Decision { objectName: 'dropImmediateButton'; text: 'Sofort transkribieren'; enabled: !dialog.api.state.busy && dialog.actionable > 0; onClicked: dialog.api.resolveDrop('immediate') }
            Decision { objectName: 'dropIgnoreButton'; text: 'Bereits erfasste ignorieren'; enabled: !dialog.api.state.busy; onClicked: dialog.api.resolveDrop('ignore') }
        }
        Decision {
            Layout.leftMargin: 12; Layout.rightMargin: 12; Layout.bottomMargin: 12
            text: dialog.finished ? 'Schließen' : 'Gesamten Drop verwerfen'
            enabled: !dialog.api.state.busy
            onClicked: dialog.api.dismissDrop()
        }
    }
}
