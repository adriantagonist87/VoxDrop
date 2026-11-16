import Darwin
import Foundation

@main
struct Launcher {
    static func main() {
        guard let resources = Bundle.main.resourceURL else { exit(1) }
        let python = resources.appendingPathComponent("Python/bin/python3.12").path
        let entry = resources.appendingPathComponent("Desktop/desktop.py").path
        let arguments = [python, "-BEs", "-Xutf8", entry] + Array(CommandLine.arguments.dropFirst())
        var command = arguments.map { strdup($0) }
        command.append(nil)
        execv(python, &command)
        perror("VoxDrop")
        exit(1)
    }
}
