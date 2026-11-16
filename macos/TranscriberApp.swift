import AppKit
import SwiftUI
import UserNotifications

private let settingsEncoder: JSONEncoder = {
    let encoder = JSONEncoder()
    encoder.keyEncodingStrategy = .convertToSnakeCase
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
    return encoder
}()

private func decode<T: Decodable>(_ type: T.Type, from data: Data) throws -> T {
    let decoder = JSONDecoder()
    decoder.keyDecodingStrategy = .convertFromSnakeCase
    return try decoder.decode(type, from: data)
}

private enum TranscriptionModel: String, Codable, CaseIterable {
    case qwen = "qwen3-asr-1.7b"
    case whisper = "large-v3-turbo"

    var name: String {
        switch self {
        case .qwen: "Qwen3-ASR 1.7B"
        case .whisper: "Whisper Large v3 Turbo"
        }
    }

    var requiredWeights: [String] {
        switch self {
        case .qwen: ["qwen3-asr-1.7b/model.safetensors", "qwen3-forced-aligner-0.6b/model.safetensors"]
        case .whisper: ["large-v3-turbo/model.bin"]
        }
    }
}

private struct Settings: Codable {
    var inputDir: String?
    var folders: [String]?
    var createOutputSubfolder: Bool?
    var outputSubfolder: String?
    var intervalSeconds = 30
    var language = "auto"
    var model: TranscriptionModel?
    var hardware: String?
    var skipSilence: Bool?
    var speakers = true
    var speakerCount: Int?
    var doverLap: Bool?
    var monitoring = false

    var paths: [String] { folders ?? inputDir.map { [$0] } ?? [] }

    var normalized: Settings {
        var copy = self
        copy.folders = paths.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        copy.inputDir = nil
        copy.createOutputSubfolder = createOutputSubfolder ?? false
        copy.doverLap = doverLap ?? false
        copy.outputSubfolder = (outputSubfolder ?? "_FERTIGGESTELLT").trimmingCharacters(in: .whitespacesAndNewlines)
        return copy
    }
}

private enum HistoryOrder: String, CaseIterable {
    case descending = "desc"
    case ascending = "asc"

    var title: String {
        switch self {
        case .descending: "Chronologisch absteigend"
        case .ascending: "Chronologisch aufsteigend"
        }
    }
}

private struct Job: Decodable, Identifiable {
    let id: Int
    let source: String
    let completedDir: String
    let detected: Double
    let started: Double?
    let finished: Double?
    let updated: Double
    let state: String
    let settings: String
    let attempt: Int
    let phase: String?
    let progress: Double?
    let error: String?
    let transcriptionStarted: Double?
    let audioSeconds: Double?
    let speechSeconds: Double?
    let speakerSeconds: Double?
    let peakMemoryBytes: Int64?
    let speakerMethod: String?
    let speakerPasses: Int?
    let speakerNote: String?
    let originJobId: Int?

    var filename: String { URL(fileURLWithPath: source).lastPathComponent }
    private var savedSettings: [String: Any]? {
        try? JSONSerialization.jsonObject(with: Data(settings.utf8)) as? [String: Any]
    }
    var accelerator: String {
        savedSettings?["hardware"] as? String == "metal" ? "Apple-GPU (Metal)" : "CPU"
    }
    var modelName: String {
        let raw = savedSettings?["model"] as? String ?? TranscriptionModel.whisper.rawValue
        return TranscriptionModel(rawValue: raw)?.name ?? raw
    }
    var speakerRecognitionEnabled: Bool { savedSettings?["speakers"] as? Bool ?? true }
    var speakerMethodText: String {
        guard speakerRecognitionEnabled else { return "Deaktiviert" }
        switch speakerMethod {
        case "dover-lap": return "DOVER-Lap (\(speakerPasses ?? 3) Durchgänge)"
        case "single-fallback": return "Einzellauf nach DOVER-Lap-Prüfung"
        default: return savedSettings?["dover_lap"] as? Bool == true ? "DOVER-Lap" : "Einzellauf"
        }
    }
    var canRetry: Bool { ["failed", "blocked"].contains(state) }
    var canRetranscribe: Bool { state == "done" || canRetry }
    var transcriptionFinished: Double? { state == "done" ? finished : nil }
    var totalDuration: TimeInterval? {
        guard let start = transcriptionStarted, let end = transcriptionFinished, end >= start else { return nil }
        return end - start
    }
    var filePath: String {
        let moved = originJobId == nil &&
            (savedSettings?["watch_path"] == nil || savedSettings?["move_media"] as? Bool == true)
        return state == "done" && moved ? destination.path : source
    }
    var fileToShow: URL {
        if originJobId != nil {
            let stem = destination.deletingPathExtension().lastPathComponent
            let name = "\(stem) (Neu \(id)).txt"
            return destination.deletingLastPathComponent().appendingPathComponent(
                name.utf8.count <= 255 ? name : "Neutranskription \(id).txt"
            )
        }
        if savedSettings?["watch_path"] != nil {
            return destination.deletingPathExtension().appendingPathExtension("txt")
        }
        return destination
    }
    var ramPeak: String {
        guard let peak = peakMemoryBytes else { return "—" }
        let gibibytes = Double(peak) / (1024 * 1024 * 1024)
        return "\(gibibytes.formatted(.number.precision(.fractionLength(2)).locale(Locale(identifier: "de_DE")))) GiB Spitze"
    }
    var destination: URL {
        URL(fileURLWithPath: completedDir, isDirectory: true).appendingPathComponent(filename)
    }
}

private struct ServiceState: Decodable {
    let state: String
    let error: String?
}

private struct ConnectionState: Decodable {
    let available: Bool
}

private struct FolderCheck: Decodable, Identifiable {
    let path: String
    let available: Bool
    let error: String?
    let updated: Double?
    let incident: String?

    var id: String { path }
    var failed: Bool { !available && error != nil }
}

private final class FolderNotificationDelegate: NSObject, UNUserNotificationCenterDelegate {
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions { [.banner, .list] }
}

private struct Snapshot: Decodable {
    var service: ServiceState?
    var connection: ConnectionState?
    var startupRetryDelays: [TimeInterval] = []
    var running = false
    var autostart = false
    var waiting = 0
    var current: Job?
    var jobs: [Job] = []
    var folders: [FolderCheck] = []

    var serviceLabel: String {
        running ? status(service?.state ?? "active") : "Dienst aus"
    }
}

private struct CommandError: LocalizedError {
    let errorDescription: String?
    init(_ description: String) { errorDescription = description }
}

private struct Project {
    let resources = Bundle.main.bundleURL.appendingPathComponent("Contents/Resources", isDirectory: true)
    let runtime = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        .appendingPathComponent("SMB Transcriber", isDirectory: true)
    var settingsURL: URL { runtime.appendingPathComponent("config.json") }
    var defaultSettingsURL: URL { resources.appendingPathComponent("Engine/airdrop.example.json") }
    var activeSettingsURL: URL {
        FileManager.default.fileExists(atPath: settingsURL.path) ? settingsURL : defaultSettingsURL
    }
    var python: URL { resources.appendingPathComponent("Python/bin/python3.12") }
    func modelReady(_ model: TranscriptionModel, speakers: Bool) -> Bool {
        let models = runtime.appendingPathComponent("data/models", isDirectory: true)
        let speakerFiles = [
            "speaker-detection/config.yaml", "speaker-detection/embedding/pytorch_model.bin",
            "speaker-detection/segmentation/pytorch_model.bin", "speaker-detection/plda/plda.npz",
            "speaker-detection/plda/xvec_transform.npz"
        ]
        let required = model.requiredWeights + (speakers ? speakerFiles : [])
        return required.allSatisfy {
            FileManager.default.fileExists(atPath: models.appendingPathComponent($0).path)
        }
    }

    func run(_ command: [String]) async throws -> Data {
        let arguments = [
            "-BEs", resources.appendingPathComponent("Engine/watch_service.py").path,
            "--state-dir", runtime.appendingPathComponent("service").path,
            "--model-data", runtime.appendingPathComponent("data").path,
        ] + command
        let executable = python
        return try await Task.detached {
            let process = Process()
            let pipe = Pipe()
            process.executableURL = executable
            process.arguments = arguments
            process.standardOutput = pipe
            process.standardError = pipe
            try process.run()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            process.waitUntilExit()
            if process.terminationStatus != 0 {
                throw CommandError(String(decoding: data, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines))
            }
            return data
        }.value
    }
}

@MainActor
private final class AppModel: ObservableObject {
    let project = Project()
    @Published var settings = Settings()
    @Published var snapshot = Snapshot()
    @Published var message: String?
    @Published var busy = false
    @Published var downloadingModels = false
    @Published var filter = "Alle"
    @Published var historyOrder = HistoryOrder(
        rawValue: UserDefaults.standard.string(forKey: "historyOrder") ?? ""
    ) ?? .descending {
        didSet {
            UserDefaults.standard.set(historyOrder.rawValue, forKey: "historyOrder")
            Task { await refresh() }
        }
    }
    @Published var selectedJob: Job?
    @Published var historyMessage: String?
    @Published var confirmsClearHistory = false
    @Published private(set) var monitoringEnabled = false
    @Published private var directFolders: [String: FolderCheck] = [:]
    @Published private(set) var checkingFolders: Set<String> = []
    private var queuedChecks: [String: Double] = [:]
    private var directProbeRunning = false
    private var nextDirectProbe: TimeInterval = 0
    private var settingsRevision = 0
    private var refreshing = false
    private var refreshTimer: Timer?
    private let notificationDelegate = FolderNotificationDelegate()
    private var notificationRunning = false
    private var askedForNotifications = false
    private var deliveredIncidents = UserDefaults.standard.dictionary(forKey: "folderIncidents") as? [String: String] ?? [:]

    func folderStatus(_ path: String) -> FolderCheck? {
        let key = path.trimmingCharacters(in: .whitespacesAndNewlines)
        return directFolders[key] ?? snapshot.folders.first { $0.path == key }
    }

    var failedFolders: [FolderCheck] {
        Set(settings.normalized.paths).compactMap { folderStatus($0) }
            .filter(\.failed).sorted { $0.path.localizedStandardCompare($1.path) == .orderedAscending }
    }

    var connected: Bool? {
        let paths = settings.normalized.paths.filter { !$0.isEmpty }
        if paths.isEmpty { return nil }
        let checks = paths.compactMap { folderStatus($0) }
        if checks.contains(where: \.failed) { return false }
        if checks.count == paths.count && checks.allSatisfy(\.available) { return true }
        return nil
    }

    var connectionLabel: String {
        if let connected { return connected ? "Alle Ordner verfügbar" : "Ordner prüfen" }
        return settings.paths.isEmpty ? "Keine Ordner eingerichtet" : "Ordner werden geprüft"
    }

    init() {
        do {
            settings = try loadSettings()
            monitoringEnabled = settings.monitoring
        } catch { message = error.localizedDescription }
        UNUserNotificationCenter.current().delegate = notificationDelegate
        let timer = Timer(timeInterval: 2.0, repeats: true) { [weak self] _ in
            Task { @MainActor in await self?.refresh() }
        }
        RunLoop.main.add(timer, forMode: .common)
        refreshTimer = timer
        Task { await refresh() }
    }

    deinit { refreshTimer?.invalidate() }

    func refresh() async {
        guard !refreshing else { return }
        refreshing = true
        defer { refreshing = false }
        do {
            let wasRunning = snapshot.running
            snapshot = try await decode(
                Snapshot.self,
                from: project.run(["status", "--limit", "250", "--order", historyOrder.rawValue])
            )
            if snapshot.running && !wasRunning { directFolders.removeAll() }
            for entry in snapshot.folders {
                if let requested = queuedChecks[entry.path], let updated = entry.updated, updated >= requested {
                    queuedChecks.removeValue(forKey: entry.path)
                    checkingFolders.remove(entry.path)
                }
            }
            if snapshot.running {
                nextDirectProbe = 0
                notifyFolderFailures()
            } else if !directProbeRunning, ProcessInfo.processInfo.systemUptime >= nextDirectProbe {
                directProbeRunning = true
                Task { await probeSavedFolders() }
            }
        } catch { message = error.localizedDescription }
    }

    private func notifyFolderFailures() {
        let pending = snapshot.folders.filter { entry in
            guard entry.failed, let incident = entry.incident else { return false }
            return deliveredIncidents[entry.path] != incident
        }
        guard !pending.isEmpty, !notificationRunning else { return }
        notificationRunning = true
        Task {
            defer { notificationRunning = false }
            let center = UNUserNotificationCenter.current()
            var authorization = await center.notificationSettings().authorizationStatus
            if authorization == .notDetermined && !askedForNotifications {
                askedForNotifications = true
                _ = try? await center.requestAuthorization(options: [.alert])
                authorization = await center.notificationSettings().authorizationStatus
            }
            guard authorization == .authorized || authorization == .provisional else { return }
            for entry in pending {
                guard let incident = entry.incident,
                      snapshot.folders.contains(where: { $0.incident == incident && $0.failed })
                else { continue }
                let content = UNMutableNotificationContent()
                content.title = "Überwachter Ordner nicht verfügbar"
                content.subtitle = entry.path
                content.body = entry.error ?? "Bitte prüfe die Verbindung und Schreibrechte."
                do {
                    try await center.add(UNNotificationRequest(identifier: incident, content: content, trigger: nil))
                    deliveredIncidents[entry.path] = incident
                    UserDefaults.standard.set(deliveredIncidents, forKey: "folderIncidents")
                } catch { message = error.localizedDescription }
            }
        }
    }

    private func probeSavedFolders() async {
        defer { directProbeRunning = false }
        let revision = settingsRevision
        nextDirectProbe = ProcessInfo.processInfo.systemUptime + TimeInterval(settings.intervalSeconds)
        guard let saved = try? loadSettings(), !saved.paths.isEmpty,
              let checks = try? await check(saved), !snapshot.running, revision == settingsRevision else { return }
        directFolders = Dictionary(uniqueKeysWithValues: checks.map { ($0.path, $0) })
    }

    func addFolder() {
        settings.folders = settings.paths + [""]
    }

    func setPath(_ value: String, at index: Int) {
        var paths = settings.paths
        guard paths.indices.contains(index) else { return }
        paths[index] = value
        settings.folders = paths
    }

    func removeFolder(at index: Int) {
        var paths = settings.paths
        guard paths.indices.contains(index) else { return }
        paths.remove(at: index)
        settings.folders = paths
    }

    func chooseFolder(at index: Int) {
        let dialog = NSOpenPanel()
        dialog.canChooseDirectories = true
        dialog.canChooseFiles = false
        if dialog.runModal() == .OK, let path = dialog.url?.path { setPath(path, at: index) }
    }

    private func loadSettings() throws -> Settings {
        try decode(Settings.self, from: Data(contentsOf: project.activeSettingsURL)).normalized
    }

    private func withTemporarySettings<T>(_ settings: Settings, _ perform: (URL) async throws -> T) async throws -> T {
        try FileManager.default.createDirectory(at: project.runtime, withIntermediateDirectories: true)
        let temp = project.runtime.appendingPathComponent("check-\(UUID().uuidString).json")
        defer { try? FileManager.default.removeItem(at: temp) }
        try settingsEncoder.encode(settings.normalized).write(to: temp, options: .atomic)
        return try await perform(temp)
    }

    private func check(_ settings: Settings, path: String? = nil) async throws -> [FolderCheck] {
        try await withTemporarySettings(settings) { temp in
            let command = ["check", temp.path] + (path.map { ["--folder", $0] } ?? [])
            return try await decode([FolderCheck].self, from: project.run(command))
        }
    }

    func refreshFolder(_ path: String) {
        let path = path.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !path.isEmpty, checkingFolders.insert(path).inserted else { return }
        let draft = settings.normalized
        Task {
            var queued = false
            defer { if !queued { checkingFolders.remove(path) } }
            do {
                if snapshot.running, let saved = try? loadSettings(), saved.paths.contains(path),
                   draft.createOutputSubfolder == saved.createOutputSubfolder, draft.outputSubfolder == saved.outputSubfolder {
                    let requested = Date().timeIntervalSince1970
                    let config = project.activeSettingsURL
                    _ = try await project.run(["refresh-folder", config.path, path])
                    directFolders.removeValue(forKey: path)
                    queuedChecks[path] = requested
                    queued = true
                    Task {
                        try? await Task.sleep(for: .seconds(15))
                        if queuedChecks[path] == requested {
                            queuedChecks.removeValue(forKey: path)
                            checkingFolders.remove(path)
                        }
                    }
                    await refresh()
                } else {
                    var single = draft
                    single.folders = [path]
                    if let result = try await check(single, path: path).first {
                        directFolders[path] = result
                    }
                }
            } catch { message = error.localizedDescription }
        }
    }

    private func save(_ value: Settings) throws {
        try FileManager.default.createDirectory(at: project.runtime, withIntermediateDirectories: true)
        try settingsEncoder.encode(value.normalized).write(to: project.settingsURL, options: .atomic)
        monitoringEnabled = value.monitoring
        settingsRevision += 1
        nextDirectProbe = 0
        directFolders.removeAll()
    }

    func apply(_ action: String) {
        busy = true
        let draft = settings.normalized
        Task {
            defer { busy = false }
            do {
                if action == "check" {
                    let checks = try await check(draft)
                    if !snapshot.running || draft.paths != (try? loadSettings().paths) {
                        directFolders = Dictionary(uniqueKeysWithValues: checks.map { ($0.path, $0) })
                    }
                    message = checks.isEmpty ? "Keine Ordner eingerichtet." :
                        (checks.allSatisfy(\.available) ? "Alle Ordner sind erreichbar und beschreibbar." : nil)
                } else {
                    try await withTemporarySettings(draft) { temp in
                        _ = try await project.run(["validate-settings", temp.path])
                    }
                    try save(draft)
                    settings = draft
                    if action == "start" { _ = try await project.run(["start", project.settingsURL.path]) }
                    message = action == "start" ? "Hintergrunddienst wird gestartet." : "Einstellungen gespeichert."
                }
                await refresh()
            } catch { message = error.localizedDescription }
        }
    }

    func toggleMonitoring() {
        do {
            var saved = try loadSettings()
            saved.monitoring.toggle()
            try save(saved)
            settings.monitoring = saved.monitoring
            message = saved.monitoring ? "Ordnerüberwachung fortgesetzt." : "Ordnerüberwachung pausiert."
        } catch { message = error.localizedDescription }
    }

    func downloadModels() {
        guard !busy else { return }
        let selected = settings.model ?? .qwen
        let arguments = ["setup-models", "--model", selected.rawValue] +
            (settings.speakers ? [] : ["--no-speakers"])
        busy = true
        downloadingModels = true
        message = nil
        Task {
            defer {
                downloadingModels = false
                busy = false
            }
            do {
                _ = try await project.run(arguments)
                message = "\(selected.name) ist einsatzbereit."
            } catch {
                message = error.localizedDescription
            }
        }
    }

    func setAutostart(_ enabled: Bool) {
        busy = true
        Task {
            defer { busy = false }
            do {
                try await withTemporarySettings(settings) { temp in
                    _ = try await project.run(["validate-settings", temp.path])
                }
                try save(settings)
                _ = try await project.run(["autostart", enabled ? "on" : "off", project.settingsURL.path])
                message = enabled ? "Der Dienst startet bei der nächsten Anmeldung." : "Login-Start deaktiviert."
                await refresh()
            } catch { message = error.localizedDescription }
        }
    }

    func retry(_ job: Job) {
        Task {
            do {
                _ = try await project.run(["retry", String(job.id)])
                await refresh()
            } catch { message = error.localizedDescription }
        }
    }

    func retranscribe(_ job: Job) {
        busy = true
        historyMessage = nil
        var profile = settings.normalized
        profile.folders = []
        profile.createOutputSubfolder = false
        Task {
            defer { busy = false }
            do {
                try await withTemporarySettings(profile) { url in
                    _ = try await project.run(["retranscribe", String(job.id), url.path])
                }
                selectedJob = nil
                if !snapshot.running {
                    _ = try await project.run(["start", project.activeSettingsURL.path])
                }
                historyMessage = "Neue Transkription eingeplant. Die TXT erhält einen eigenen Namen."
                await refresh()
            } catch {
                historyMessage = error.localizedDescription
            }
        }
    }

    func clearHistory() {
        busy = true
        historyMessage = nil
        Task {
            defer { busy = false }
            do {
                _ = try await project.run(["clear-history"])
                selectedJob = nil
                historyMessage = "Verlauf und bekannte Dateien zurückgesetzt."
                await refresh()
            } catch {
                historyMessage = error.localizedDescription
            }
        }
    }
}

private func status(_ state: String) -> String {
    ["seen": "Wartet auf stabile Datei", "ready": "Wartet", "copying": "Wird lokal kopiert",
     "transcribing": "Wird verarbeitet", "exporting": "Ergebnis wird geschrieben", "done": "Erfolgreich",
     "failed": "Fehler", "blocked": "Ausgabe blockiert", "superseded": "Neue Dateiversion",
     "active": "Aktiv", "paused": "Pausiert", "unavailable": "Ordner nicht erreichbar",
     "stopped": "Beendet"][state] ?? state
}

private let historyLocale = Locale(identifier: "de_DE")

private func clockText(_ time: Double?) -> String {
    guard let time else { return "—" }
    let clock = Date(timeIntervalSince1970: time).formatted(
        .dateTime.hour(.twoDigits(amPM: .omitted)).minute(.twoDigits).locale(historyLocale)
    )
    return "\(clock) Uhr"
}

private func durationText(_ duration: TimeInterval?, showAllUnits: Bool = false) -> String {
    guard let duration else { return "—" }
    let seconds = Int(max(0, duration))
    let hours = seconds / 3_600
    let minutes = seconds / 60 % 60
    let remainder = seconds % 60
    if hours > 0 || showAllUnits { return "\(hours) Std. \(minutes) Min. \(remainder) Sek." }
    if minutes > 0 { return "\(minutes) Min. \(remainder) Sek." }
    return "\(remainder) Sek."
}

private func completedText(_ time: Double?, now: Date) -> String {
    let clock = clockText(time)
    guard let time else { return clock }
    let age = now.timeIntervalSince1970 - time
    guard age >= 0, age < 3600 else { return clock }
    let seconds = Int(age)
    if seconds < 60 {
        return "\(clock) (vor \(seconds) \(seconds == 1 ? "Sekunde" : "Sekunden"))"
    }
    let minutes = seconds / 60
    return "\(clock) (vor \(minutes) \(minutes == 1 ? "Minute" : "Minuten"))"
}

private struct Dashboard: View {
    @ObservedObject var model: AppModel
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    private let brandGreen = Color(red: 0.04, green: 0.34, blue: 0.21)
    private let logo = Bundle.main.url(forResource: "VoxDropLogo", withExtension: "png")
        .flatMap { NSImage(contentsOf: $0) }

    var body: some View {
        VStack(spacing: 0) {
            branding
            Divider()
            HStack(alignment: .top, spacing: 0) {
                ScrollView { configuration.padding(24) }
                    .frame(width: 340)
                    .background(Color(red: 0.97, green: 0.98, blue: 0.97))
                Divider()
                VStack(spacing: 0) {
                    folderWarnings.padding([.top, .horizontal], 24)
                    ScrollView { activeJob.padding(24) }
                }.frame(minWidth: 295, maxWidth: .infinity)
                Divider()
                history.padding(24).frame(minWidth: 365, maxWidth: .infinity)
            }
        }
        .frame(minWidth: 1050, minHeight: 650)
        .background(Color.white)
        .tint(brandGreen)
        .preferredColorScheme(.light)
        .sheet(item: $model.selectedJob) { job in details(job) }
        .alert("Verlauf und bekannte Dateien leeren?", isPresented: $model.confirmsClearHistory) {
            Button("Abbrechen", role: .cancel) {}
            Button("Leeren", role: .destructive) { model.clearHistory() }
        } message: {
            Text("Das löscht die Auftragsdaten aus VoxDrop. Aufnahmen und exportierte TXT-Dateien bleiben erhalten. Dateien in überwachten Ordnern können danach erneut erkannt werden.")
        }
    }

    private var branding: some View {
        HStack(spacing: 16) {
            if let logo {
                Image(nsImage: logo)
                    .resizable()
                    .scaledToFit()
                    .padding(6)
                    .frame(width: 72, height: 72)
                    .background(.white, in: RoundedRectangle(cornerRadius: 17))
                    .overlay(RoundedRectangle(cornerRadius: 17).strokeBorder(brandGreen.opacity(0.14)))
                    .accessibilityHidden(true)
            }
            VStack(alignment: .leading, spacing: 3) {
                Text("VoxDrop")
                    .font(.system(size: 33, weight: .bold))
                    .foregroundStyle(brandGreen)
                    .accessibilityAddTraits(.isHeader)
                Text("Automatic Media Transcription")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 24)
        .padding(.vertical, 14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(LinearGradient(
            colors: [Color(red: 0.90, green: 0.96, blue: 0.91), Color(red: 0.98, green: 0.99, blue: 0.98)],
            startPoint: .leading, endPoint: .trailing
        ))
    }

    private var configuration: some View {
        VStack(alignment: .leading, spacing: 15) {
            Text("Transkriptionsdienst").font(.title2.bold())
            Label(model.snapshot.serviceLabel,
                  systemImage: model.snapshot.running ? "circle.inset.filled" : "circle")
                .foregroundStyle(model.snapshot.running ? brandGreen : .secondary)
            if model.snapshot.running, let error = model.snapshot.service?.error {
                Text(error).font(.callout).foregroundStyle(.red).textSelection(.enabled)
            }
            Toggle("Automatisch bei Anmeldung starten", isOn: Binding(
                get: { model.snapshot.autostart }, set: { model.setAutostart($0) }
            )).disabled(model.busy)
            Toggle("Ordnerüberwachung aktiv", isOn: $model.settings.monitoring)
            Text("Überwachte Ordner").font(.headline)
            ForEach(Array(model.settings.paths.enumerated()), id: \.offset) { index, path in
                watchedFolder(index, path: path)
            }
            Button("Pfad hinzufügen", systemImage: "plus") { model.addFolder() }
            Button("Alle Ordner prüfen") { model.apply("check") }.disabled(model.busy)
            Toggle("Unterordner für fertige Transkripte erstellen?", isOn: Binding(
                get: { model.settings.createOutputSubfolder ?? false },
                set: { model.settings.createOutputSubfolder = $0 }
            ))
            .help("Legt das Transkript und die Originalaufnahme nach erfolgreichem Export gemeinsam im Unterordner ab.")
            if model.settings.createOutputSubfolder == true {
                TextField("Name des Unterordners", text: Binding(
                    get: { model.settings.outputSubfolder ?? "_FERTIGGESTELLT" },
                    set: { model.settings.outputSubfolder = $0 }
                ))
            }
            Divider()
            Picker("Intervall Ordnerüberwachung", selection: $model.settings.intervalSeconds) {
                ForEach(Array(Set([10, 30, 60, 300, model.settings.intervalSeconds])).sorted(), id: \.self) { seconds in
                    Text("\(seconds) Sekunden").tag(seconds)
                }
            }
            Picker("Modell", selection: Binding(
                get: { model.settings.model ?? .qwen }, set: { model.settings.model = $0 }
            )) {
                ForEach(TranscriptionModel.allCases, id: \.self) { choice in
                    Text(choice.name).tag(choice)
                }
            }.pickerStyle(.menu)
            if model.downloadingModels {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text("Modelle werden geladen …").font(.caption).foregroundStyle(.secondary)
                }
            } else if model.project.modelReady(model.settings.model ?? .qwen, speakers: model.settings.speakers) {
                Text("Modelle installiert").font(.caption).foregroundStyle(.secondary)
            } else {
                Button("Modelle herunterladen", systemImage: "arrow.down.circle") { model.downloadModels() }
                    .help("Lädt das gewählte Transkriptionsmodell und bei Bedarf das Modell zur Sprechererkennung.")
                    .disabled(model.busy)
            }
            Picker("Sprache", selection: $model.settings.language) {
                Text("Automatisch").tag("auto")
                Text("Deutsch").tag("de")
                Text("Englisch").tag("en")
            }
            Toggle("Lange Stille überspringen", isOn: Binding(
                get: { model.settings.skipSilence ?? false },
                set: { model.settings.skipSilence = $0 }
            ))
            .help("Lässt bei der Spracherkennung Pausen ab etwa drei Sekunden aus. Die Zeitstempel bleiben auf der Originalaufnahme.")
            Toggle("Sprechererkennung", isOn: $model.settings.speakers)
            Toggle("Mehrere Prüfdurchgänge (DOVER-Lap)", isOn: Binding(
                get: { model.settings.doverLap ?? false },
                set: { model.settings.doverLap = $0 }
            ))
            .disabled(!model.settings.speakers)
            .help("Kombiniert drei lokale Sprecherprüfungen. Funktioniert mit automatischer und fester Sprecherzahl.")
            Picker("Sprecherzahl", selection: $model.settings.speakerCount) {
                Text("Automatisch").tag(nil as Int?)
                ForEach(1...8, id: \.self) { number in Text("\(number)").tag(Optional(number)) }
            }.disabled(!model.settings.speakers)
            Picker("Rechengerät", selection: Binding(
                get: { model.settings.hardware ?? "metal" }, set: { model.settings.hardware = $0 }
            )) {
                Text("Apple-GPU (Metal)").tag("metal")
                Text("CPU").tag("cpu")
            }
            Divider()
            HStack {
                Button("Speichern") { model.apply("save") }.buttonStyle(.borderedProminent)
                if !model.snapshot.running { Button("Dienst starten") { model.apply("start") } }
            }.disabled(model.busy)
            if let message = model.message { Text(message).font(.callout).textSelection(.enabled) }
        }.frame(maxWidth: .infinity, alignment: .leading)
    }

    private func watchedFolder(_ index: Int, path: String) -> some View {
        let key = path.trimmingCharacters(in: .whitespacesAndNewlines)
        let check = model.folderStatus(key)
        let busy = model.checkingFolders.contains(key)
        return VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                if check?.failed == true {
                    TimelineView(.periodic(from: .now, by: 0.7)) { context in
                        let interval = Int(context.date.timeIntervalSinceReferenceDate / 0.7)
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundStyle(.red)
                            .opacity(reduceMotion || interval.isMultiple(of: 2) ? 1 : 0.3)
                            .accessibilityLabel("Ordnerproblem")
                    }
                }
                TextField("Ordner oder smb://", text: Binding(
                    get: { model.settings.paths.indices.contains(index) ? model.settings.paths[index] : "" },
                    set: { model.setPath($0, at: index) }
                )).labelsHidden()
                Button { model.refreshFolder(path) } label: { Image(systemName: "arrow.clockwise") }
                    .help("Ordner jetzt prüfen")
                    .accessibilityLabel("Ordner jetzt prüfen")
                    .disabled(key.isEmpty || busy)
                Button { model.chooseFolder(at: index) } label: { Image(systemName: "folder") }
                    .help("Ordner im Finder auswählen")
                    .accessibilityLabel("Ordner im Finder auswählen")
                Button { model.removeFolder(at: index) } label: { Image(systemName: "minus.circle") }
                    .help("Pfad aus der Liste entfernen")
                    .accessibilityLabel("Pfad aus der Liste entfernen")
            }
            if busy {
                Text("Wird geprüft …").font(.caption).foregroundStyle(.secondary)
            } else if let error = check?.error {
                Text(error).font(.caption).foregroundStyle(.red).textSelection(.enabled)
            } else if check?.available == true {
                Text("Erreichbar und beschreibbar").font(.caption).foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder
    private var folderWarnings: some View {
        let failures = model.failedFolders
        if !failures.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                Label(failures.count == 1 ? "Ein Ordner ist nicht verfügbar" :
                        "\(failures.count) Ordner sind nicht verfügbar",
                      systemImage: "exclamationmark.triangle.fill")
                    .font(.headline).foregroundStyle(.red)
                ScrollView {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(failures) { entry in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(entry.path).fontWeight(.semibold).textSelection(.enabled)
                                Text(entry.error ?? "").foregroundStyle(.red).textSelection(.enabled)
                            }.font(.callout).frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                }.frame(maxHeight: failures.count == 1 ? 78 : 150)
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.red.opacity(0.07), in: RoundedRectangle(cornerRadius: 8))
            .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(.red.opacity(0.24)))
        }
    }

    private var activeJob: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Aktueller Auftrag").font(.title2.bold())
            if let job = model.snapshot.current {
                Text(job.filename).font(.title3.weight(.semibold)).textSelection(.enabled)
                Text(job.phase ?? status(job.state)).font(.headline)
                if let fraction = job.progress {
                    ProgressView(value: fraction).accessibilityLabel("Fortschritt der aktuellen Phase")
                    Text(fraction.formatted(.percent.precision(.fractionLength(0)))).monospacedDigit()
                } else { ProgressView().controlSize(.small) }
                if let started = job.started {
                    LabeledContent("Laufzeit") {
                        Text(Date(timeIntervalSince1970: started), style: .timer).monospacedDigit()
                    }
                }
                LabeledContent("Modell", value: job.modelName)
                LabeledContent("Rechengerät", value: job.accelerator)
            } else { Text("Kein Auftrag in Bearbeitung").foregroundStyle(.secondary) }
            Divider()
            LabeledContent("Warteschlange", value: String(model.snapshot.waiting))
        }.frame(maxWidth: .infinity, alignment: .leading)
    }

    private var history: some View {
        let filter = model.filter
        let order = model.historyOrder
        let jobs = model.snapshot.jobs.filter { job in
            filter == "Alle" || (filter == "Fehler" ? job.canRetry : job.state == "done")
        }.sorted { a, b in
            let earlier = (a.updated, a.id) < (b.updated, b.id)
            return order == .ascending ? earlier : (b.updated, b.id) < (a.updated, a.id)
        }
        return VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Verlauf").font(.title2.bold())
                Spacer()
                Button(role: .destructive) { model.confirmsClearHistory = true } label: {
                    Label("Verlauf leeren …", systemImage: "trash")
                }
                .help(model.snapshot.current == nil ? "Verlauf und Liste bekannter Dateien zurücksetzen" :
                    "Der Verlauf lässt sich nach Abschluss des aktiven Auftrags leeren.")
                .disabled(model.busy || model.snapshot.current != nil || model.snapshot.jobs.isEmpty)
            }
            if let message = model.historyMessage {
                Text(message).font(.callout).textSelection(.enabled)
            }
            Picker("Verlauf filtern", selection: $model.filter) {
                Text("Alle").tag("Alle")
                Text("Fehler").tag("Fehler")
                Text("Fertig").tag("Fertig")
            }.labelsHidden().pickerStyle(.segmented)
            Picker("Sortierung", selection: $model.historyOrder) {
                ForEach(HistoryOrder.allCases, id: \.self) { order in
                    Text(order.title).tag(order)
                }
            }.pickerStyle(.menu)
            if jobs.isEmpty { Text("Keine Aufträge").foregroundStyle(.secondary) }
            TimelineView(.periodic(from: .now, by: 1)) { timeline in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 0) {
                        ForEach(jobs) { job in
                            Button {
                                model.historyMessage = nil
                                model.selectedJob = job
                            } label: {
                                historyRow(job, now: timeline.date)
                            }.buttonStyle(.plain)
                            Divider()
                        }
                    }
                }
            }
        }.frame(maxHeight: .infinity, alignment: .topLeading)
    }

    private func historyRow(_ job: Job, now: Date) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(job.filename)
                .font(.title3.bold())
                .fixedSize(horizontal: false, vertical: true)
            if job.originJobId != nil {
                Text("Neutranskription").font(.caption).foregroundStyle(.secondary)
            }
            Text(job.filePath)
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            VStack(alignment: .leading, spacing: 3) {
                Text("Gesamtdauer der Audiodatei: \(durationText(job.audioSeconds, showAllUnits: true))")
                Text("Transkriptionsbeginn: \(clockText(job.transcriptionStarted))")
                Text("Transkriptionsdauer (gesamt): \(durationText(job.totalDuration))")
                Text("Transkription fertiggestellt: \(completedText(job.transcriptionFinished, now: now))")
            }
            .font(.callout)
            .monospacedDigit()
            .fixedSize(horizontal: false, vertical: true)
            .padding(.top, 4)
            HStack {
                Text(status(job.state)).foregroundStyle(job.canRetry ? .red : .secondary)
                Spacer()
                Text(Date(timeIntervalSince1970: job.updated), format: .dateTime.day().month().year().locale(historyLocale))
                    .foregroundStyle(.secondary)
            }
            .font(.caption)
            .padding(.top, 2)
        }
        .multilineTextAlignment(.leading)
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.vertical, 12)
        .contentShape(Rectangle())
    }

    private func details(_ job: Job) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(job.filename).font(.title2.bold()).fixedSize(horizontal: false, vertical: true)
            Text(status(job.state)).font(.headline)
            LabeledContent("Gesamtdauer der Audiodatei", value: durationText(job.audioSeconds, showAllUnits: true))
            LabeledContent("Erkannt") { Text(Date(timeIntervalSince1970: job.detected).formatted()) }
            if let start = job.started { LabeledContent("Beginn") { Text(Date(timeIntervalSince1970: start).formatted()) } }
            if let finish = job.finished { LabeledContent("Ende") { Text(Date(timeIntervalSince1970: finish).formatted()) } }
            LabeledContent("Versuche", value: String(job.attempt))
            LabeledContent("Modell verwendet", value: job.modelName)
            LabeledContent("RAM-Auslastung verursacht", value: job.ramPeak)
                .help("Gemessene Spitze der physischen Speicherbelegung während der Transkription.")
            LabeledContent("Dauer Spracherkennung", value: durationText(job.speechSeconds))
            LabeledContent("Verfahren der Sprecherzuordnung", value: job.speakerMethodText)
            LabeledContent("Dauer Sprecherzuordnung", value:
                job.speakerRecognitionEnabled ? durationText(job.speakerSeconds) : "Deaktiviert"
            )
            LabeledContent("Dauer gesamt", value: durationText(job.totalDuration))
            LabeledContent("Rechengerät", value: job.accelerator)
            Text(job.filePath).textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
            if let error = job.error { Text(error).textSelection(.enabled).foregroundStyle(.red) }
            if let message = model.historyMessage {
                Text(message).font(.callout).textSelection(.enabled)
            }
            if let note = job.speakerNote {
                Text(note).font(.callout).foregroundStyle(.secondary).textSelection(.enabled)
            }
            HStack {
                if job.canRetry {
                    Button("Erneut versuchen") {
                        model.retry(job)
                        model.selectedJob = nil
                    }
                }
                if job.canRetranscribe {
                    Button("Neu transkribieren") { model.retranscribe(job) }
                        .help("Verwendet die aktuellen Einstellungen und legt eine zusätzliche TXT ab.")
                        .disabled(model.busy)
                }
                if job.state == "done" { Button("Im Finder zeigen") { NSWorkspace.shared.activateFileViewerSelecting([job.fileToShow]) } }
                Spacer()
                Button("Schließen") { model.selectedJob = nil }.keyboardShortcut(.cancelAction)
            }
        }.padding(24).frame(width: 550)
    }
}

private struct StatusMenu: View {
    @ObservedObject var model: AppModel
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        Text(model.connectionLabel)
        Text(model.snapshot.serviceLabel)
        if let job = model.snapshot.current {
            Text(job.phase ?? status(job.state))
        }
        Divider()
        Button("Hauptfenster öffnen") {
            openWindow(id: "dashboard")
            NSApp.activate()
        }
        if model.snapshot.running {
            Button(model.monitoringEnabled ? "Ordnerüberwachung pausieren" : "Ordnerüberwachung fortsetzen") {
                model.toggleMonitoring()
            }.disabled(model.busy)
        } else {
            Button("Dienst starten") { model.apply("start") }.disabled(model.busy)
        }
        Divider()
        Button("Oberfläche beenden") { NSApp.terminate(nil) }
    }
}

private func menuWaveform(color: NSColor) -> NSImage {
    let image = NSImage(size: NSSize(width: 18, height: 18), flipped: false) { _ in
        let waveform = NSBezierPath()
        for (index, height) in [4.0, 9.0, 15.0, 9.0, 4.0].enumerated() {
            let x = 2.0 + Double(index) * 3.5
            waveform.move(to: NSPoint(x: x, y: 9 - height / 2))
            waveform.line(to: NSPoint(x: x, y: 9 + height / 2))
        }
        waveform.lineCapStyle = .round
        waveform.lineWidth = 1.8
        color.setStroke()
        waveform.stroke()
        return true
    }
    image.isTemplate = false
    return image
}

@main
struct TranscriberApp: App {
    @StateObject private var model = AppModel()
    private let onlineIcon = menuWaveform(color: .systemGreen)
    private let offlineIcon = menuWaveform(color: .systemRed)

    var body: some Scene {
        Window("VoxDrop", id: "dashboard") { Dashboard(model: model) }
            .defaultSize(width: 1280, height: 780)
            .windowResizability(.contentMinSize)
        MenuBarExtra {
            StatusMenu(model: model)
        } label: {
            Image(nsImage: model.connected == true ? onlineIcon : offlineIcon)
                .renderingMode(.original)
                .accessibilityLabel("VoxDrop – \(model.connectionLabel)")
        }
    }
}
