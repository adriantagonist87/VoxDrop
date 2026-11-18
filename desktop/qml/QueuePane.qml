import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: pane
    required property var api
    required property var viewState
    property var items: api.queueItems
    property bool dragging: false
    property real dragY: -1
    spacing: 8

    component QueueButton: Button {
        padding: 7
        font.pixelSize: 12
        palette.buttonText: "#e8e8e8"
        contentItem: Text { text: parent.text; font: parent.font; color: parent.enabled ? "#e8e8e8" : "#777"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: 5; color: parent.down ? "#456653" : parent.hovered ? "#383838" : "#282828"; border.color: "#454545" }
    }

    RowLayout {
        Layout.fillWidth: true
        Text { text: "Warteschlange (" + pane.items.length + ")"; color: "#ededed"; font.pixelSize: 17; font.bold: true; Layout.fillWidth: true }
        QueueButton {
            objectName: "pauseQueueButton"
            text: pane.viewState.queuePaused ? "Fortsetzen" : "Pausieren"
            enabled: !pane.viewState.busy
            onClicked: pane.api.pauseQueue(!pane.viewState.queuePaused)
        }
    }
    RowLayout {
        Layout.fillWidth: true
        QueueButton {
            objectName: "cancelQueueButton"
            text: "Alle abbrechen …"
            enabled: !pane.viewState.busy && (pane.items.length > 0 || Boolean(pane.viewState.current.name))
            onClicked: confirmCancelQueue.open()
        }
        Text { text: "Am Griff ziehen oder Reihenfolge im Menü ändern"; color: "#ababab"; font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    }
    Text {
        Layout.fillWidth: true
        visible: pane.viewState.queuePaused
        text: "Pausiert. Der aktuelle Auftrag darf fertiglaufen. Neue Dateien werden weiter erfasst."
        wrapMode: Text.WordWrap; color: "#d9bd83"; font.pixelSize: 12
    }
    Text {
        Layout.fillWidth: true
        visible: pane.items.length === 0
        text: "Keine Aufträge in der Warteschlange."
        color: "#ababab"; font.pixelSize: 13
    }
    ListView {
        id: queueList
        objectName: "queueList"
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 100
        clip: true
        spacing: 7
        model: pane.items
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}
        delegate: Item {
            id: row
            required property var modelData
            required property int index
            objectName: "queueRow" + modelData.id
            width: queueList.width - 12
            height: contents.implicitHeight + 20
            Rectangle { anchors.fill: parent; radius: 7; color: "#242424"; border.color: drop.containsDrag ? "#8dc5ac" : "#3a3a3a"; opacity: dragMouse.drag.active ? .55 : 1 }
            Rectangle {
                id: token
                objectName: "queueDrag" + row.modelData.id
                x: 8; y: 9; width: 28; height: 30; radius: 5
                color: dragMouse.drag.active ? "#456653" : "#333"
                z: 10
                Drag.active: dragMouse.drag.active
                Drag.source: row
                Drag.keys: ["voxdrop-queue"]
                Drag.supportedActions: Qt.MoveAction
                Drag.hotSpot.x: width / 2
                Drag.hotSpot.y: height / 2
                Column { anchors.centerIn: parent; spacing: 3; Repeater { model: 3; Rectangle { width: 12; height: 2; color: "#c8dfd3" } } }
                states: State {
                    when: dragMouse.drag.active
                    ParentChange { target: token; parent: Overlay.overlay }
                }
            }
            MouseArea {
                id: dragMouse
                objectName: "queueDragHandle" + row.modelData.id
                x: 8; y: 9; width: 28; height: 30
                enabled: !pane.viewState.busy
                cursorShape: Qt.OpenHandCursor
                drag.target: token
                drag.axis: Drag.YAxis
                preventStealing: true
                onPressed: { pane.dragging = true; pane.api.setQueueDragging(true) }
                onReleased: { token.Drag.drop(); pane.dragging = false; pane.api.setQueueDragging(false); token.x = 8; token.y = 9 }
                onCanceled: { token.Drag.cancel(); pane.dragging = false; pane.api.setQueueDragging(false); token.x = 8; token.y = 9 }
            }
            ColumnLayout {
                id: contents
                x: 44; y: 9; width: Math.max(1, row.width - 54)
                spacing: 5
                Text { Layout.fillWidth: true; text: (row.index + 1) + ".  " + row.modelData.name; font.bold: true; font.pixelSize: 13; color: "#ededed"; wrapMode: Text.WrapAnywhere; maximumLineCount: 2; elide: Text.ElideRight }
                Text { Layout.fillWidth: true; text: row.modelData.path; color: "#a9a9a9"; font.pixelSize: 11; elide: Text.ElideMiddle }
                Text { Layout.fillWidth: true; text: row.modelData.status + " · " + row.modelData.size + " · Dauer " + row.modelData.audio; color: "#c8dfd3"; font.pixelSize: 11; wrapMode: Text.WordWrap }
                Text { Layout.fillWidth: true; text: row.modelData.model + " · " + row.modelData.language + " · " + row.modelData.hardware; color: "#bcbcbc"; font.pixelSize: 11; wrapMode: Text.WordWrap }
                Text { Layout.fillWidth: true; text: "Eingereiht " + row.modelData.added + (row.modelData.retryAt ? " · Wiederholung " + row.modelData.retryAt : "") + (row.modelData.options ? " · " + row.modelData.options : ""); color: "#aaa"; font.pixelSize: 11; wrapMode: Text.WordWrap }
                RowLayout {
                    Layout.fillWidth: true; spacing: 4
                    QueueButton { text: "Reihenfolge"; enabled: !pane.viewState.busy; Accessible.name: "Reihenfolge ändern: " + row.modelData.name; onClicked: moveMenu.open() }
                    QueueButton { text: "Details"; enabled: !pane.viewState.busy; onClicked: pane.api.showDetails(row.modelData.id) }
                    Item { Layout.fillWidth: true }
                    QueueButton { objectName: "removeQueue" + row.modelData.id; text: "Entfernen"; enabled: !pane.viewState.busy; Accessible.name: "Aus Warteschlange entfernen: " + row.modelData.name; onClicked: pane.api.cancelJob(row.modelData.id) }
                }
            }
            Menu {
                id: moveMenu
                MenuItem { text: "Als Nächstes"; enabled: row.index > 0; onTriggered: pane.api.moveQueueItem(row.modelData.id, pane.items[0].id) }
                MenuItem { text: "Einen Platz nach oben"; enabled: row.index > 0; onTriggered: pane.api.moveQueueItem(row.modelData.id, pane.items[row.index - 1].id) }
                MenuItem { text: "Einen Platz nach unten"; enabled: row.index + 1 < pane.items.length; onTriggered: pane.api.moveQueueItem(row.modelData.id, row.index + 2 < pane.items.length ? pane.items[row.index + 2].id : 0) }
                MenuItem { text: "Ans Ende"; enabled: row.index + 1 < pane.items.length; onTriggered: pane.api.moveQueueItem(row.modelData.id, 0) }
            }
            DropArea {
                id: drop
                anchors.fill: parent
                keys: ["voxdrop-queue"]
                onPositionChanged: drag => { pane.dragY = row.mapToItem(queueList, 0, drag.y).y }
                onDropped: event => {
                    if (!event.source || event.source.modelData.id === row.modelData.id) return
                    var after = event.y > height / 2
                    var before = after ? (row.index + 1 < pane.items.length ? pane.items[row.index + 1].id : 0) : row.modelData.id
                    pane.api.moveQueueItem(event.source.modelData.id, before)
                    event.accept(Qt.MoveAction)
                }
                Rectangle { anchors.left: parent.left; anchors.right: parent.right; height: 3; color: "#8dc5ac"; visible: drop.containsDrag; y: drop.drag.y > parent.height / 2 ? parent.height - height : 0 }
            }
        }
        Timer {
            interval: 40; repeat: true; running: pane.dragging
            onTriggered: {
                var delta = pane.dragY < 35 ? -12 : pane.dragY > queueList.height - 35 ? 12 : 0
                if (delta) queueList.contentY = Math.max(0, Math.min(Math.max(0, queueList.contentHeight - queueList.height), queueList.contentY + delta))
            }
        }
    }
    Dialog {
        id: confirmCancelQueue
        objectName: "confirmCancelQueue"
        title: "Gesamte Warteschlange abbrechen?"
        modal: true
        anchors.centerIn: Overlay.overlay
        width: Math.min(490, pane.Window.window.width - 40)
        standardButtons: Dialog.Cancel | Dialog.Ok
        background: Rectangle { color: "#292929"; radius: 8; border.color: "#454545" }
        contentItem: Text {
            text: "Wartende Aufträge werden entfernt und die aktuelle Transkription wird abgebrochen. Ein bereits begonnener Export wird fertiggestellt. Originale und vorhandene Transkripte bleiben erhalten.\n\nDie Warteschlange bleibt pausiert, bis du Fortsetzen wählst. Abgebrochene Dateiversionen werden nicht automatisch erneut eingereiht."
            wrapMode: Text.WordWrap; color: "#ddd"; font.pixelSize: 13
        }
        onAccepted: pane.api.cancelQueue()
    }
}
