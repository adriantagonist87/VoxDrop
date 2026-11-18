import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: pane
    required property var api
    required property var viewState
    signal configureFolders()
    property var items: api.queueItems
    readonly property bool compact: viewState.queueCompact
    property bool searchOpen: false
    readonly property bool searching: Boolean(viewState.queueSearch)
    property bool dragging: false
    property real dragY: -1
    property var expandedJobs: ({})
    onCompactChanged: expandedJobs = ({})
    function toggleExpanded(identifier, expanded) {
        var updated = Object.assign({}, expandedJobs)
        updated[identifier] = !expanded
        expandedJobs = updated
    }
    spacing: 8

    component QueueButton: Button {
        property bool primary: false
        padding: 7
        font.pixelSize: 12
        palette.buttonText: "#e8e8e8"
        contentItem: Text { text: parent.text; font: parent.font; color: parent.enabled ? "#e8e8e8" : "#777"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; wrapMode: Text.WordWrap }
        background: Rectangle { radius: 5; color: parent.down ? "#456653" : parent.primary && parent.enabled ? "#32644a" : parent.hovered ? "#383838" : "#282828"; border.color: parent.primary && parent.enabled ? "#8ac6a5" : "#454545" }
    }
    component QueueMenuAction: MenuItem {
        id: menuAction
        contentItem: Text {
            text: menuAction.text; font: menuAction.font
            color: menuAction.enabled ? '#ededee' : '#7e7e84'
            verticalAlignment: Text.AlignVCenter
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Text { text: "Warteschlange (" + (pane.searching ? pane.items.length + " / " : "") + pane.viewState.queueCount + ")"; color: "#ededed"; font.pixelSize: 17; font.bold: true; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true }
        SearchToggle {
            objectName: 'queueSearchToggle'
            checked: pane.searchOpen
            Accessible.name: pane.searchOpen ? 'Warteschlangensuche schließen und zurücksetzen' : 'Warteschlange durchsuchen'
            onClicked: {
                pane.searchOpen = !pane.searchOpen
                if (pane.searchOpen) queueSearch.forceActiveFocus()
                else pane.api.setQueueSearch('')
            }
        }
        QueueButton {
            objectName: "queueDetailsToggle"
            text: pane.compact ? "Details anzeigen" : "Kompakte Liste"
            enabled: !pane.dragging
            onClicked: pane.api.setQueueCompact(!pane.compact)
        }
        QueueButton { id: queueActionTrigger; objectName: "queueActionsButton"; text: "Aktionen …"; Accessible.name: "Warteschlangenaktionen"; onClicked: queueActions.open() }
    }
    RowLayout {
        visible: pane.searchOpen
        Layout.fillWidth: true
        TextField {
            id: queueSearch
            objectName: 'queueSearchField'
            Layout.fillWidth: true
            selectByMouse: true
            placeholderText: 'Dateiname oder Pfad (* und ?)'
            Accessible.name: 'Warteschlange nach Dateiname oder Pfad durchsuchen'
            text: pane.viewState.queueSearch
            onTextChanged: pane.api.setQueueSearch(text)
        }
        QueueButton { text: '×'; Accessible.name: 'Warteschlangensuche zurücksetzen'; onClicked: pane.api.setQueueSearch('') }
    }
    Text { visible: pane.searching; text: 'Positionen und Reihenfolgeaktionen gelten für die gesamte Warteschlange.'; color: "#b7b7bc"; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    Text {
        Layout.fillWidth: true
        visible: pane.items.length === 0
        text: pane.searching ? 'Keine passenden Aufträge.' : "Keine wartenden Aufträge. Dateien oder Ordner hier ablegen oder oben hinzufügen."
        color: "#ababab"; font.pixelSize: 13
    }
    QueueButton { text: "Ordnerüberwachung einrichten"; visible: !pane.searching && pane.items.length === 0 && pane.viewState.folderCount === 0; onClicked: pane.configureFolders() }
    ListView {
        id: queueList
        objectName: "queueList"
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 100
        clip: true
        spacing: pane.compact ? 3 : 7
        model: pane.api.queueModel
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}
        delegate: Item {
            id: row
            required property var modelData
            required property int index
            property bool expanded: Object.prototype.hasOwnProperty.call(pane.expandedJobs, modelData.id) ? pane.expandedJobs[modelData.id] : !pane.compact
            objectName: "queueRow" + modelData.id
            width: queueList.width - 12
            height: contents.implicitHeight + 16
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
                RowLayout {
                    Layout.fillWidth: true; spacing: 4
                    Text { Layout.fillWidth: true; text: row.modelData.position + ".  " + row.modelData.name; font.bold: true; font.pixelSize: 13; color: "#ededed"; wrapMode: row.expanded ? Text.WrapAnywhere : Text.NoWrap; maximumLineCount: row.expanded ? 2 : 1; elide: Text.ElideMiddle }
                    QueueButton {
                        objectName: "expandQueue" + row.modelData.id
                        Layout.preferredWidth: 27
                        contentItem: Item {
                            implicitWidth: 13; implicitHeight: 14
                            Item {
                                anchors.centerIn: parent; width: 12; height: 12
                                rotation: row.expanded ? 90 : 0
                                Rectangle { x: 3; y: 2; width: 7; height: 2; radius: 1; color: "#e8e8e8"; rotation: 45 }
                                Rectangle { x: 3; y: 6; width: 7; height: 2; radius: 1; color: "#e8e8e8"; rotation: -45 }
                            }
                        }
                        Accessible.name: (row.expanded ? "Angaben einklappen: " : "Angaben ausklappen: ") + row.modelData.name
                        enabled: !pane.dragging
                        onClicked: pane.toggleExpanded(row.modelData.id, row.expanded)
                    }
                    QueueButton {
                        id: rowActionTrigger
                        objectName: "queueActions" + row.modelData.id
                        Layout.preferredWidth: 27
                        contentItem: Item {
                            implicitWidth: 13; implicitHeight: 14
                            Row { anchors.centerIn: parent; spacing: 2; Repeater { model: 3; Rectangle { width: 2; height: 2; radius: 1; color: "#e8e8e8" } } }
                        }
                        Accessible.name: "Auftragsaktionen: " + row.modelData.name
                        enabled: !pane.viewState.busy
                        onClicked: moveMenu.open()
                    }
                }
                Text { Layout.fillWidth: true; text: row.modelData.path; color: "#b7b7bc"; font.pixelSize: 12; elide: row.expanded ? Text.ElideNone : Text.ElideMiddle; wrapMode: row.expanded ? Text.WrapAnywhere : Text.NoWrap }
                Text { visible: row.expanded; Layout.fillWidth: true; text: row.modelData.status + " · " + row.modelData.size + " · Dauer " + row.modelData.audio; color: "#c8dfd3"; font.pixelSize: 11; wrapMode: Text.WordWrap }
                Text { visible: row.expanded; Layout.fillWidth: true; text: row.modelData.model + " · " + row.modelData.language + " · " + row.modelData.hardware; color: "#bcbcbc"; font.pixelSize: 11; wrapMode: Text.WordWrap }
                Text { visible: row.expanded; Layout.fillWidth: true; text: "Eingereiht " + row.modelData.added + (row.modelData.retryAt ? " · Wiederholung " + row.modelData.retryAt : "") + (row.modelData.options ? " · " + row.modelData.options : ""); color: "#aaa"; font.pixelSize: 11; wrapMode: Text.WordWrap }
                RowLayout {
                    visible: row.expanded && pane.width >= 340
                    Layout.fillWidth: true; spacing: 4
                    QueueButton { text: "Reihenfolge"; enabled: !pane.viewState.busy; Accessible.name: "Reihenfolge ändern: " + row.modelData.name; onClicked: moveMenu.open() }
                    QueueButton { text: "Details"; enabled: !pane.viewState.busy; onClicked: pane.api.showDetails(row.modelData.id) }
                    Item { Layout.fillWidth: true }
                    QueueButton { objectName: "removeQueue" + row.modelData.id; text: "Entfernen"; enabled: !pane.viewState.busy; Accessible.name: "Aus Warteschlange entfernen: " + row.modelData.name; onClicked: pane.api.cancelJob(row.modelData.id) }
                }
            }
            Menu {
                id: moveMenu
                objectName: 'queueMoveMenu' + row.modelData.id
                x: Math.max(0, Math.min(row.width - width, rowActionTrigger.mapToItem(row, 0, 0).x))
                y: rowActionTrigger.mapToItem(row, 0, rowActionTrigger.height).y
                QueueMenuAction { objectName: 'queueMoveFirst' + row.modelData.id; text: "Als Nächstes"; enabled: !pane.viewState.busy && row.modelData.position > 1; onTriggered: pane.api.moveQueueRelative(row.modelData.id, 'first') }
                QueueMenuAction { objectName: 'queueMoveUp' + row.modelData.id; text: "Einen Platz nach oben"; enabled: !pane.viewState.busy && row.modelData.position > 1; onTriggered: pane.api.moveQueueRelative(row.modelData.id, 'up') }
                QueueMenuAction { objectName: 'queueMoveDown' + row.modelData.id; text: "Einen Platz nach unten"; enabled: !pane.viewState.busy && row.modelData.position < pane.viewState.queueCount; onTriggered: pane.api.moveQueueRelative(row.modelData.id, 'down') }
                QueueMenuAction { objectName: 'queueMoveLast' + row.modelData.id; text: "Ans Ende"; enabled: !pane.viewState.busy && row.modelData.position < pane.viewState.queueCount; onTriggered: pane.api.moveQueueRelative(row.modelData.id, 'last') }
                MenuSeparator {}
                QueueMenuAction { text: "Auftragsdetails öffnen"; onTriggered: pane.api.showDetails(row.modelData.id) }
                QueueMenuAction { text: "Aus Warteschlange entfernen"; onTriggered: pane.api.cancelJob(row.modelData.id) }
            }
            DropArea {
                id: drop
                anchors.fill: parent
                keys: ["voxdrop-queue"]
                onPositionChanged: drag => { pane.dragY = row.mapToItem(queueList, 0, drag.y).y }
                onDropped: event => {
                    if (!event.source || event.source.modelData.id === row.modelData.id) return
                    var after = event.y > height / 2
                    pane.api.moveQueueDrop(event.source.modelData.id, row.modelData.id, after)
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
    Menu {
        id: queueActions
        objectName: "queueActionsMenu"
        x: Math.max(0, Math.min(pane.width - width, queueActionTrigger.mapToItem(pane, 0, 0).x))
        y: queueActionTrigger.mapToItem(pane, 0, queueActionTrigger.height).y
        QueueMenuAction {
            objectName: "cancelQueueButton"
            text: "Warteschlange leeren …"
            enabled: !pane.viewState.busy && (pane.viewState.queueCount > 0 || Boolean(pane.viewState.current.name))
            onTriggered: confirmCancelQueue.open()
        }
    }
    Dialog {
        id: confirmCancelQueue
        objectName: "confirmCancelQueue"
        title: "Warteschlange leeren und Aufträge abbrechen?"
        modal: true
        anchors.centerIn: Overlay.overlay
        width: Math.min(490, pane.Window.window.width - 40)
        standardButtons: Dialog.Cancel | Dialog.Ok
        background: Rectangle { color: "#292929"; radius: 8; border.color: "#454545" }
        contentItem: Text {
            text: pane.viewState.queueCount + " wartende Aufträge werden entfernt" + (pane.viewState.current.name ? " und der aktuelle Auftrag wird abgebrochen" : "") + ". Ein bereits begonnener Export wird fertiggestellt. Originale und vorhandene Transkripte bleiben erhalten.\n\nZum bloßen Anhalten nutze Stopp. Ungestartete Aufträge zählen nicht als Verarbeitung im Verlauf. Nach dem Leeren werden abgebrochene Dateiversionen nicht automatisch erneut eingereiht."
            wrapMode: Text.WordWrap; color: "#ddd"; font.pixelSize: 13
        }
        onAccepted: pane.api.cancelQueue()
    }
}
