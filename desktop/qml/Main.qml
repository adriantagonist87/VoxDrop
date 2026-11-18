import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ApplicationWindow {
    id: window
    objectName: "voxdropWindow"
    required property var api
    property var viewState: api.state
    property var settings: api.settings
    property var selected: api.detail
    property bool historySearchOpen: false
    property bool settingsOpen: false
    property int settingsTab: 0
    property int workTab: 0
    readonly property bool focusView: width < 1200 || api.workspaceView === "focus"
    onSettingsTabChanged: Qt.callLater(function() { settingsScroll.contentItem.contentY = 0 })
    function openSettings(tab) { settingsTab = tab; settingsOpen = true }
    function showHistory() { settingsOpen = false; workTab = 1 }
    function showQueue() { settingsOpen = false; workTab = 0 }
    readonly property color canvas: "#1e1e1e"
    readonly property color sidebar: "#242424"
    readonly property color surface: "#292929"
    readonly property color line: "#3b3b3b"
    readonly property color textColor: "#ededee"
    readonly property color muted: "#b7b7bc"
    readonly property color accent: "#8ac6a5"
    readonly property color warningColor: "#ffb4ad"
    property bool warningPulse: true
    property real currentTime: Date.now() / 1000

    function completionTime(job) {
        const elapsed = Math.floor(currentTime - job.finished)
        if (!job.finished || elapsed < 0 || elapsed >= 3600)
        return job.end
        const age = elapsed < 60 ? elapsed + " Sek." : Math.floor(elapsed / 60) + " Min."
        return job.end + " (vor " + age + ")"
    }

    Timer {
        interval: 1000
        repeat: true
        running: window.visible
        triggeredOnStart: true
        onTriggered: window.currentTime = Date.now() / 1000
    }

    Timer {
        interval: 700
        repeat: true
        running: window.visible && viewState.warnings.length > 0
        onTriggered: window.warningPulse = !window.warningPulse
    }

    title: "VoxDrop"
    width: 1280
    height: 820
    minimumWidth: 1010
    minimumHeight: 630
    color: canvas
    font.pixelSize: 13
    palette.window: canvas
    palette.windowText: textColor
    palette.base: "#202020"
    palette.text: textColor
    palette.button: surface
    palette.buttonText: textColor
    palette.mid: line
    palette.dark: "#171717"
    palette.light: "#454545"
    palette.highlight: accent
    palette.highlightedText: "#14231c"
    palette.placeholderText: muted

    onClosing: function(event) {
        if (api.state.shutdownComplete) {
            event.accepted = true
            return
        }
        event.accepted = false
        if (api.hasTray())
        window.hide()
        else
        window.showMinimized()
    }

    component Copy: Label {
        color: window.textColor
        textFormat: Text.PlainText
        wrapMode: Text.Wrap
    }

    component Muted: Copy {
        color: window.muted
        font.pixelSize: 12
    }

    component Heading: Copy {
        font.pixelSize: 17
        font.weight: Font.DemiBold
    }

    component AppActionButton: Button {
        id: action
        property bool primary: false
        property bool errorAlert: false
        font.pixelSize: 12
        horizontalPadding: 10
        verticalPadding: 6
        implicitHeight: 30
        contentItem: Text {
            text: action.text
            textFormat: Text.PlainText
            font: action.font
            color: !action.enabled ? "#a0a0a4" :
            action.errorAlert ? "#ffffff" :
            (action.primary || action.checked ? "#14231c" : window.textColor)
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        background: Rectangle {
            radius: 6
            color: action.errorAlert && action.enabled ?
            (action.down ? "#92252e" : action.hovered ? "#c5424b" : "#b5303a") :
            action.primary || action.checked ?
            (action.enabled ? (action.down ? "#76ac8e" : window.accent) : "#343d37") :
            (action.down ? "#414141" : action.hovered ? "#353535" : window.surface)
            border.color: action.activeFocus ? window.accent :
            action.errorAlert ? (action.checked ? window.warningColor : "#d85f68") : window.line
            border.width: action.activeFocus || (action.errorAlert && action.checked) ? 2 : 1
        }
    }

    component Picker: ComboBox {
        id: picker
        font.pixelSize: 12
        implicitHeight: 30
        indicator: Text {
            x: picker.width - width - 9
            y: (picker.height - height) / 2
            color: window.muted
            text: "⌄"
            font.pixelSize: 17
        }
        background: Rectangle {
            color: window.canvas
            border.color: picker.activeFocus ? window.accent : window.line
            radius: 5
        }
    }

    component Field: TextField {
        id: field
        font.pixelSize: 12
        implicitHeight: 30
        selectByMouse: true
        background: Rectangle {
            color: window.canvas
            border.color: field.activeFocus ? window.accent : window.line
            radius: 5
        }
    }

    component TaskProgress: ProgressBar {
        id: progress
        implicitHeight: 6
        padding: 0
        background: Rectangle {
            color: window.line
            radius: 3
        }
        contentItem: Item {
            clip: true
            Rectangle {
                id: fill
                width: parent.width * (progress.indeterminate ? 0.28 : progress.visualPosition)
                height: parent.height
                radius: 3
                color: window.accent
                NumberAnimation on x {
                    running: progress.visible && progress.indeterminate
                    from: -fill.width
                    to: progress.availableWidth
                    duration: 1450
                    loops: Animation.Infinite
                }
            }
        }
        onIndeterminateChanged: {
            if (!indeterminate)
            fill.x = 0
        }
    }

    component Toggle: CheckBox {
        id: toggle
        font.pixelSize: 12
        spacing: 9
        padding: 0
        leftPadding: 0
        rightPadding: 0
        implicitHeight: Math.max(23, caption.implicitHeight + 4)
        indicator: Rectangle {
            x: 0
            y: (toggle.height - height) / 2
            implicitWidth: 15
            implicitHeight: 15
            radius: 3
            color: toggle.checked ? window.accent : window.canvas
            border.color: toggle.activeFocus ? window.accent : "#68686b"
            Text {
                anchors.centerIn: parent
                text: toggle.checked ? "✓" : ""
                color: "#14231c"
                font.pixelSize: 12
                font.weight: Font.Bold
            }
        }
        contentItem: Copy {
            id: caption
            text: toggle.text
            font: toggle.font
            color: toggle.enabled ? window.textColor : "#a0a0a4"
            leftPadding: toggle.indicator.width + toggle.spacing
            verticalAlignment: Text.AlignVCenter
        }
    }

    DropArea {
        id: folderDrop
        objectName: "folderDrop"
        anchors.fill: parent
        z: 20
        enabled: viewState.ready && !viewState.busy
        onEntered: function(drag) {
            drag.accepted = drag.hasUrls && (drag.supportedActions & Qt.CopyAction) !== 0
        }
        onDropped: function(drop) {
            if (drop.hasUrls && (drop.supportedActions & Qt.CopyAction) !== 0) {
                drop.accept(Qt.CopyAction)
                api.enqueueFolders(drop.urls)
            } else {
                drop.accepted = false
            }
        }

        Rectangle {
            anchors.fill: parent
            anchors.margins: 5
            visible: folderDrop.containsDrag
            radius: 9
            color: "#b51e1e1e"
            border.color: accent
            border.width: 2
            Heading {
                anchors.centerIn: parent
                text: "Dateien oder Ordner einmalig hinzufügen"
            }
        }
    }


    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 54
            color: sidebar
            RowLayout {
                anchors.fill: parent; anchors.leftMargin: 16; anchors.rightMargin: 16
                spacing: 12
                AppActionButton {
                    objectName: "folderStatusButton"
                    text: "Überwachung " + (viewState.monitoringEnabled ? "an" : "aus") + " · Ordner " + viewState.availableFolderCount + "/" + viewState.folderCount
                    Accessible.description: "Überwachungszustand und Erreichbarkeit. Einstellungen für Ordner öffnen."
                    errorAlert: viewState.folderWarnings.length > 0
                    onClicked: window.openSettings(1)
                }
                Item { Layout.fillWidth: true }
                Copy { text: "GPU-Budget " + Math.round(gpuBudgetSlider.value) + " %"; font.pixelSize: 12 }
                Slider {
                    id: gpuBudgetSlider
                    objectName: "gpuBudgetSlider"
                    Layout.preferredWidth: 132
                    Layout.minimumWidth: 90
                    Layout.maximumWidth: 180
                    from: 10
                    to: 100
                    stepSize: 5
                    snapMode: Slider.SnapAlways
                    value: settings.gpu_budget_percent || 100
                    enabled: viewState.ready && !viewState.busy && api.gpuValue === "cuda" && (settings.hardware === "cuda" || viewState.current.hardwareValue === "cuda")
                    Accessible.name: "GPU-Arbeitsbudget in Prozent"
                    Accessible.description: "Weniger GPU-Arbeit lässt mehr Zeit für andere Programme und verlängert die Transkription."
                    background: Rectangle {
                        x: gpuBudgetSlider.leftPadding
                        y: gpuBudgetSlider.topPadding + gpuBudgetSlider.availableHeight / 2 - height / 2
                        width: gpuBudgetSlider.availableWidth
                        implicitHeight: 6
                        radius: 3
                        color: "#505055"
                        Rectangle {
                            width: gpuBudgetSlider.visualPosition * parent.width
                            height: parent.height
                            radius: 3
                            color: gpuBudgetSlider.enabled ? window.accent : "#77777d"
                        }
                    }
                    handle: Rectangle {
                        x: gpuBudgetSlider.leftPadding + gpuBudgetSlider.visualPosition * (gpuBudgetSlider.availableWidth - width)
                        y: gpuBudgetSlider.topPadding + gpuBudgetSlider.availableHeight / 2 - height / 2
                        implicitWidth: 20
                        implicitHeight: 20
                        radius: 10
                        color: gpuBudgetSlider.enabled ? window.accent : "#77777d"
                        border.width: gpuBudgetSlider.activeFocus ? 2 : 1
                        border.color: gpuBudgetSlider.activeFocus ? window.textColor : "#242424"
                    }
                    onMoved: {
                        gpuBudgetSave.pendingValue = Math.round(value)
                        api.setSetting("gpu_budget_percent", gpuBudgetSave.pendingValue)
                        gpuBudgetSave.restart()
                    }
                    Timer {
                        id: gpuBudgetSave
                        property int pendingValue: 100
                        interval: 250
                        onTriggered: {
                            if (viewState.busy) {
                                restart()
                                return
                            }
                            api.setGpuBudget(pendingValue)
                        }
                    }
                }

                AppActionButton { objectName: "settingsButton"; text: "Einstellungen" + (viewState.settingsDirty ? " •" : ""); checked: window.settingsOpen; onClicked: window.settingsOpen = !window.settingsOpen }
                AppActionButton { text: "Menü"; Accessible.name: "App-Menü und Ansicht"; onClicked: appMenu.open() }
            }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: line }
        Item {
            Layout.fillWidth: true
            implicitHeight: 108
            RowLayout {
                anchors.fill: parent; anchors.margins: 14
                spacing: 14
                PlaybackButton { api: window.api; viewState: window.viewState; showLabel: false; Layout.preferredWidth: 44; Layout.maximumWidth: 44 }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 4
                    Copy {
                        objectName: "processingStatus"
                        Layout.fillWidth: true; font.pixelSize: 12
                        text: viewState.queuePaused && viewState.queueImmediateCount > 0 ? "Nur Sofort-Auswahl · Restwarteschlange angehalten" : viewState.processingStatus
                        color: viewState.processingStopping || viewState.queuePaused ? "#e4c07d" : accent
                        maximumLineCount: 1; elide: Text.ElideRight
                    }
                    Copy { objectName: "currentFileName"; text: viewState.current.name || (viewState.ready ? "Kein Auftrag in Bearbeitung" : "VoxDrop wird vorbereitet …"); font.weight: Font.DemiBold; font.pixelSize: 14; Layout.fillWidth: true; elide: Text.ElideMiddle; maximumLineCount: 1 }
                    TaskProgress { Layout.fillWidth: true; visible: Boolean(viewState.current.name); indeterminate: viewState.current.progress === null || viewState.current.progress === undefined; value: viewState.current.progress || 0 }
                    Muted {
                        Layout.fillWidth: true; maximumLineCount: 1; elide: Text.ElideRight
                        text: viewState.current.name ? viewState.current.phase + (viewState.current.progress === null || viewState.current.progress === undefined ? " · Verarbeitung läuft, Fortschritt noch unbekannt" : " · " + Math.round(viewState.current.progress * 100) + " % dieser Phase") + " · Laufzeit " + viewState.current.elapsed + " · " + viewState.current.model + " · " + viewState.current.hardware : "Start/Stopp steuert die Verarbeitung. Die Ordnerüberwachung wird separat geschaltet."
                    }
                }
                ColumnLayout {
                    Layout.preferredWidth: 230
                    Layout.maximumWidth: 230
                    spacing: 5
                    RowLayout {
                        Layout.fillWidth: true
                        AppActionButton { objectName: "currentDetailsButton"; text: "Auftragsdetails"; Layout.fillWidth: true; enabled: Boolean(viewState.current.id); onClicked: api.showDetails(viewState.current.id) }
                        AppActionButton { objectName: "currentActionsButton"; text: "Aktionen"; Accessible.name: "Aktionen zum aktuellen Auftrag"; enabled: Boolean(viewState.current.id); onClicked: currentMenu.open() }
                    }
                    AppActionButton {
                        objectName: "pauseQueueButton"; text: "Nach diesem Auftrag pausieren"; Layout.fillWidth: true
                        enabled: Boolean(viewState.current.name) && !viewState.processingStopping && (!viewState.queuePaused || viewState.queueImmediateCount > 0) && !viewState.busy
                        onClicked: api.pauseQueue(true)
                    }
                }
            }
        }
        Rectangle {
            Layout.fillWidth: true; visible: viewState.folderWarnings.length > 0 || viewState.waitingForNetwork || (viewState.ready && !viewState.modelsReady)
            implicitHeight: globalWarning.implicitHeight + 16; color: "#352825"
            RowLayout {
                id: globalWarning; x: 16; y: 8; width: parent.width - 32; spacing: 12
                Copy { Layout.fillWidth: true; color: warningColor; maximumLineCount: 2; elide: Text.ElideRight; text: viewState.waitingForNetwork ? "Modell-Download: Netzwerkzugriff verweigert (10013). Ohne sichtbare Freigabeanfrage Protokoll prüfen. Automatischer erneuter Versuch läuft." : viewState.folderWarnings.length ? viewState.folderWarnings.length + " Ordner nicht erreichbar. Andere verfügbare Ordner werden weiter verarbeitet." : "Für die gewählte Konfiguration fehlen Modelle. Die Einrichtung kann unter Transkription abgeschlossen werden." }
                AppActionButton { text: "Ordner prüfen"; visible: !viewState.waitingForNetwork && viewState.folderWarnings.length > 0; onClicked: window.openSettings(1) }
                AppActionButton { objectName: "modelSetupButton"; text: "Modelle einrichten"; visible: !viewState.waitingForNetwork && !viewState.modelsReady; onClicked: window.openSettings(0) }
                AppActionButton { objectName: "cancelNetworkWait"; text: "Warten abbrechen"; visible: viewState.waitingForNetwork; onClicked: api.cancelNetworkWait() }
                AppActionButton { text: "Protokoll öffnen"; visible: viewState.waitingForNetwork; onClicked: api.openLog() }
            }
        }
        RowLayout {
            Layout.fillWidth: true; Layout.leftMargin: 16; Layout.rightMargin: 16; Layout.topMargin: 4; Layout.bottomMargin: 4; spacing: 6
            AppActionButton { objectName: "queueTab"; text: "Warteschlange (" + viewState.queueCount + ")"; checked: !window.settingsOpen && (!window.focusView || window.workTab === 0); onClicked: window.showQueue() }
            AppActionButton { objectName: "historyTab"; text: "Verlauf (" + (viewState.globalHistoryCounts.all || 0) + ")"; checked: !window.settingsOpen && (!window.focusView || window.workTab === 1); onClicked: window.showHistory() }
            Item { Layout.fillWidth: true }
            AppActionButton { objectName: "globalErrorsButton"; text: "Fehler (" + (viewState.globalHistoryCounts.errors || 0) + ")"; Accessible.description: "Alle Fehler anzeigen; eine aktive Verlaufssuche wird zurückgesetzt."; errorAlert: (viewState.globalHistoryCounts.errors || 0) > 0; onClicked: { api.setHistorySearch(""); api.stopContentSearch(); api.setFilter("errors"); window.showHistory() } }
            AppActionButton { objectName: "addMediaButton"; text: "Dateien hinzufügen …"; enabled: viewState.ready && !viewState.busy; onClicked: api.pickMedia() }
            AppActionButton { text: "Ordner hinzufügen …"; enabled: viewState.ready && !viewState.busy; onClicked: api.pickDropFolder() }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: line }
        StackLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            currentIndex: window.settingsOpen ? 1 : 0
            SplitView {
                id: split; objectName: "columns"
                handle: Rectangle {
                    objectName: "columnHandle"; implicitWidth: 8
                    color: SplitHandle.pressed ? "#456653" : SplitHandle.hovered ? "#393939" : canvas
                    Rectangle { anchors.horizontalCenter: parent.horizontalCenter; width: 1; height: parent.height; color: parent.SplitHandle.hovered ? accent : line }
                }
                onResizingChanged: { if (!resizing && !window.focusView) api.saveWorkspaceHistoryWidth(Math.round(historyPane.width)) }
                Rectangle {
                    id: workPane; objectName: "workPane"; color: canvas
                    SplitView.fillWidth: true; SplitView.minimumWidth: window.focusView ? 0 : 450
                    visible: !window.focusView || window.workTab === 0
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 14; spacing: 4
                        QueuePane { api: window.api; viewState: window.viewState; Layout.fillWidth: true; Layout.fillHeight: true; onConfigureFolders: window.openSettings(1) }
                    }
                }
                Rectangle {
                    id: historyPane
                    objectName: "historyPane"
                    color: sidebar
                    SplitView.minimumWidth: window.focusView ? 0 : 340
                    SplitView.fillWidth: window.focusView
                    SplitView.preferredWidth: api.workspaceHistoryWidth
                    visible: !window.focusView || window.workTab === 1
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 10
                        RowLayout {
                            Layout.fillWidth: true
                            Heading { text: "Verlauf & Bestand"; Layout.fillWidth: true }
                            SearchToggle {
                                objectName: 'historySearchToggle'
                                checked: window.historySearchOpen
                                Accessible.name: window.historySearchOpen ? 'Verlaufssuche schließen und zurücksetzen' : 'Verlauf durchsuchen'
                                onClicked: {
                                    window.historySearchOpen = !window.historySearchOpen
                                    if (window.historySearchOpen) historySearch.forceActiveFocus()
                                    else { api.setHistorySearch(''); api.stopContentSearch() }
                                }
                            }

                        }
                        ColumnLayout {
                            visible: window.historySearchOpen
                            Layout.fillWidth: true
                            RowLayout {
                                Layout.fillWidth: true
                                Field {
                                    id: historySearch
                                    objectName: 'historySearchField'
                                    Layout.fillWidth: true
                                    placeholderText: 'Dateiname/Pfad (* und ?) oder Suchtext'
                                    Accessible.name: 'Verlauf durchsuchen'
                                    text: viewState.historySearch
                                    onTextChanged: api.setHistorySearch(text)
                                }
                                AppActionButton { text: '×'; Accessible.name: 'Verlaufssuche zurücksetzen'; onClicked: api.setHistorySearch('') }
                            }
                            AppActionButton {
                                objectName: 'contentSearchButton'
                                text: viewState.contentSearchRunning ? 'Detailsuche stoppen' : viewState.contentSearchActive ? 'Detailsuche beenden' : 'Detailsuche starten'
                                enabled: !viewState.busy && !viewState.contentSearchStopping && (viewState.contentSearchRunning || viewState.contentSearchActive || viewState.historySearch.trim().length > 0)
                                onClicked: {
                                    if (viewState.contentSearchRunning || viewState.contentSearchActive) api.stopContentSearch()
                                    else api.startContentSearch()
                                }
                            }
                            Muted { Layout.fillWidth: true; text: viewState.contentSearchStatus; visible: text.length > 0 }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            Repeater {
                                model: [{label: "Alle", value: "all"}, {label: "Fehler", value: "errors"}, {label: "Fertig", value: "done"}]
                                delegate: AppActionButton {
                                    required property var modelData
                                    readonly property int itemCount: viewState.historyCounts[modelData.value] || 0
                                    objectName: "historyFilter_" + modelData.value
                                    Layout.fillWidth: true
                                    text: modelData.label + " (" + itemCount + ")"
                                    errorAlert: modelData.value === "errors" && itemCount > 0
                                    checkable: true
                                    checked: viewState.filter === modelData.value
                                    onClicked: api.setFilter(modelData.value)
                                }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            Repeater {
                                model: [{label: 'Abgebrochen', value: 'cancelled'}, {label: 'Bestand', value: 'existing'}]
                                delegate: AppActionButton {
                                    required property var modelData
                                    objectName: 'historyFilter_' + modelData.value
                                    Layout.fillWidth: true
                                    text: modelData.label + ' (' + (viewState.historyCounts[modelData.value] || 0) + ')'
                                    checkable: true
                                    checked: viewState.filter === modelData.value
                                    onClicked: api.setFilter(modelData.value)
                                }
                            }
                        }
                        Muted {
                            Layout.fillWidth: true
                            text: viewState.filter === 'existing' ? 'Vorhandene oder übernommene Transkripte; keine neue Verarbeitung.' : 'Verlauf: gestartete Verarbeitungen. Vor dem Start entfernte Aufträge werden nicht gezählt.'
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Copy { text: "Sortierung"; Layout.fillWidth: true }
                            Picker {
                                objectName: "historyOrder"
                                Layout.preferredWidth: 206
                                Accessible.name: "Verlauf sortieren"
                                model: ["Chronologisch absteigend", "Chronologisch aufsteigend"]
                                currentIndex: viewState.order === "asc" ? 1 : 0
                                onActivated: index => api.setOrder(index === 1 ? "asc" : "desc")
                            }
                        }
                        Muted { text: "Keine Aufträge"; visible: jobs.count === 0; Layout.fillWidth: true }
                        ListView {
                            id: jobs
                            objectName: "historyList"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            spacing: 1
                            model: api.historyModel
                            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                            delegate: ItemDelegate {
                                id: job
                                required property var modelData
                                width: ListView.view.width - (jobs.ScrollBar.vertical.visible ? 10 : 0)
                                padding: 8
                                implicitHeight: jobInfo.implicitHeight + 16
                                Accessible.name: "Auftragsdetails " + modelData.name
                                onClicked: api.showDetails(modelData.id)
                                background: Rectangle {
                                    radius: 5
                                    color: job.hovered || job.activeFocus ? "#303030" : "transparent"
                                    border.color: job.activeFocus ? accent : "transparent"
                                    Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: line }
                                }
                                contentItem: ColumnLayout {
                                    id: jobInfo
                                    spacing: 3
                                    Copy { text: job.modelData.name; font.pixelSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true; maximumLineCount: 1; elide: Text.ElideMiddle }
                                    Muted { text: "Neutranskription"; visible: job.modelData.repeat; Layout.fillWidth: true }
                                    Muted { text: job.modelData.path; Layout.fillWidth: true; maximumLineCount: 1; elide: Text.ElideMiddle }
                                    Muted { text: "Aufnahme " + job.modelData.audio + " · Verarbeitung " + job.modelData.elapsed; Layout.fillWidth: true; maximumLineCount: 1; elide: Text.ElideRight }
                                    Muted { text: window.completionTime(job.modelData); Layout.fillWidth: true }
                                    Copy { text: job.modelData.errorText || ""; visible: text.length > 0; color: warningColor; Layout.fillWidth: true; maximumLineCount: 2; elide: Text.ElideRight }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Muted { text: job.modelData.status; color: job.modelData.error ? warningColor : muted; Layout.fillWidth: true }
                                        Muted { text: job.modelData.updated }
                                    }
                                }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Muted { text: "Angezeigt " + api.historyItems.length + " / " + viewState.historyTotal; Layout.fillWidth: true }
                            AppActionButton { objectName: "historyPrevious"; text: "‹"; Accessible.name: "Vorherige Verlaufsseite"; enabled: viewState.historyOffset > 0 && !viewState.busy; onClicked: api.setHistoryPage(viewState.historyPage - 1) }
                            SpinBox { objectName: "historyPagePicker"; Accessible.name: "Verlaufsseite"; from: 1; to: Math.max(1, Math.ceil(viewState.historyTotal / 250)); value: viewState.historyPage + 1; editable: true; onValueModified: api.setHistoryPage(value - 1); Layout.preferredWidth: 104; implicitHeight: 30 }
                            AppActionButton { objectName: "historyNext"; text: "›"; Accessible.name: "Nächste Verlaufsseite"; enabled: viewState.historyOffset + api.historyItems.length < viewState.historyTotal && !viewState.busy; onClicked: api.setHistoryPage(viewState.historyPage + 1) }
                        }
                    }
                }

            }
            Rectangle {
                id: settingsPane; objectName: "settingsPane"; color: canvas
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 14; spacing: 12
                    RowLayout {
                        Layout.fillWidth: true
                        Heading { text: "Einstellungen"; Layout.fillWidth: true }
                        AppActionButton { text: "Zur Arbeitsübersicht"; onClicked: window.settingsOpen = false }
                    }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 8
                        AppActionButton { objectName: "transcriptionSettingsTab"; text: "Transkription"; checked: window.settingsTab === 0; onClicked: window.settingsTab = 0 }
                        AppActionButton { objectName: "folderSettingsTab"; text: "Ordner & Überwachung"; checked: window.settingsTab === 1; onClicked: window.settingsTab = 1 }
                        AppActionButton { objectName: "appSettingsTab"; text: "App & Daten"; checked: window.settingsTab === 2; onClicked: window.settingsTab = 2 }
                    }
                    ScrollView {
                        id: settingsScroll; objectName: "settingsScroll"
                        Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                        contentWidth: availableWidth; contentHeight: form.implicitHeight + 18
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                        ScrollBar.vertical.policy: ScrollBar.AlwaysOn
                        ColumnLayout {
                            id: form; objectName: "settingsForm"; x: 4; y: 4
                            width: Math.min(860, Math.max(1, settingsScroll.availableWidth - 20)); spacing: 12
                            ColumnLayout {
                                Layout.fillWidth: true
                                visible: window.settingsTab === 0
                                spacing: 12
                                Muted {
                                    Layout.fillWidth: true
                                    text: "Speichern gilt für neue überwachte Aufträge. Einmaliges Hinzufügen und Neutranskription verwenden die hier gewählten Optionen. Bereits eingereihte Aufträge behalten ihre Einstellungen."
                                }
                                Heading { text: "Spracherkennung"; font.pixelSize: 14 }
                                GridLayout {
                                    columns: 2
                                    uniformCellWidths: true
                                    columnSpacing: 24
                                    rowSpacing: 14
                                    Layout.fillWidth: true
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Copy { text: "Modell" }
                                        Picker {
                                            objectName: "modelPicker"
                                            Layout.fillWidth: true
                                            Accessible.name: "Transkriptionsmodell"
                                            model: ["Qwen3-ASR 1.7B", "Whisper Large v3 Turbo"]
                                            currentIndex: settings.model === "large-v3-turbo" ? 1 : 0
                                            onActivated: index => api.setSetting("model", ["qwen3-asr-1.7b", "large-v3-turbo"][index])
                                        }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Copy { text: "Sprache" }
                                        Picker {
                                            objectName: "languagePicker"
                                            Layout.fillWidth: true
                                            Accessible.name: "Sprache"
                                            model: ["Automatisch", "Deutsch", "Englisch"]
                                            currentIndex: ["auto", "de", "en"].indexOf(settings.language)
                                            onActivated: index => api.setSetting("language", ["auto", "de", "en"][index])
                                        }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Copy { text: "Rechengerät" }
                                        Picker {
                                            objectName: "hardwarePicker"
                                            Layout.fillWidth: true
                                            Accessible.name: "Rechengerät"
                                            model: [api.gpuName, "CPU"]
                                            currentIndex: settings.hardware === "cpu" ? 1 : 0
                                            onActivated: index => api.setSetting("hardware", [api.gpuValue, "cpu"][index])
                                        }
                                    }
                                    Toggle {
                                        objectName: "skipSilenceToggle"
                                        Layout.fillWidth: true
                                        text: "Lange Stille überspringen"
                                        checked: settings.skip_silence
                                        onToggled: api.setSetting("skip_silence", checked)
                                    }
                                }
                                Rectangle { Layout.fillWidth: true; height: 1; color: line }
                                Heading { text: "Sprecherzuordnung"; font.pixelSize: 14 }
                                GridLayout {
                                    columns: 2
                                    uniformCellWidths: true
                                    columnSpacing: 24
                                    rowSpacing: 10
                                    Layout.fillWidth: true
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Toggle {
                                            objectName: "speakersToggle"
                                            Layout.fillWidth: true
                                            text: "Sprechererkennung"
                                            checked: settings.speakers
                                            onToggled: api.setSetting("speakers", checked)
                                        }
                                        Toggle {
                                            objectName: "doverToggle"
                                            Layout.fillWidth: true
                                            text: "Mehrere Prüfdurchgänge (DOVER-Lap)"
                                            checked: settings.dover_lap
                                            enabled: settings.speakers
                                            onToggled: api.setSetting("dover_lap", checked)
                                        }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Copy { text: "Sprecherzahl" }
                                        Picker {
                                            objectName: "speakerCountPicker"
                                            Layout.fillWidth: true
                                            Accessible.name: "Sprecherzahl"
                                            model: ["Automatisch", "1", "2", "3", "4", "5", "6", "7", "8"]
                                            currentIndex: settings.speaker_count || 0
                                            enabled: settings.speakers
                                            onActivated: index => api.setSetting("speaker_count", index || null)
                                        }
                                    }
                                }
                                Rectangle { Layout.fillWidth: true; height: 1; color: line }
                                Heading { text: "Modelle & Speicher"; font.pixelSize: 14 }
                                Copy { text: viewState.modelsReady ? "Modelle installiert" : "Modell-Setup erforderlich"; Layout.fillWidth: true }
                                Muted { text: "Modellspeicher: " + api.modelLocation; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere }
                                RowLayout {
                                    AppActionButton { objectName: "downloadModelsButton"; text: "Modelle herunterladen"; visible: !viewState.modelsReady; enabled: viewState.ready && !viewState.busy; onClicked: api.downloadModels() }
                                    AppActionButton { text: "Protokoll öffnen"; onClicked: api.openLog() }
                                }
                                TaskProgress { Layout.fillWidth: true; visible: viewState.downloading; indeterminate: true }
                                Muted { text: api.gpuValue === "cuda" ? "GPU-Budget oben: wirkt sofort, auch für laufende Aufträge. Rechenzeit wird kooperativ freigegeben; Lastspitzen und Grafikspeicherbedarf bleiben möglich." : "GPU-Arbeitsbudget: derzeit für Windows-CUDA verfügbar. Metal-Portierung steht separat aus."; Layout.fillWidth: true }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true; visible: window.settingsTab === 1; spacing: 12
                                Toggle { objectName: "monitoringToggle"; text: "Ordnerüberwachung aktiv (wirkt sofort)"; checked: viewState.monitoringEnabled; enabled: viewState.ready && !viewState.busy; onClicked: api.setMonitoring(checked) }
                                Heading { text: "Überwachte Ordner"; Layout.fillWidth: true; font.pixelSize: 14 }
                                Repeater {
                                    model: api.folderPaths
                                    delegate: ColumnLayout {
                                        id: folder
                                        required property int index
                                        required property string modelData
                                        readonly property var status: viewState.checked[pathField.text] || ({})
                                        Layout.fillWidth: true
                                        spacing: 3
                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 5
                                            Field {
                                                id: pathField
                                                objectName: "folderField" + folder.index
                                                Layout.fillWidth: true
                                                Layout.minimumWidth: 48
                                                text: folder.modelData
                                                placeholderText: "Ordnerpfad oder smb://"
                                                Accessible.name: "Überwachter Ordner " + (folder.index + 1)
                                                ToolTip.visible: hovered && !activeFocus && contentWidth > availableWidth
                                                ToolTip.text: text
                                                ToolTip.delay: 500
                                                onTextChanged: api.editFolder(folder.index, text)
                                            }
                                            AppActionButton {
                                                text: "↻"
                                                Layout.preferredWidth: 30
                                                Accessible.name: "Ordner jetzt prüfen"
                                                enabled: pathField.text.trim().length > 0
                                                onClicked: api.checkFolders(pathField.text.trim())
                                            }
                                            AppActionButton {
                                                text: "…"
                                                Layout.preferredWidth: 30
                                                Accessible.name: "Ordner auswählen"
                                                onClicked: api.pickFolder(folder.index)
                                            }
                                            AppActionButton {
                                                text: "−"
                                                Layout.preferredWidth: 30
                                                Accessible.name: "Pfad entfernen"
                                                onClicked: api.removeFolder(folder.index)
                                            }
                                        }
                                        RowLayout {
                                            Layout.fillWidth: true
                                            visible: Boolean(folder.status.error || folder.status.available)
                                            Muted {
                                                text: "⚠"
                                                color: warningColor
                                                visible: Boolean(folder.status.error)
                                                opacity: window.warningPulse ? 1 : 0.4
                                                Accessible.name: "Ordnerproblem"
                                            }
                                            Muted {
                                                Layout.fillWidth: true
                                                color: folder.status.error ? warningColor : muted
                                                text: folder.status.error || "Erreichbar und beschreibbar"
                                            }
                                        }
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true
                                    AppActionButton { text: "+ Pfad hinzufügen"; Layout.fillWidth: true; enabled: viewState.ready; onClicked: api.addFolder() }
                                    AppActionButton { text: "Alle prüfen"; Accessible.name: "Alle Ordner prüfen"; enabled: viewState.ready; onClicked: api.checkFolders("") }
                                }
                                Toggle {
                                    objectName: "includeSubfolders"
                                    text: "Unterordner mit einbeziehen"
                                    Layout.fillWidth: true
                                    checked: settings.include_subfolders
                                    onToggled: api.setSetting("include_subfolders", checked)
                                }
                                Toggle {
                                    objectName: "createOutputSubfolder"
                                    text: "Unterordner für fertige Transkripte erstellen?"
                                    Layout.fillWidth: true
                                    enabled: !settings.include_subfolders
                                    checked: settings.create_output_subfolder
                                    onToggled: api.setSetting("create_output_subfolder", checked)
                                }
                                Field {
                                    objectName: "outputSubfolderName"
                                    Layout.fillWidth: true
                                    visible: settings.create_output_subfolder && !settings.include_subfolders
                                    text: settings.output_subfolder || ""
                                    Accessible.name: "Name des Unterordners"
                                    placeholderText: "_FERTIGGESTELLT"
                                    onTextEdited: api.setSetting("output_subfolder", text)
                                }
                                Copy { text: "Intervall Ordnerüberwachung"; Layout.fillWidth: true }
                                Picker {
                                    Layout.fillWidth: true
                                    Accessible.name: "Intervall Ordnerüberwachung"
                                    property int configured: settings.interval_seconds || 30
                                    property var options: [10, 30, 60, 300].includes(configured) ? [10, 30, 60, 300] :
                                    [10, 30, 60, 300, configured].sort((a, b) => a - b)
                                    model: options.map(seconds => seconds + " Sekunden")
                                    currentIndex: options.indexOf(configured)
                                    onActivated: index => api.setSetting("interval_seconds", options[index])
                                }

                                Muted { Layout.fillWidth: true; text: "Pfadänderungen erst speichern. Rekursive Überwachung und einmalige Drops erhalten Originalhierarchie und TXT neben Aufnahme. Ohne Unterordner kann die Zieloption Aufnahme und TXT gemeinsam verschieben. Noch geschriebene Aufnahmen werden zurückgestellt." }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true; visible: window.settingsTab === 2; spacing: 14
                                Heading { text: "App & Fenster"; font.pixelSize: 14 }
                                Muted { text: api.buildInformation; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere }
                                Toggle {
                                    text: "Automatisch bei Anmeldung starten (wirkt sofort)"
                                    Layout.fillWidth: true
                                    enabled: viewState.ready && !viewState.busy
                                    checked: viewState.autostart
                                    onToggled: api.setAutostart(checked)
                                }

                                Copy { Layout.fillWidth: true; text: "X blendet in den Systemtray aus; Minimieren geht in die Taskleiste. Erst VoxDrop beenden stoppt Überwachung und Verarbeitung und entlädt alle Modelle aus RAM/VRAM." }
                                AppActionButton { text: "VoxDrop beenden"; onClicked: api.requestQuit() }
                                Rectangle { Layout.fillWidth: true; height: 1; color: line }
                                Heading { text: "Lokale Auftragsdatenbank"; font.pixelSize: 14 }
                                Copy { Layout.fillWidth: true; text: "Zurücksetzen entfernt Warteschlange, Verlauf, Bestand, gespeicherte Abbrüche, Dateiversionen, Suchindex und lokale Arbeitskopien. Aufnahmen, TXT, Modelle und Einstellungen bleiben erhalten. Aktive Überwachung liest beim nächsten Intervall vollständig neu ein." }
                                AppActionButton { objectName: "clearHistoryButton"; text: "Auftragsdatenbank zurücksetzen …"; enabled: viewState.canClear; onClicked: confirmClear.open() }
                                Muted { Layout.fillWidth: true; visible: Boolean(viewState.current.name); text: "Während eines aktiven Auftrags gesperrt. Zum Bereinigen zuerst die Verarbeitung kontrolliert stoppen und deren Ende abwarten." }
                                RowLayout {
                                    AppActionButton { text: "Ordner jetzt prüfen"; onClicked: api.checkFolders("") }
                                    AppActionButton { text: "Protokoll öffnen"; onClicked: api.openLog() }
                                    AppActionButton { text: "Einrichtung erneut prüfen"; enabled: !viewState.busy; onClicked: api.retryPreparation() }
                                }
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Muted { text: viewState.settingsDirty ? "Ungespeicherte Änderungen" : viewState.settingsExist ? "Einstellungen gespeichert" : "Einstellungen noch nicht gespeichert"; Layout.fillWidth: true }
                        AppActionButton { objectName: "discardSettingsButton"; text: "Änderungen verwerfen"; enabled: viewState.settingsDirty && !viewState.busy; onClicked: api.discardSettings() }
                        AppActionButton { objectName: "saveButton"; text: "Änderungen speichern"; primary: true; enabled: viewState.ready && !viewState.busy && (viewState.settingsDirty || !viewState.settingsExist); onClicked: api.save(false) }
                    }
                }
            }
        }
        Rectangle {
            Layout.fillWidth: true; implicitHeight: footerContent.implicitHeight + 12; color: sidebar
            RowLayout {
                id: footerContent; x: 16; y: 6; width: parent.width - 32; spacing: 10
                Copy { objectName: "feedback"; Layout.fillWidth: true; font.pixelSize: 12; maximumLineCount: 2; elide: Text.ElideRight; text: viewState.feedbackText || (window.focusView ? "Fokusansicht · Warteschlange und Verlauf über die Reiter wechseln" : "Doppelansicht · Trennsteg zum Anpassen der Listenbreite ziehen"); color: viewState.feedbackError ? warningColor : muted }
                AppActionButton { text: "Details"; visible: Boolean(viewState.message || viewState.dropMessage); onClicked: feedbackDialog.open() }
                AppActionButton { text: "Protokoll"; visible: viewState.logAvailable; onClicked: api.openLog() }
            }
        }
    }
    Menu {
        id: appMenu
        x: window.width - width - 16; y: 52
        MenuItem { text: "Arbeitsübersicht"; onTriggered: window.settingsOpen = false }
        MenuItem { text: "Fokusansicht"; checkable: true; checked: api.workspaceView === "focus"; onTriggered: api.setWorkspaceView("focus") }
        MenuItem { text: "Automatische Doppel-/Fokusansicht"; checkable: true; checked: api.workspaceView !== "focus"; onTriggered: api.setWorkspaceView("auto") }
        MenuSeparator {}
        MenuItem { text: "Protokoll öffnen"; onTriggered: api.openLog() }
        MenuItem { text: "Über VoxDrop"; onTriggered: aboutDialog.open() }
        MenuItem { text: "VoxDrop beenden"; onTriggered: api.requestQuit() }
    }
    Menu {
        id: currentMenu
        objectName: "currentActionsMenu"
        x: window.width - width - 16; y: 120
        MenuItem { objectName: "cancelCurrentButton"; text: "Diesen Auftrag abbrechen …"; enabled: !viewState.busy && Boolean(viewState.current.canCancel); onTriggered: { confirmCurrent.jobId = viewState.current.id; confirmCurrent.jobName = viewState.current.name; confirmCurrent.open() } }
    }
    Dialog {
        id: feedbackDialog; objectName: "feedbackDialog"; title: "VoxDrop – Rückmeldung"; modal: true
        anchors.centerIn: Overlay.overlay; width: Math.min(640, window.width - 48); height: Math.min(420, window.height - 48)
        standardButtons: Dialog.Close
        contentItem: ScrollView {
            id: feedbackScroll
            clip: true; contentWidth: availableWidth
            TextArea { objectName: "feedbackText"; width: feedbackScroll.availableWidth; readOnly: true; selectByMouse: true; color: window.textColor; wrapMode: TextEdit.WrapAnywhere; textFormat: TextEdit.PlainText; text: viewState.feedbackDetails; background: null }
        }
    }
    Dialog {
        id: aboutDialog; objectName: "aboutDialog"; title: "Über VoxDrop"; modal: true
        anchors.centerIn: Overlay.overlay; width: Math.min(560, window.width - 48)
        standardButtons: Dialog.Close
        contentItem: Copy { text: api.buildInformation + "\n\nQt-/Modell- und aTrain-Lizenzen liegen im Programmordner. Überwachung und Verarbeitung laufen ausschließlich mit der aktiven App."; wrapMode: Text.WrapAnywhere }
    }
    Dialog {
        id: confirmCurrent; objectName: "confirmCurrent"; property int jobId: 0; property string jobName: ""; title: "Aktuellen Auftrag abbrechen?"; modal: true
        anchors.centerIn: Overlay.overlay; width: Math.min(510, window.width - 48)
        standardButtons: Dialog.Cancel | Dialog.Ok
        contentItem: Copy { text: confirmCurrent.jobName + "\n\nNur dieser Auftrag wird abgebrochen. Die übrige Warteschlange darf anschließend weiterlaufen. Zum Anhalten und Behalten aller Aufträge den Stopp-Knopf verwenden. Originale und vorhandene TXT bleiben erhalten." }
        onAccepted: api.cancelJob(jobId)
    }
    Connections {
        target: api
        function onDetailsOpened() { detail.open() }
        function onDropConflictOpened() { dropConflicts.open() }
        function onDropResolved() { dropConflicts.close() }
    }

    DropConflictDialog { id: dropConflicts; api: window.api }

    Dialog {
        id: detail
        objectName: "jobDialog"
        modal: true
        title: "Auftragsdetails"
        anchors.centerIn: Overlay.overlay
        width: Math.min(610, window.width - 48)
        height: Math.min(window.height - 46, detailsContent.implicitHeight + 102)
        padding: 14
        background: Rectangle { color: surface; radius: 9; border.color: line }
        contentItem: ScrollView {
            id: detailsScroll
            objectName: "detailsScroll"
            clip: true
            contentWidth: availableWidth
            contentHeight: detailsContent.implicitHeight + 4
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ColumnLayout {
                id: detailsContent
                width: Math.max(1, detailsScroll.availableWidth - 4)
                spacing: 9
                Heading { text: selected.name || ""; Layout.fillWidth: true }
                Copy { text: selected.status || ""; font.weight: Font.DemiBold; Layout.fillWidth: true }
                Repeater {
                    model: selected.rows || []
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        Muted { text: modelData.label; Layout.fillWidth: true; Layout.preferredWidth: 2 }
                        Copy { text: modelData.value; Layout.fillWidth: true; Layout.preferredWidth: 1 }
                    }
                }
                Muted { text: selected.path || ""; Layout.fillWidth: true }
                Copy { text: selected.error || ""; color: warningColor; visible: text.length > 0; Layout.fillWidth: true }
                Muted { text: selected.note || ""; visible: text.length > 0; Layout.fillWidth: true }
            }
        }
        footer: Item {
            implicitHeight: detailActions.implicitHeight + 20
            Flow {
                id: detailActions
                x: 14; y: 10; width: parent.width - 28; spacing: 6
                AppActionButton { objectName: "openTranscriptButton"; text: "Transkript öffnen"; primary: true; visible: selected.openTranscript || false; enabled: !viewState.busy; onClicked: api.openTranscript() }
                AppActionButton { objectName: "revealTranscriptButton"; text: Qt.platform.os === "osx" ? "Im Finder zeigen" : "Im Explorer zeigen"; visible: selected.reveal || false; onClicked: api.revealOutput() }
                AppActionButton { text: "Erneut versuchen"; visible: selected.retry || false; enabled: !viewState.busy; onClicked: { api.retryJob(false); detail.close() } }
                AppActionButton { text: "Neu transkribieren"; visible: selected.repeat || false; enabled: !viewState.busy; onClicked: { api.retryJob(true); detail.close() } }
                AppActionButton { objectName: "closeJobDialog"; text: "Schließen"; onClicked: detail.close() }
            }
        }
    }

    Dialog {
        id: confirmClear
        objectName: "confirmClear"
        modal: true
        title: "Auftragsdatenbank vollständig zurücksetzen?"
        anchors.centerIn: Overlay.overlay
        width: Math.min(480, window.width - 48)
        standardButtons: Dialog.Cancel | Dialog.Ok
        background: Rectangle { color: surface; radius: 9; border.color: line }
        onAccepted: api.clearHistory()
        contentItem: Copy {
            text: "Alle Aufträge, die Warteschlange, der Dateibestand, gespeicherte Abbrüche und der Suchindex werden aus der lokalen Datenbank entfernt – unabhängig vom aktuellen Filter.\n\nAufnahmen und TXT-Dateien bleiben auf ihren Laufwerken erhalten. Bei aktiver Ordnerüberwachung werden die Ordner beim nächsten Intervall vollständig neu eingelesen. Vorhandene Transkripte erscheinen wieder im Bestand; Dateien ohne TXT werden neu eingereiht. Ordner- und Pauseneinstellungen bleiben erhalten."
        }
    }
}
