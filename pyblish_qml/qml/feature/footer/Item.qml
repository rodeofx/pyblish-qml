import QtQuick 2.3

import "controller.js" as Ctrl
import "../generic" as Generic
import "../service/model.js" as Model


Generic.Rectangle {
    id: root

    property alias message: message

    signal publish

    width: 200
    height: Model.size.footerHeight

    Message {
        id: message
        anchors.verticalCenter: parent.verticalCenter
    }

    Row {
        id: headerButtons

        anchors {
            right: parent.right
            top: parent.top
            bottom: parent.bottom
            margins: Model.margins.main
        }

        spacing: Model.margins.alt

         Generic.Button {
            id: publishButton
            source: Model.image.publish
            width: 30
            height: 30

            onClicked: root.publish();
        }
    }
}