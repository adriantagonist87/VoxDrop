import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: playback
    required property var api
    required property var viewState
    objectName: "queuePlaybackButton"
    Layout.fillWidth: true
    Layout.preferredHeight: 66
    property bool stopMode: Boolean(viewState.processingActive)
    text: viewState.processingStopping ? "Wird gestoppt …" : stopMode ? "STOPP" : "STARTEN"
    enabled: stopMode ? Boolean(viewState.canStopProcessing) : Boolean(viewState.canStartProcessing)
    Accessible.name: stopMode ? 'Warteschlange und Transkription stoppen' : 'Warteschlange und Transkription starten'
    Accessible.description: 'Stopp erhält die Warteschlange. Eine unterbrochene Erkennung beginnt beim Fortsetzen neu.'
    ToolTip.visible: hovered
    ToolTip.text: stopMode ? 'Aktuelle Erkennung stoppen und Warteschlange anhalten. Fertige Ergebnisse werden noch sicher gespeichert.' : 'Warteschlange starten oder fortsetzen, auch bei ausgeschalteter Ordnerüberwachung.'
    contentItem: RowLayout {
        spacing: 12
        Item { Layout.fillWidth: true }
        Canvas {
            id: playbackIcon
            Layout.preferredWidth: 25
            Layout.preferredHeight: 25
            property bool square: playback.stopMode
            property color ink: playback.stopMode ? '#ffffff' : '#14231c'
            onSquareChanged: requestPaint()
            onInkChanged: requestPaint()
            onPaint: {
                var ctx = getContext('2d')
                ctx.clearRect(0, 0, width, height)
                ctx.fillStyle = ink
                if (square) ctx.fillRect(3, 3, 19, 19)
                else {
                    ctx.beginPath(); ctx.moveTo(4, 1); ctx.lineTo(24, 12.5); ctx.lineTo(4, 24); ctx.closePath(); ctx.fill()
                }
            }
        }
        Text {
            text: playback.text
            color: playback.stopMode ? '#ffffff' : '#14231c'
            font.pixelSize: viewState.processingStopping ? 16 : 20
            font.bold: true
        }
        Item { Layout.fillWidth: true }
    }
    background: Rectangle {
        radius: 8
        color: playback.stopMode ? (playback.down ? '#8f2530' : '#b5303a') : (playback.down ? '#6fa98b' : '#8ac6a5')
        opacity: playback.enabled ? 1 : .65
        border.width: playback.activeFocus ? 2 : 1
        border.color: playback.activeFocus ? '#ffffff' : playback.stopMode ? '#d96770' : '#a7dec0'
    }
    onClicked: stopMode ? api.stopProcessing() : api.startProcessing()
}
