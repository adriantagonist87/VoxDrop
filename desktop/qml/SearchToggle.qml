import QtQuick
import QtQuick.Controls.Basic

Button {
    id: button
    implicitWidth: 30
    implicitHeight: 30
    padding: 6
    ToolTip.visible: hovered
    ToolTip.text: Accessible.name
    contentItem: Item {
        implicitWidth: 18; implicitHeight: 18
        Rectangle { x: 2; y: 1; width: 11; height: 11; radius: 6; color: 'transparent'; border.color: '#ededee'; border.width: 2 }
        Rectangle { x: 10; y: 12; width: 8; height: 2; radius: 1; rotation: 45; color: '#ededee' }
    }
    background: Rectangle {
        radius: 5
        color: button.checked ? '#456653' : button.down ? '#414141' : button.hovered ? '#353535' : '#292929'
        border.color: button.activeFocus ? '#8ac6a5' : '#454545'
        border.width: button.activeFocus ? 2 : 1
    }
}
