import QtQuick
import Quickshell
import Quickshell.Io

Item {
  id: root

  property bool opened: false
  property var strokes: []
  property var currentStroke: []
  property var candidates: []
  property int sel: 0
  property string statusText: "Omarchy Handwrite board"

  readonly property int winW: 470
  readonly property int winH: 430

  // Directory this plugin lives in, so the backend + venv resolve wherever the
  // plugin is installed (not hardcoded to the dev checkout).
  readonly property string pluginDir: Qt.resolvedUrl(".").toString().slice(7)

  // -- IPC to the Python backend (stdio) --------------------------------
  function send(cmd) {
    backend.write(JSON.stringify(cmd) + "\n")
  }

  function handle(msg) {
    switch (msg.type) {
      case "ready":
        statusText = "可開始書寫"
        // Re-send show/hide in case the open()/close() message raced the
        // backend process startup and was dropped by the `running` guard.
        if (opened) send({ type: "show" })
        break
      case "down":
        canvas.beginStroke(msg.x, msg.y)
        break
      case "move":
        canvas.appendPoint(msg.x, msg.y)
        break
      case "up":
        canvas.endStroke()
        break
      case "candidates":
        candidates = msg.chars
        sel = 0
        break
      case "inserted":
        canvas.clear()
        candidates = []
        break
      case "clear_surface":
        canvas.clear()
        break
      case "status":
        statusText = msg.text
        break
    }
  }

  // Shell summon contract: `summon <id>` calls open(), `hide <id>` calls close().
  function open(payloadJson) {
    opened = true
  }
  function close() {
    opened = false
  }
  function toggle() { opened ? close() : open("") }
  function confirm() { send({ type: "confirm" }) }

  // Move the candidate highlight by delta (wraps), keeping the backend in sync.
  function selectBy(delta) {
    if (candidates.length === 0) return
    sel = (sel + delta + candidates.length) % candidates.length
    send({ type: "select", index: sel })
  }
  function selectLeft() { selectBy(-1) }
  function selectRight() { selectBy(1) }

  onOpenedChanged: {
    if (opened) send({ type: "show" })
    else send({ type: "hide" })
  }

  // -- backend process ---------------------------------------------------
  Process {
    id: backend
    running: true
    command: [root.pluginDir + ".venv/bin/python", root.pluginDir + "backend.py"]
    workingDirectory: root.pluginDir
    stdinEnabled: true
    stdout: SplitParser {
      splitMarker: "\n"
      onRead: (data) => {
        try { root.handle(JSON.parse(data)) } catch (e) {}
      }
    }
    stderr: SplitParser {
      splitMarker: "\n"
      onRead: (data) => console.log("[omarchy-write]", data)
    }
  }

  // -- floating window ---------------------------------------------------
  FloatingWindow {
    id: win
    visible: root.opened
    implicitWidth: root.winW
    implicitHeight: root.winH
    minimumSize: Qt.size(root.winW, root.winH)
    maximumSize: Qt.size(root.winW, root.winH)
    title: "Omarchy Handwrite board"

    Rectangle {
      anchors.fill: parent
      radius: 14
      color: "#1e1e2e"
      border.color: "#45475a"
      border.width: 1

      // header (drag handle)
      Rectangle {
        id: header
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 40
        color: "transparent"
        MouseArea {
          anchors.fill: parent
          onPressed: win.startSystemMove()
        }
        Text {
          anchors.centerIn: parent
          text: "⠿ Omarchy Handwrite board · 繁簡手寫"
          color: "#cdd6f4"
          font.pixelSize: 14
        }
      }

      // clear button
      Rectangle {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 8
        width: 30
        height: 30
        radius: 6
        color: "#313244"
        Text { anchors.centerIn: parent; text: "✕"; color: "#cdd6f4"; font.pixelSize: 15 }
        MouseArea {
          anchors.fill: parent
          onClicked: send({ type: "clear" })
        }
      }

      // writing surface
      Canvas {
        id: canvas
        anchors.top: header.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: candRow.top
        anchors.margins: 10

        function beginStroke(nx, ny) {
          root.currentStroke = [{ x: nx * width, y: ny * height }]
          requestPaint()
        }
        function appendPoint(nx, ny) {
          root.currentStroke.push({ x: nx * width, y: ny * height })
          requestPaint()
        }
        function endStroke() {
          if (root.currentStroke.length > 0) root.strokes.push(root.currentStroke)
          root.currentStroke = []
          requestPaint()
        }
        function clear() {
          root.strokes = []
          root.currentStroke = []
          requestPaint()
        }

        onPaint: {
          var ctx = getContext("2d")
          ctx.fillStyle = "#313244"
          ctx.fillRect(0, 0, width, height)
          ctx.strokeStyle = "#cdd6f4"
          ctx.lineWidth = 5
          ctx.lineCap = "round"
          ctx.lineJoin = "round"

          var s, p, pts
          for (s = 0; s < root.strokes.length; s++) {
            pts = root.strokes[s]
            if (pts.length < 2) continue
            ctx.beginPath()
            ctx.moveTo(pts[0].x, pts[0].y)
            for (p = 1; p < pts.length; p++) ctx.lineTo(pts[p].x, pts[p].y)
            ctx.stroke()
          }
          if (root.currentStroke.length >= 2) {
            ctx.beginPath()
            ctx.moveTo(root.currentStroke[0].x, root.currentStroke[0].y)
            for (p = 1; p < root.currentStroke.length; p++)
              ctx.lineTo(root.currentStroke[p].x, root.currentStroke[p].y)
            ctx.stroke()
          } else if (root.currentStroke.length === 1) {
            ctx.beginPath()
            ctx.arc(root.currentStroke[0].x, root.currentStroke[0].y, ctx.lineWidth / 2, 0, 2 * Math.PI)
            ctx.fill()
          }
        }

        // mouse drawing (also used for testing); the touchpad is primary.
        MouseArea {
          anchors.fill: parent
          onPressed: (mouse) => send({ type: "stroke", phase: "down", x: mouse.x / parent.width, y: mouse.y / parent.height })
          onPositionChanged: (mouse) => send({ type: "stroke", phase: "move", x: mouse.x / parent.width, y: mouse.y / parent.height })
          onReleased: send({ type: "stroke", phase: "up" })
        }
      }

      // candidate row
      Row {
        id: candRow
        anchors.bottom: status.top
        anchors.horizontalCenter: parent.horizontalCenter
        height: 50
        spacing: 6
        Repeater {
          model: root.candidates
          delegate: Rectangle {
            width: 44
            height: 44
            radius: 8
            color: index === root.sel ? "#89b4fa" : "#313244"
            border.color: index === root.sel ? "#89b4fa" : "#45475a"
            border.width: 1
            Text {
              anchors.centerIn: parent
              text: modelData
              color: index === root.sel ? "#1e1e2e" : "#cdd6f4"
              font.pixelSize: 20
            }
            MouseArea {
              anchors.fill: parent
              onClicked: {
                root.sel = index
                send({ type: "select", index: index })
                send({ type: "confirm" })
              }
            }
          }
        }
      }

      // status line
      Text {
        id: status
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 10
        text: root.statusText
        color: "#a6adc8"
        font.pixelSize: 13
      }
    }
  }

  // Direct IPC (e.g. `qs ipc call jack.omarchy-write toggle`).
  IpcHandler {
    target: "jack.omarchy-write"
    function open(): string { root.open(""); return "ok" }
    function close(): string { root.close(); return "ok" }
    function toggle(): string { root.toggle(); return "ok" }
    function confirm(): string { root.confirm(); return "ok" }
    function selectLeft(): string { root.selectLeft(); return "ok" }
    function selectRight(): string { root.selectRight(); return "ok" }
    function state(): string { return root.opened ? "open" : "closed" }
    function ping(): string { return "ok" }
  }
}
