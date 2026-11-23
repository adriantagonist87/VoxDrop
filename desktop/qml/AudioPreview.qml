import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Pane {
    id: panel
    required property QtObject player
    property var audio: player.state
    property string extraError: ""
    padding: 12
    background: Rectangle { color: "#292b2a"; radius: 10; border.color: "#4a504c" }
    function timeText(milliseconds) {
        let seconds = Math.max(0, Math.floor(milliseconds / 1000))
        let hours = Math.floor(seconds / 3600)
        let minutes = Math.floor((seconds % 3600) / 60)
        return (hours ? hours + ":" : "") + String(minutes).padStart(2, "0") + ":" + String(seconds % 60).padStart(2, "0")
    }

    component IconButton: Button {
        id: button
        property string symbol
        property color ink: "#ededed"
        property color fill: "transparent"
        implicitWidth: 28; implicitHeight: 36
        padding: 3
        background: Rectangle {
            radius: 6
            color: button.fill !== "transparent" ? button.fill : button.down ? "#454f49" : button.hovered ? "#3a403c" : "transparent"
            border.color: button.visualFocus ? "#8ac6a5" : "transparent"
            border.width: button.visualFocus ? 2 : 0
            opacity: button.enabled ? 1 : .4
        }
        contentItem: Canvas {
            implicitWidth: 20; implicitHeight: 20
            property string shape: button.symbol
            property color ink: button.ink
            property bool enabledIcon: button.enabled
            onShapeChanged: requestPaint()
            onInkChanged: requestPaint()
            onEnabledIconChanged: requestPaint()
            onPaint: {
                let ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                ctx.save(); ctx.translate(width / 2, height / 2)
                ctx.strokeStyle = ink; ctx.fillStyle = ink; ctx.lineWidth = 2.4
                ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.globalAlpha = enabledIcon ? 1 : .4
                if (shape === "pause") { ctx.fillRect(-5, -7, 3.5, 14); ctx.fillRect(2, -7, 3.5, 14) }
                else if (shape === "play") { ctx.beginPath(); ctx.moveTo(-4,-8); ctx.lineTo(8,0); ctx.lineTo(-4,8); ctx.closePath(); ctx.fill() }
                else if (shape === "slower" || shape === "faster") {
                    let side = shape === "slower" ? -1 : 1
                    ctx.beginPath(); ctx.moveTo(-side*3,-6); ctx.lineTo(side*3,0); ctx.lineTo(-side*3,6); ctx.stroke()
                } else {
                    ctx.beginPath(); ctx.moveTo(-10,-3); ctx.lineTo(-6,-3); ctx.lineTo(0,-8); ctx.lineTo(0,8); ctx.lineTo(-6,3); ctx.lineTo(-10,3); ctx.closePath(); ctx.fill()
                    if (shape === "muted") {
                        ctx.beginPath(); ctx.moveTo(4,-4); ctx.lineTo(10,4); ctx.moveTo(10,-4); ctx.lineTo(4,4); ctx.stroke()
                    } else {
                        ctx.beginPath(); ctx.arc(0,0,6,-.8,.8); ctx.stroke()
                        ctx.beginPath(); ctx.arc(0,0,10,-.8,.8); ctx.stroke()
                    }
                }
                ctx.restore()
            }
        }
        ToolTip.visible: hovered
        ToolTip.text: Accessible.name
        ToolTip.delay: 600
    }
    component AudioSlider: Slider {
        id: control
        implicitHeight: 36
        padding: 2
        hoverEnabled: true
        background: Rectangle {
            x: control.leftPadding + control.handle.width / 2
            y: control.topPadding + control.availableHeight / 2 - height / 2
            width: control.availableWidth - control.handle.width; height: 3; radius: 1.5
            color: "#555b57"
            Rectangle { width: control.visualPosition * parent.width; height: parent.height; radius: 1.5; color: "#8ac6a5" }
        }
        handle: Rectangle {
            x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
            y: control.topPadding + control.availableHeight / 2 - height / 2
            implicitWidth: 28; implicitHeight: 32
            color: "transparent"
            Rectangle {
                anchors.centerIn: parent
                width: 4; height: control.pressed || control.hovered || control.visualFocus ? 16 : 12; radius: 2
                color: control.enabled ? "#a7cdb8" : "#777d79"
                border.width: control.visualFocus ? 1 : 0; border.color: "#ededed"
            }
        }
    }
    contentItem: ColumnLayout {
        spacing: 5
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            IconButton {
                objectName: "previewPlayButton"
                implicitWidth: 40; implicitHeight: 36
                symbol: panel.audio.playing ? "pause" : "play"
                fill: "#8ac6a5"; ink: "#14231c"
                Accessible.name: panel.audio.playing ? "Audio pausieren" : "Audio abspielen"
                enabled: panel.audio.available && !panel.audio.loading
                onClicked: panel.player.toggle()
            }
            AudioSlider {
                id: seek
                objectName: "previewSeekSlider"
                Accessible.name: "Wiedergabeposition"
                Layout.fillWidth: true; Layout.minimumWidth: 160
                property bool scrubbing: false
                property real scrubPosition: 0
                from: 0; to: Math.max(1, panel.audio.duration || 0)
                stepSize: 1000; snapMode: Slider.NoSnap
                enabled: panel.audio.seekable && !panel.audio.loading
                onPressedChanged: {
                    if (pressed) { scrubPosition = value; scrubbing = true }
                    else if (scrubbing) {
                        if (enabled) panel.player.seek(scrubPosition)
                        scrubbing = false
                    }
                }
                onValueChanged: {
                    if (scrubbing) scrubPosition = value
                    else if (!pressed && enabled && Math.abs(value - (panel.audio.position || 0)) > 50) panel.player.seek(value)
                }
                Binding { target: seek; property: "value"; when: !seek.scrubbing; value: panel.audio.position || 0 }
            }
            Label {
                objectName: "previewTime"
                text: (seek.scrubbing ? panel.timeText(seek.scrubPosition) : panel.audio.positionText) + " / " + panel.audio.durationText
                color: "#bdc4c0"; font.pixelSize: 12
                Layout.minimumWidth: implicitWidth
            }
            RowLayout {
                spacing: 0
                IconButton {
                    objectName: "previewSlowerButton"; symbol: "slower"
                    Accessible.name: "Langsamer abspielen"
                    enabled: panel.audio.rateAvailable && panel.audio.rate > .5
                    onClicked: panel.player.changeRate(-1)
                }
                Label {
                    objectName: "previewRate"
                    text: Number(panel.audio.rate).toFixed(panel.audio.rate % .5 === 0 ? 1 : 2) + "×"
                    color: "#ededed"; font.pixelSize: 13; font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter; Layout.minimumWidth: 48
                }
                IconButton {
                    objectName: "previewFasterButton"; symbol: "faster"
                    Accessible.name: "Schneller abspielen"
                    enabled: panel.audio.rateAvailable && panel.audio.rate < 3
                    onClicked: panel.player.changeRate(1)
                }
            }
            IconButton {
                objectName: "previewMuteButton"
                symbol: panel.audio.muted || panel.audio.volume === 0 ? "muted" : "speaker"
                Accessible.name: panel.audio.muted ? "Ton einschalten" : "Stummschalten"
                onClicked: panel.player.toggleMute()
            }
            AudioSlider {
                id: volume
                objectName: "previewVolumeSlider"
                Accessible.name: "Lautstärke der Audiowiedergabe"
                Layout.preferredWidth: 96; Layout.minimumWidth: 80
                from: 0; to: 100; stepSize: 5; snapMode: Slider.NoSnap
                Binding { target: volume; property: "value"; value: panel.audio.volume }
                onValueChanged: if (panel.player && Math.abs(value - panel.audio.volume) > .01) panel.player.setVolume(value)
            }
        }
        Label {
            objectName: "previewStatus"
            text: panel.audio.error || panel.extraError || (panel.audio.loading || !panel.audio.available ? "Tonspur wird geladen …" : "")
            visible: text.length > 0
            color: panel.audio.error || panel.extraError ? "#ffb4ad" : "#bdc4c0"
            wrapMode: Text.Wrap; Layout.fillWidth: true
            font.pixelSize: 12
        }
    }
}
