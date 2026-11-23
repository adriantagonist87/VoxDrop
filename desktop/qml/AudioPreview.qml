import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Frame {
    id: panel
    required property QtObject player
    property var audio: player.state
    padding: 10
    background: Rectangle { color: "#202322"; radius: 6; border.color: "#3b403d" }
    contentItem: ColumnLayout {
        spacing: 6
        Label { text: "Originaldatei anhören"; color: "#ededed"; font.bold: true }
        Label {
            text: panel.audio.available ? panel.audio.name : "Mit „Originaldatei abspielen“ die Tonspur laden."
            color: "#aab0ad"; wrapMode: Text.WrapAnywhere; Layout.fillWidth: true
        }
        RowLayout {
            Layout.fillWidth: true
            Button {
                objectName: "previewPlayButton"
                text: panel.audio.playing ? "Pause" : "Play"
                Accessible.name: panel.audio.playing ? "Audio pausieren" : "Audio abspielen"
                enabled: panel.audio.available && !panel.audio.loading
                onClicked: panel.player.toggle()
            }
            Slider {
                id: seek
                objectName: "previewSeekSlider"
                Accessible.name: "Wiedergabeposition"
                Layout.fillWidth: true
                from: 0; to: Math.max(1, panel.audio.duration || 0)
                enabled: panel.audio.seekable && !panel.audio.loading
                onValueChanged: if (enabled && Math.abs(value - (panel.audio.position || 0)) > 50) panel.player.seek(value)
                Binding { target: seek; property: "value"; when: !seek.pressed; value: panel.audio.position || 0 }
            }
            Label {
                objectName: "previewTime"
                text: panel.audio.positionText + " / " + panel.audio.durationText
                color: "#ededed"; Layout.minimumWidth: 90
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Label { text: "Lautstärke"; color: "#aab0ad" }
            Slider {
                objectName: "previewVolumeSlider"
                Accessible.name: "Lautstärke der Audiowiedergabe"
                Layout.fillWidth: true
                from: 0; to: 100; value: panel.audio.volume
                onValueChanged: if (panel.player && Math.abs(value - panel.audio.volume) > 0.01) panel.player.setVolume(value)
            }
            Label { text: Math.round(panel.audio.volume) + " %"; color: "#ededed"; Layout.minimumWidth: 40 }
        }
        Label {
            objectName: "previewStatus"
            text: panel.audio.error || (panel.audio.loading ? "Tonspur wird geladen …" : "")
            visible: text.length > 0
            color: panel.audio.error ? "#e8ae8e" : "#aab0ad"
            wrapMode: Text.Wrap; Layout.fillWidth: true
        }
    }
}
