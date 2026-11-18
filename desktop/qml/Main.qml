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
    readonly property var initialColumns: api.columnWidths()
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
                text: "Ordner zur Warteschlange hinzufügen"
            }
        }
    }

    SplitView {
        id: split
        objectName: "columns"
        anchors.fill: parent
        handle: Rectangle {
            objectName: "columnHandle"
            implicitWidth: 8
            color: SplitHandle.pressed ? "#456653" : SplitHandle.hovered ? "#393939" : canvas
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 1
                height: parent.height
                color: parent.SplitHandle.pressed || parent.SplitHandle.hovered ? accent : line
            }
        }
        onResizingChanged: {
            if (!resizing)
                api.saveColumnWidths(Math.round(settingsPane.width), Math.round(historyPane.width))
        }

        Rectangle {
            id: settingsPane
            objectName: "settingsPane"
            color: sidebar
            SplitView.minimumWidth: 285
            SplitView.maximumWidth: 620
            SplitView.preferredWidth: window.initialColumns.left

            ScrollView {
                id: settingsScroll
                objectName: "settingsScroll"
                anchors.fill: parent
                clip: true
                contentWidth: availableWidth
                contentHeight: form.implicitHeight + 40
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                ColumnLayout {
                    id: form
                    objectName: "settingsForm"
                    x: 18
                    y: 19
                    width: Math.max(1, settingsScroll.availableWidth - 36)
                    spacing: 10
                    Heading { text: "Transkriptionsdienst"; Layout.fillWidth: true }
                    RowLayout {
                        spacing: 8
                        Rectangle { width: 7; height: 7; radius: 4; color: viewState.running ? accent : "#818186" }
                        Copy { text: viewState.service || "Dienst aus"; Layout.fillWidth: true }
                    }
                    Toggle {
                        text: "Automatisch bei Anmeldung starten"
                        Layout.fillWidth: true
                        enabled: viewState.ready && !viewState.busy
                        checked: viewState.autostart
                        onToggled: api.setAutostart(checked)
                    }
                    Toggle {
                        text: "Ordnerüberwachung aktiv"
                        Layout.fillWidth: true
                        enabled: viewState.ready
                        checked: settings.monitoring
                        onToggled: api.setSetting("monitoring", checked)
                    }
                    Rectangle { Layout.fillWidth: true; height: 1; color: line }
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
                    Rectangle { Layout.fillWidth: true; height: 1; color: line }
                    Heading { text: "Transkription"; font.pixelSize: 14 }
                    Copy { text: "Modell"; Layout.fillWidth: true }
                    Picker {
                        objectName: "modelPicker"
                        Layout.fillWidth: true
                        Accessible.name: "Transkriptionsmodell"
                        model: ["Qwen3-ASR 1.7B", "Whisper Large v3 Turbo"]
                        currentIndex: settings.model === "large-v3-turbo" ? 1 : 0
                        onActivated: index => api.setSetting("model", ["qwen3-asr-1.7b", "large-v3-turbo"][index])
                    }
                    Muted {
                        Layout.fillWidth: true
                        text: viewState.modelsReady ? "Modelle installiert" : "Modell-Setup erforderlich"
                    }
                    AppActionButton {
                        Layout.fillWidth: true
                        text: "Modelle herunterladen"
                        visible: !viewState.modelsReady
                        enabled: viewState.ready && !viewState.busy
                        onClicked: api.downloadModels()
                    }
                    Muted {
                        Layout.fillWidth: true
                        text: "Modellspeicher: " + api.modelLocation
                    }
                    TaskProgress {
                        Layout.fillWidth: true
                        visible: viewState.downloading
                        indeterminate: true
                    }
                    Muted {
                        Layout.fillWidth: true
                        visible: viewState.waitingForNetwork
                        color: warningColor
                        text: "Netzwerkzugriff verweigert (10013). Bestätige eine eventuell angezeigte Freigabeanfrage selbst. Ohne sichtbare Anfrage: Protokoll öffnen. Der Download wird automatisch erneut geprüft."
                    }
                    AppActionButton {
                        Layout.fillWidth: true
                        visible: viewState.waitingForNetwork
                        objectName: "cancelNetworkWait"
                        text: "Warten abbrechen"
                        onClicked: api.cancelNetworkWait()
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Copy { text: "Sprache"; Layout.fillWidth: true }
                        Picker {
                            Layout.preferredWidth: 164
                            Accessible.name: "Sprache"
                            model: ["Automatisch", "Deutsch", "Englisch"]
                            currentIndex: ["auto", "de", "en"].indexOf(settings.language)
                            onActivated: index => api.setSetting("language", ["auto", "de", "en"][index])
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Copy { text: "Rechengerät"; Layout.fillWidth: true }
                        Picker {
                            Layout.preferredWidth: 164
                            Accessible.name: "Rechengerät"
                            model: [api.gpuName, "CPU"]
                            currentIndex: settings.hardware === "cpu" ? 1 : 0
                            onActivated: index => api.setSetting("hardware", [api.gpuValue, "cpu"][index])
                        }
                    }
                    Copy {
                        Layout.fillWidth: true
                        text: "GPU-Arbeitsbudget: " + Math.round(gpuBudgetSlider.value) + " %"
                    }
                    Slider {
                        id: gpuBudgetSlider
                        objectName: "gpuBudgetSlider"
                        Layout.fillWidth: true
                        from: 10
                        to: 100
                        stepSize: 5
                        snapMode: Slider.SnapAlways
                        value: settings.gpu_budget_percent || 100
                        enabled: viewState.ready && !viewState.busy && api.gpuValue === "cuda" && settings.hardware === "cuda"
                        Accessible.name: "GPU-Arbeitsbudget in Prozent"
                        onMoved: gpuBudgetSave.restart()
                        Timer {
                            id: gpuBudgetSave
                            interval: 250
                            onTriggered: api.setGpuBudget(Math.round(gpuBudgetSlider.value))
                        }
                    }
                    Muted {
                        Layout.fillWidth: true
                        text: api.gpuValue !== "cuda" ? "Derzeit für NVIDIA-GPUs unter Windows verfügbar." :
                            "Sofort gespeichert, auch während der Verarbeitung. Weniger Last bedeutet längere Laufzeit. Kurze Lastspitzen und der Grafikspeicherbedarf bleiben bestehen."
                    }
                    Toggle {
                        Layout.fillWidth: true
                        text: "Lange Stille überspringen"
                        checked: settings.skip_silence
                        onToggled: api.setSetting("skip_silence", checked)
                    }
                    Toggle {
                        Layout.fillWidth: true
                        text: "Sprechererkennung"
                        checked: settings.speakers
                        onToggled: api.setSetting("speakers", checked)
                    }
                    Toggle {
                        Layout.fillWidth: true
                        text: "Mehrere Prüfdurchgänge (DOVER-Lap)"
                        checked: settings.dover_lap
                        enabled: settings.speakers
                        onToggled: api.setSetting("dover_lap", checked)
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Copy { text: "Sprecherzahl"; Layout.fillWidth: true }
                        Picker {
                            Layout.preferredWidth: 164
                            Accessible.name: "Sprecherzahl"
                            model: ["Automatisch", "1", "2", "3", "4", "5", "6", "7", "8"]
                            currentIndex: settings.speaker_count || 0
                            enabled: settings.speakers
                            onActivated: index => api.setSetting("speaker_count", index || null)
                        }
                    }
                    Rectangle { Layout.fillWidth: true; height: 1; color: line }
                    RowLayout {
                        Layout.fillWidth: true
                        AppActionButton {
                            objectName: "saveButton"
                            text: "Speichern"
                            primary: true
                            Layout.fillWidth: true
                            enabled: viewState.ready && !viewState.busy
                            onClicked: api.save(false)
                        }
                        AppActionButton {
                            text: "Dienst starten"
                            Layout.fillWidth: true
                            enabled: viewState.ready && !viewState.busy
                            visible: !viewState.running
                            onClicked: api.save(true)
                        }
                    }
                    Muted {
                        objectName: "feedback"
                        Layout.fillWidth: true
                        visible: text.length > 0
                        text: viewState.message || ""
                        color: viewState.messageError ? warningColor : muted
                    }
                    AppActionButton { text: "Protokoll öffnen"; visible: viewState.logAvailable; onClicked: api.openLog() }
                    AppActionButton {
                        text: "Erneut prüfen"
                        visible: !viewState.ready && !viewState.busy && viewState.messageError
                        onClicked: api.retryPreparation()
                    }
                }
            }
        }

        Rectangle {
            id: workPane
            objectName: "workPane"
            color: canvas
            SplitView.minimumWidth: 265
            SplitView.fillWidth: true
                ColumnLayout {
                    id: work
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 12
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: warningBox.implicitHeight + 22
                        visible: viewState.warnings && viewState.warnings.length > 0
                        radius: 7
                        color: "#352825"
                        border.color: "#68423d"
                        ColumnLayout {
                            id: warningBox
                            x: 11
                            y: 11
                            width: parent.width - 22
                            spacing: 7
                            Heading { text: "Überwachte Ordner prüfen"; color: warningColor; font.pixelSize: 14; Layout.fillWidth: true }
                            Repeater {
                                model: viewState.warnings || []
                                delegate: Copy {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    color: warningColor
                                    text: modelData.path + "\n" + modelData.error
                                }
                            }
                        }
                    }
                    Heading { text: "Aktueller Auftrag"; Layout.fillWidth: true }
                    Muted { text: viewState.ready ? "Kein Auftrag in Bearbeitung" : "VoxDrop wird vorbereitet …"; visible: !viewState.current.name; Layout.fillWidth: true }
                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: Boolean(viewState.current.name)
                        spacing: 8
                        Copy { text: viewState.current.name || ""; font.weight: Font.DemiBold; font.pixelSize: 15; Layout.fillWidth: true }
                        Copy { text: viewState.current.phase || ""; Layout.fillWidth: true }
                        TaskProgress {
                            Layout.fillWidth: true
                            indeterminate: viewState.current.progress === null || viewState.current.progress === undefined
                            value: viewState.current.progress || 0
                        }
                        Muted {
                            Layout.fillWidth: true
                            text: viewState.current.progress === null || viewState.current.progress === undefined ? "Verarbeitung läuft. Für diese Phase ist noch keine Prozentangabe verfügbar." :
                                Math.round(viewState.current.progress * 100) + " %"
                            visible: text.length > 0
                        }
                        Muted { text: viewState.current.elapsed ? "Laufzeit  " + viewState.current.elapsed : ""; Layout.fillWidth: true }
                        Copy { text: "Modell  " + (viewState.current.model || ""); Layout.fillWidth: true }
                        Copy { text: "Rechengerät  " + (viewState.current.hardware || ""); Layout.fillWidth: true }
                        AppActionButton {
                            objectName: "cancelCurrentButton"
                            text: "Aktuelle Transkription abbrechen"
                            enabled: !viewState.busy && Boolean(viewState.current.canCancel)
                            onClicked: api.cancelJob(viewState.current.id)
                        }
                    }
                    Rectangle { Layout.fillWidth: true; height: 1; color: line }
                    QueuePane { api: window.api; viewState: window.viewState; Layout.fillWidth: true; Layout.fillHeight: true }
                    Muted {
                        text: viewState.dropMessage || "Dateien oder Ordner für eine einmalige Transkription hier ablegen."
                        color: viewState.dropError ? warningColor : muted
                        Layout.fillWidth: true
                    }
                }
        }

        Rectangle {
            id: historyPane
            objectName: "historyPane"
            color: sidebar
            SplitView.minimumWidth: 325
            SplitView.maximumWidth: 720
            SplitView.preferredWidth: window.initialColumns.right
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 10
                RowLayout {
                    Layout.fillWidth: true
                    Heading { text: "Verlauf"; Layout.fillWidth: true }
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
                    AppActionButton { objectName: 'clearHistoryButton'; text: "Verlauf leeren …"; enabled: viewState.canClear; onClicked: confirmClear.open() }
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
                    model: api.historyItems
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    delegate: ItemDelegate {
                        id: job
                        required property var modelData
                        width: ListView.view.width - (jobs.ScrollBar.vertical.visible ? 10 : 0)
                        padding: 10
                        implicitHeight: jobInfo.implicitHeight + 20
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
                            spacing: 5
                            Copy { text: job.modelData.name; font.pixelSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true }
                            Muted { text: "Neutranskription"; visible: job.modelData.repeat; Layout.fillWidth: true }
                            Muted { text: job.modelData.path; Layout.fillWidth: true }
                            Copy { text: "Gesamtdauer der Audiodatei: " + job.modelData.audio; Layout.fillWidth: true }
                            Copy { text: "Transkriptionsbeginn: " + job.modelData.start; Layout.fillWidth: true }
                            Copy { text: "Transkriptionsdauer (gesamt): " + job.modelData.elapsed; Layout.fillWidth: true }
                            Copy { text: "Transkription fertiggestellt: " + window.completionTime(job.modelData); Layout.fillWidth: true }
                            RowLayout {
                                Layout.fillWidth: true
                                Muted { text: job.modelData.status; color: job.modelData.error ? warningColor : muted; Layout.fillWidth: true }
                                Muted { text: job.modelData.updated }
                            }
                        }
                    }
                }
            }
        }
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
        footer: RowLayout {
            spacing: 6
            AppActionButton { text: "Erneut versuchen"; visible: selected.retry || false; enabled: !viewState.busy; onClicked: { api.retryJob(false); detail.close() } }
            AppActionButton { text: "Neu transkribieren"; visible: selected.repeat || false; enabled: !viewState.busy; onClicked: { api.retryJob(true); detail.close() } }
            AppActionButton { objectName: "openTranscriptButton"; text: "Transkript öffnen"; visible: selected.openTranscript || false; enabled: !viewState.busy; onClicked: api.openTranscript() }
            AppActionButton { text: Qt.platform.os === "osx" ? "Im Finder zeigen" : "Im Explorer zeigen"; visible: selected.reveal || false; onClicked: api.revealOutput() }
            Item { Layout.fillWidth: true }
            AppActionButton { text: "Schließen"; onClicked: detail.close() }
        }
    }

    Dialog {
        id: confirmClear
        objectName: "confirmClear"
        modal: true
        title: "Alle Auftrags- und Suchdaten leeren?"
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
