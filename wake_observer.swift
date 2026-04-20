#!/usr/bin/env swift
import AppKit
import Foundation

let baseDir = (NSHomeDirectory() as NSString).appendingPathComponent("Library/Application Support/NingenRadioXPost")
let scriptPath = (baseDir as NSString).appendingPathComponent("run_post.sh")
let minInterval: TimeInterval = 300

final class WakeObserver {
    private var lastRun: Date = .distantPast

    func start() {
        NSWorkspace.shared.notificationCenter.addObserver(
            self,
            selector: #selector(handleWake),
            name: NSWorkspace.didWakeNotification,
            object: nil
        )

        // Catch missed runs after login/reboot as well.
        trigger(reason: "agent-start")
        RunLoop.current.run()
    }

    @objc private func handleWake(_ notification: Notification) {
        trigger(reason: "did-wake")
    }

    private func trigger(reason: String) {
        let now = Date()
        guard now.timeIntervalSince(lastRun) >= minInterval else {
            return
        }
        lastRun = now

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/zsh")
        process.arguments = [scriptPath]
        process.environment = ProcessInfo.processInfo.environment

        do {
            try process.run()
            process.waitUntilExit()
            let timestamp = ISO8601DateFormatter().string(from: now)
            FileHandle.standardOutput.write(Data("[\(timestamp)] triggered: \(reason)\n".utf8))
        } catch {
            let timestamp = ISO8601DateFormatter().string(from: now)
            FileHandle.standardError.write(Data("[\(timestamp)] wake observer error: \(error)\n".utf8))
        }
    }
}

WakeObserver().start()
