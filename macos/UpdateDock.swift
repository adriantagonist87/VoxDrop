import Foundation
import Darwin

let app = URL(fileURLWithPath: CommandLine.arguments[1]).standardizedFileURL
let legacy = URL(fileURLWithPath: CommandLine.arguments[2]).standardizedFileURL
let domain = "com.apple.dock" as CFString
let key = "persistent-apps" as CFString
var entries = CFPreferencesCopyAppValue(key, domain) as? [[String: Any]] ?? []
var changed = false

for index in entries.indices {
    guard var data = entries[index]["tile-data"] as? [String: Any],
          data["bundle-identifier"] as? String == "local.voxdrop",
          let file = data["file-data"] as? [String: Any],
          let address = file["_CFURLString"] as? String,
          URL(string: address)?.standardizedFileURL.path == legacy.path else { continue }
    data["file-data"] = ["_CFURLString": app.absoluteString, "_CFURLStringType": 15]
    data["book"] = try app.bookmarkData(options: .minimalBookmark, includingResourceValuesForKeys: nil, relativeTo: nil)
    entries[index]["tile-data"] = data
    changed = true
}

if changed {
    CFPreferencesSetAppValue(key, entries as CFArray, domain)
    guard CFPreferencesAppSynchronize(domain) else { exit(1) }
    let refresh = Process()
    refresh.executableURL = URL(fileURLWithPath: "/bin/launchctl")
    refresh.arguments = ["kickstart", "-k", "gui/\(getuid())/com.apple.Dock.agent"]
    try refresh.run()
    refresh.waitUntilExit()
    exit(refresh.terminationStatus)
}
