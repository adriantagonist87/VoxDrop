import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RowLayout {
    id: control
    signal stopRequested()
    property bool showLabel: true
    required property var api
    required property var viewState
    Layout.preferredHeight: 44
    Layout.minimumHeight: 44
    Layout.maximumHeight: 44
    spacing: 10
    Button {
        id: playback
        objectName: "queuePlaybackButton"
        Layout.preferredWidth: 44
        Layout.minimumWidth: 44
        Layout.maximumWidth: 44
        Layout.preferredHeight: 44
        Layout.minimumHeight: 44
        Layout.maximumHeight: 44
        property bool stopMode: Boolean(viewState.processingActive)
        text: viewState.processingStopping ? "Wird gestoppt …" : stopMode ? "STOPP" : "STARTEN"
        enabled: stopMode ? Boolean(viewState.canStopProcessing) : Boolean(viewState.canStartProcessing)
        Accessible.name: stopMode ? 'Warteschlange und Transkription stoppen' : 'Warteschlange und Transkription starten'
        Accessible.description: 'Stopp öffnet die Auswahl: sofort stoppen oder die laufende Transkription fertigstellen und danach pausieren.'
        ToolTip.visible: hovered
        ToolTip.text: stopMode ? 'Stoppoptionen öffnen.\nWarteschlange bleibt erhalten.' : 'Warteschlange starten oder fortsetzen.\nÜberwachung ist separat schaltbar.'
        ToolTip.delay: 700
        contentItem: Item {
            implicitWidth: 20
            implicitHeight: 20
            Canvas {
                anchors.centerIn: parent
                width: 20
                height: 20
                property bool square: playback.stopMode
                property color ink: playback.stopMode ? '#ffffff' : '#14231c'
                onSquareChanged: requestPaint()
                onInkChanged: requestPaint()
                onPaint: {
                    var ctx = getContext('2d')
                    ctx.clearRect(0, 0, width, height)
                    ctx.fillStyle = ink
                    if (square) ctx.fillRect(2, 2, 16, 16)
                    else {
                        ctx.beginPath(); ctx.moveTo(3, 1); ctx.lineTo(19, 10); ctx.lineTo(3, 19); ctx.closePath(); ctx.fill()
                    }
                }
            }
        }
        background: Rectangle {
            radius: 4
            color: playback.stopMode ? (playback.down ? '#8f2530' : '#b5303a') : (playback.down ? '#6fa98b' : '#8ac6a5')
            opacity: playback.enabled ? 1 : .65
            border.width: playback.activeFocus ? 2 : 1
            border.color: playback.activeFocus ? '#ffffff' : playback.stopMode ? '#d96770' : '#a7dec0'
        }
        onClicked: stopMode ? control.stopRequested() : api.startProcessing()
    }
    Text {
        visible: parent.showLabel
        Layout.fillWidth: true
        text: viewState.processingStopping ? 'Wird gestoppt …' : playback.stopMode ? 'Stopp' : 'Starten'
        color: '#ededed'
        font.pixelSize: 14
        wrapMode: Text.WordWrap
    }
}
