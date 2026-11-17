import Darwin
import Foundation

@main
struct Launcher {
    static func main() {
        guard let resources = Bundle.main.resourceURL else { exit(1) }
        let python = resources.appendingPathComponent("Python/bin/python3.12").path
        let library = resources.appendingPathComponent("Python/lib/libpython3.12.dylib").path
        let entry = resources.appendingPathComponent("Desktop/desktop.py").path
        // Keep the app executable registered with Launch Services while running Qt.
        guard let handle = dlopen(library, RTLD_NOW | RTLD_GLOBAL),
              let symbol = dlsym(handle, "Py_BytesMain") else {
            if let error = dlerror() {
                fputs("VoxDrop: \(String(cString: error))\n", stderr)
            }
            exit(1)
        }
        typealias PythonMain = @convention(c) (Int32, UnsafeMutablePointer<UnsafeMutablePointer<CChar>?>) -> Int32
        let pythonMain = unsafeBitCast(symbol, to: PythonMain.self)
        let arguments = [python, "-BEs", "-Xutf8", entry] + Array(CommandLine.arguments.dropFirst())
        var command = arguments.map { strdup($0) }
        command.append(nil)
        exit(pythonMain(Int32(arguments.count), &command))
    }
}
