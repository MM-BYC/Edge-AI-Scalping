import SwiftUI

// MARK: - 3D press button style

struct PressButtonStyle: ButtonStyle {
    let color: Color
    let isActive: Bool

    func makeBody(configuration: Configuration) -> some View {
        let pressed = configuration.isPressed || isActive
        return configuration.label
            .frame(maxWidth: .infinity)
            .padding()
            .background(
                ZStack {
                    // Shadow layer (bottom-right offset gives raised look)
                    RoundedRectangle(cornerRadius: 8)
                        .fill(color.opacity(0.5))
                        .offset(x: pressed ? 0 : 3, y: pressed ? 0 : 4)
                    // Face
                    RoundedRectangle(cornerRadius: 8)
                        .fill(pressed ? color.opacity(0.75) : color)
                        .offset(x: pressed ? 2 : 0, y: pressed ? 2 : 0)
                }
            )
            .foregroundColor(.white)
            .fontWeight(.semibold)
            .offset(x: pressed ? 2 : 0, y: pressed ? 2 : 0)
            .animation(.easeOut(duration: 0.1), value: pressed)
    }
}

// MARK: - View

struct ControlView: View {
    @EnvironmentObject var botService: BotService
    @State private var serverURL  = UserDefaults.standard.string(forKey: "botServerURL")
                                    ?? "ws://192.168.1.192:8765/ws/live"
    @State private var editingURL = false
    @State private var activeCmd: String? = nil   // "start" | "pause" | "stop"

    var body: some View {
        NavigationView {
            VStack(spacing: 16) {

                // ── Server Connection ──────────────────────────────────
                VStack(spacing: 12) {
                    Text("Server Connection").font(.headline)

                    HStack {
                        if editingURL {
                            TextField("ws://192.168.1.192:8765/ws/live", text: $serverURL)
                                .textFieldStyle(.roundedBorder)
                                .font(.caption)
                        } else {
                            Text(serverURL)
                                .font(.caption)
                                .foregroundColor(.blue)
                                .truncationMode(.middle)
                        }
                        Button(action: { editingURL.toggle() }) {
                            Image(systemName: editingURL ? "checkmark" : "pencil")
                        }
                    }

                    HStack(spacing: 12) {
                        Button(action: { botService.connect(to: serverURL) }) {
                            Text("Connect")
                        }
                        .buttonStyle(PressButtonStyle(color: .blue,
                                                      isActive: botService.isConnected))
                        .disabled(botService.isConnected)

                        Button(action: { botService.disconnect() }) {
                            Text("Disconnect")
                        }
                        .buttonStyle(PressButtonStyle(color: .red,
                                                      isActive: !botService.isConnected))
                        .disabled(!botService.isConnected)
                    }
                }
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(8)

                // ── Bot Controls ───────────────────────────────────────
                if botService.isConnected {
                    VStack(spacing: 12) {
                        Text("Bot Control").font(.headline)

                        HStack(spacing: 12) {
                            Button(action: { send("start") }) {
                                Text("Start")
                            }
                            .buttonStyle(PressButtonStyle(color: .green,
                                                          isActive: activeCmd == "start"))

                            Button(action: { send("pause") }) {
                                Text("Pause")
                            }
                            .buttonStyle(PressButtonStyle(color: .orange,
                                                          isActive: activeCmd == "pause"))

                            Button(action: { send("stop") }) {
                                Text("Stop")
                            }
                            .buttonStyle(PressButtonStyle(color: .red,
                                                          isActive: activeCmd == "stop"))
                        }
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                }

                // ── Settings info ──────────────────────────────────────
                VStack(alignment: .leading, spacing: 8) {
                    Text("Settings").font(.headline)
                    Text("Mac mini IP or hostname:").font(.caption).foregroundColor(.gray)
                    Text("To find: On Mac mini, System Preferences > Network")
                        .font(.caption2).foregroundColor(.gray)
                }
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(8)

                Spacer()
            }
            .padding()
            .navigationTitle("Control")
        }
    }

    private func send(_ cmd: String) {
        activeCmd = cmd
        botService.sendCommand(cmd)
    }
}

// MARK: - Preview

struct ControlView_Previews: PreviewProvider {
    static var previews: some View {
        ControlView().environmentObject(BotService())
    }
}
