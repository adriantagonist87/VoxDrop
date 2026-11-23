import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Pane {
    id: panel
    required property QtObject player
    property var audio: player.state
    property string extraError: ""
    padding: 14
    background: Rectangle { color: "#ffffff"; radius: 14 }

    component IconButton: Button {
        id: button
        property string symbol
        property color ink: "#171717"
        property color fill: "transparent"
        implicitWidth: 28; implicitHeight: 36
        padding: 3
        background: Rectangle {
            radius: height / 2
            color: button.fill !== "transparent" ? button.fill : button.down ? "#e2e2e2" : button.hovered ? "#f0f0f0" : "transparent"
            border.color: button.visualFocus ? "#e60000" : "transparent"
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
        implicitHeight: 32
        padding: 6
        background: Rectangle {
            x: control.leftPadding; y: control.topPadding + control.availableHeight / 2 - height / 2
            width: control.availableWidth; height: 4; radius: 2
            color: "#c9c9c9"
            Rectangle { width: control.visualPosition * parent.width; height: parent.height; radius: 2; color: "#e60000" }
        }
        handle: Rectangle {
            x: control.leftPadding + control.visualPosition * (control.availableWidth - width)
            y: control.topPadding + control.availableHeight / 2 - height / 2
            implicitWidth: 18; implicitHeight: 18; radius: 9
            color: control.enabled ? "#e60000" : "#aaaaaa"
            border.width: control.visualFocus ? 2 : 0; border.color: "#171717"
        }
    }
    contentItem: ColumnLayout {
        spacing: 5
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            IconButton {
                objectName: "previewPlayButton"
                implicitWidth: 44; implicitHeight: 44
                symbol: panel.audio.playing ? "pause" : "play"
                fill: "#171717"; ink: "#ffffff"
                Accessible.name: panel.audio.playing ? "Audio pausieren" : "Audio abspielen"
                enabled: panel.audio.available && !panel.audio.loading
                onClicked: panel.player.toggle()
            }
            AudioSlider {
                id: seek
                objectName: "previewSeekSlider"
                Accessible.name: "Wiedergabeposition"
                Layout.fillWidth: true; Layout.minimumWidth: 160
                from: 0; to: Math.max(1, panel.audio.duration || 0)
                enabled: panel.audio.seekable && !panel.audio.loading
                onValueChanged: if (enabled && Math.abs(value - (panel.audio.position || 0)) > 50) panel.player.seek(value)
                Binding { target: seek; property: "value"; when: !seek.pressed; value: panel.audio.position || 0 }
            }
            Label {
                objectName: "previewTime"
                text: panel.audio.positionText + " / " + panel.audio.durationText
                color: "#505050"; font.pixelSize: 12
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
                    color: "#171717"; font.pixelSize: 15; font.weight: Font.DemiBold
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
                from: 0; to: 100
                Binding { target: volume; property: "value"; value: panel.audio.volume }
                onValueChanged: if (panel.player && Math.abs(value - panel.audio.volume) > .01) panel.player.setVolume(value)
            }
        }
        Label {
            objectName: "previewStatus"
            text: panel.audio.error || panel.extraError || (panel.audio.loading || !panel.audio.available ? "Tonspur wird geladen …" : "")
            visible: text.length > 0
            color: panel.audio.error || panel.extraError ? "#a82525" : "#505050"
            wrapMode: Text.Wrap; Layout.fillWidth: true
            font.pixelSize: 12
        }
    }
}
