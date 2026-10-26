import SwiftUI
import WidgetKit

@main
struct PolishedWidgetsBundle: WidgetBundle {
    var body: some Widget {
        WearTodayWidget()
    }
}

/// "Wear today": today's pick, with its lit tip. A placeholder until run 5 feeds it the App
/// Group snapshot the app writes; it shows a fixture shade.
struct WearTodayWidget: Widget {
    static let kind = "WearToday"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: Self.kind, provider: WearTodayProvider()) { entry in
            WearTodayView(entry: entry)
        }
        .configurationDisplayName("Wear today")
        .description("Today's pick from your collection.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

struct WearTodayEntry: TimelineEntry {
    let date: Date
    let shade: SampleShade
}

struct WearTodayProvider: TimelineProvider {
    func placeholder(in context: Context) -> WearTodayEntry {
        WearTodayEntry(date: .now, shade: .acidDrip)
    }

    func getSnapshot(in context: Context, completion: @escaping @Sendable (WearTodayEntry) -> Void) {
        completion(placeholder(in: context))
    }

    func getTimeline(in context: Context, completion: @escaping @Sendable (Timeline<WearTodayEntry>) -> Void) {
        completion(Timeline(entries: [placeholder(in: context)], policy: .never))
    }
}

struct WearTodayView: View {
    let entry: WearTodayEntry
    @Environment(\.widgetFamily) private var family

    var body: some View {
        HStack(spacing: 14) {
            TipView(entry.shade.recipe, size: family == .systemSmall ? .m : .l, painting: .direct)
            VStack(alignment: .leading, spacing: 2) {
                Text("Wear today")
                    .font(.footnote)
                    .foregroundStyle(Color.ink2)
                Text(entry.shade.name)
                    .font(.headline)
                    .foregroundStyle(Color.ink)
                    .lineLimit(2)
                if family == .systemMedium {
                    Text(entry.shade.detail)
                        .font(.subheadline)
                        .foregroundStyle(Color.ink2)
                }
            }
            Spacer(minLength: 0)
        }
        .containerBackground(Color.surface, for: .widget)
    }
}
