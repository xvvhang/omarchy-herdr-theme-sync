import QtQuick
import Quickshell.Io

Item {
    property var shell: null
    property var manifest: null
    property var settings: ({})

    Process {
        id: sync
        command: ["python", decodeURIComponent(Qt.resolvedUrl("sync.py").toString().replace(/^file:\/\//, "")), "sync"]
        stderr: StdioCollector {
            onStreamFinished: if (text.trim()) console.warn("Herdr Theme Sync:", text.trim())
        }
    }
    Component.onCompleted: sync.running = true
}
