import QtQuick 2.0
import Pyblish 0.1


Item {
    id: root

    height: 25
    width: parent.width

    property bool checkState: true
    property bool hideState: text == "Collect"
    property string text

    signal labelClicked
    signal sectionClicked

    Rectangle {
        color: "#333"
        border.width: 1
        border.color: "#222"
        anchors.fill: parent
        anchors.margins: 2
    }

    Rectangle {
        id: iconBackground
        anchors.fill: parent
        anchors.margins: 3
        anchors.rightMargin: parent.width - height
        opacity: ma.containsPress ? 0.15 :
                 ma.containsMouse ? 0.10 : 0
    }

    Rectangle {
        id: labelBackground
        anchors.fill: parent
        anchors.margins: 3
        anchors.leftMargin: height
        opacity: labelMa.containsPress ? 0.15 :
                 labelMa.containsMouse ? 0.10 : 0
    }

    AwesomeIcon {
        name: "minus"
        opacity: !root.hideState ? 0.5: 0

        anchors.verticalCenter: iconBackground.verticalCenter
        anchors.horizontalCenter: iconBackground.horizontalCenter

        size: 10
    }

    AwesomeIcon {
        name: "plus"
        opacity: root.hideState ? 0.5: 0

        anchors.verticalCenter: iconBackground.verticalCenter
        anchors.horizontalCenter: iconBackground.horizontalCenter

        size: 10
    }

    Label {
        id: label
        text: root.text
        opacity: 0.5
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: iconBackground.right
        anchors.leftMargin: 5
    }

    MouseArea {
        id: ma
        anchors.fill: iconBackground
        hoverEnabled: true
        onClicked: root.sectionClicked()
    }

    MouseArea {
        id: labelMa
        anchors.fill: labelBackground
        hoverEnabled: true
        onClicked: root.labelClicked()
    }
}
