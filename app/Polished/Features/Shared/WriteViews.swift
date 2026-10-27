import PolishedModels
import PolishedStore
import SwiftUI

// The pieces every form that writes is made of (docs/NATIVE.md 2.3, 5.8): the status line, the
// inline field error, a native date field with its presets, a price in dollars, and a Save that
// shows progress only after 300 ms.

/// The line a write leaves under the title: a toggle that was undone, or a fact the server told.
/// A capsule on the top edge, a few seconds, then gone; Reduce Motion fades it.
private struct StatusLineModifier: ViewModifier {
    @Environment(AppModel.self) private var app
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func body(content: Content) -> some View {
        content
            .overlay(alignment: .top) {
                if let status = app.writes.status {
                    Button {
                        app.writes.dismissStatus()
                    } label: {
                        Text(status.message)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(status.isFailure ? Color.bad : Color.ink)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 16)
                            .padding(.vertical, 10)
                            .background(Color.surface, in: Capsule())
                            .overlay { Capsule().strokeBorder(Color.line2, lineWidth: 1) }
                            .shadow(color: Color.shadowInk.opacity(0.18), radius: 10, y: 4)
                    }
                    .buttonStyle(.plain)
                    .padding(.top, 6)
                    .padding(.horizontal, 16)
                    .id(status.id)
                    .transition(reduceMotion ? .opacity : .move(edge: .top).combined(with: .opacity))
                    .accessibilityIdentifier("status-line")
                    .onAppear {
                        UIAccessibility.post(notification: .announcement, argument: status.message)
                    }
                }
            }
            .animation(reduceMotion ? .easeOut(duration: 0.15) : .smooth(duration: 0.3), value: app.writes.status)
            // Write failed, network failure on a write: .error (docs/NATIVE.md 5.8).
            .sensoryFeedback(.error, trigger: app.writes.failures)
            // A code that already means another shade: .warning.
            .sensoryFeedback(.warning, trigger: app.writes.warnings)
    }
}

extension View {
    /// Shows the coordinator's status line over this view.
    func statusLine() -> some View {
        modifier(StatusLineModifier())
    }
}

/// A 422's message under its field.
struct FieldError: View {
    let message: String?

    var body: some View {
        if let message {
            Text(message)
                .font(.footnote)
                .foregroundStyle(Color.bad)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityIdentifier("field-error")
        }
    }
}

/// A date the server checks (not after today, in the household's zone): the native picker, and
/// presets. `iso` is nil while the date is not set; `clearLabel` ("Don't know") puts it back
/// there, and is absent where the date is required.
struct DateField: View {
    let title: String
    @Binding var iso: String?
    var clearLabel: String?
    var emptyText = "Not yet"
    var error: String?
    @Environment(AppModel.self) private var app

    var body: some View {
        let day = app.day
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(title).foregroundStyle(Color.ink)
                Spacer(minLength: 12)
                if let date = day.date(iso) {
                    DatePicker(
                        title,
                        selection: Binding(get: { date }, set: { iso = day.iso($0) }),
                        in: ...(day.date(day.today()) ?? Date()),
                        displayedComponents: .date
                    )
                    .labelsHidden()
                    .environment(\.timeZone, day.timeZone)
                } else {
                    Button {
                        iso = day.today()
                    } label: {
                        Text(emptyText)
                            .foregroundStyle(Color.ink3)
                            .frame(minHeight: 44)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("\(title), \(emptyText). Pick a date")
                }
            }
            HStack(spacing: 8) {
                Chip(title: "Today", isOn: iso == day.today()) { iso = day.today() }
                Chip(title: "Yesterday", isOn: iso == day.yesterday()) { iso = day.yesterday() }
                if let clearLabel {
                    Chip(title: clearLabel, isOn: iso == nil) { iso = nil }
                }
            }
            FieldError(message: error)
        }
        .accessibilityElement(children: .contain)
    }
}

/// A price in dollars, typed as "15.50", sent as cents. `text` is what is in the field;
/// `Entry.cents` reads it.
struct PriceField: View {
    let title: String
    @Binding var text: String
    var error: String?
    var prompt = "0.00"

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(title).foregroundStyle(Color.ink)
                Spacer(minLength: 12)
                Text("$").foregroundStyle(Color.ink2)
                    .accessibilityHidden(true)
                TextField(prompt, text: $text)
                    .keyboardType(.decimalPad)
                    .multilineTextAlignment(.trailing)
                    .monospacedDigit()
                    .frame(maxWidth: 110)
                    .accessibilityLabel("\(title), in dollars")
            }
            .frame(minHeight: 44)
            FieldError(message: error)
        }
    }
}

/// The text of a price field as a validation says it, before the server is asked.
let priceMessage = "Use an amount like 15.50."

/// Cancel at the leading edge and Save (or `title`) at the trailing, the way the system places
/// them, with progress in place of the word once the wait passes 300 ms.
struct SheetBar: ToolbarContent {
    var saveTitle = "Save"
    let save: SaveAction
    var isEnabled = true
    let onCancel: () -> Void
    let onSave: () -> Void

    var body: some ToolbarContent {
        ToolbarItem(placement: .cancellationAction) {
            Button("Cancel", action: onCancel)
                .disabled(save.isRunning)
        }
        ToolbarItem(placement: .confirmationAction) {
            Button(action: onSave) {
                if save.showsProgress {
                    ProgressView()
                } else {
                    Text(saveTitle)
                }
            }
            .disabled(!isEnabled || save.isRunning)
            .accessibilityIdentifier("sheet-save")
        }
    }
}

/// The text of a status that is not tied to one field.
struct GeneralError: View {
    let message: String?

    var body: some View {
        if let message {
            Text(message)
                .font(.subheadline)
                .foregroundStyle(Color.bad)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityIdentifier("general-error")
        }
    }
}
