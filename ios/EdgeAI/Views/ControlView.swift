import SwiftUI

struct ControlView: View {
    @EnvironmentObject var botService: BotService
    @State private var serverURL = UserDefaults.standard.string(forKey: "botServerURL") ?? "ws://192.168.1.192:8765/ws/live"
    @State private var editingURL = false

    var body: some View {
        NavigationView {
            VStack(spacing: 16) {
                // Server Connection
                VStack(spacing: 12) {
                    Text("Server Connection")
                        .font(.headline)

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

                    Button(action: {
                        botService.connect(to: serverURL)
                    }) {
                        Text("Connect")
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(botService.isConnected ? Color.gray : Color.blue)
                            .foregroundColor(.white)
                            .cornerRadius(8)
                    }
                    .disabled(botService.isConnected)
                }
                .padding()
                .background(Color(.systemGray6))
                .cornerRadius(8)

                // Bot Controls
                if botService.isConnected {
                    VStack(spacing: 12) {
                        Text("Bot Control")
                            .font(.headline)

                        HStack(spacing: 12) {
                            Button(action: {
                                botService.sendCommand("start")
                            }) {
                                Text("Start")
                                    .frame(maxWidth: .infinity)
                                    .padding()
                                    .background(Color.green)
                                    .foregroundColor(.white)
                                    .cornerRadius(8)
                            }

                            Button(action: {
                                botService.sendCommand("pause")
                            }) {
                                Text("Pause")
                                    .frame(maxWidth: .infinity)
                                    .padding()
                                    .background(Color.orange)
                                    .foregroundColor(.white)
                                    .cornerRadius(8)
                            }

                            Button(action: {
                                botService.sendCommand("stop")
                            }) {
                                Text("Stop")
                                    .frame(maxWidth: .infinity)
                                    .padding()
                                    .background(Color.red)
                                    .foregroundColor(.white)
                                    .cornerRadius(8)
                            }
                        }
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                }

                // Info
                VStack(alignment: .leading, spacing: 8) {
                    Text("Settings")
                        .font(.headline)

                    Text("Mac mini IP or hostname:")
                        .font(.caption)
                        .foregroundColor(.gray)

                    Text("To find: On Mac mini, System Preferences > Network")
                        .font(.caption2)
                        .foregroundColor(.gray)
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
}

struct ControlView_Previews: PreviewProvider {
    static var previews: some View {
        ControlView()
            .environmentObject(BotService())
    }
}
