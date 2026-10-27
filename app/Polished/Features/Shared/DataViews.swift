import NailTips
import PolishedAPI
import PolishedModels
import SwiftUI

extension ShadeRow {
    var recipe: TipRecipe { TipRecipe(tip.shade) }

    /// The title with the search's matches washed in ink 12% (docs/advice v3 4.6).
    var markedTitle: AttributedString {
        Marks.attributed(title, marks: marks) { $0.backgroundColor = Color.ink.opacity(0.14) }
    }

    /// Spoken once for the whole row; the tip is decoration.
    var spokenLabel: String {
        var parts = [title]
        if !finishes.isEmpty { parts.append(Words.list(finishes)) }
        if wishlisted { parts.append("wished") }
        if ownedCount > 0 { parts.append(ownedCount == 1 ? "owned" : "owned \(ownedCount) times") }
        if let priceCents { parts.append(Words.money(priceCents)) }
        return parts.joined(separator: ", ")
    }

    var statusColor: Color {
        switch status?.key {
        case "retiring", "retired": .warn
        case "sold_out", "missing": .bad
        default: .ink2
        }
    }
}

extension Bottle {
    /// "Bought 21 Jul 2026, $15.50" as the web words it; "Archived" first when it is.
    var factsLine: String {
        var parts: [String] = []
        if archived { parts.append("Archived") }
        if let bought = Words.day(boughtOn) {
            parts.append("Bought \(bought)" + (pricePaidCents.map { ", \(Words.money($0))" } ?? ""))
        } else if let paid = pricePaidCents {
            parts.append("Paid \(Words.money(paid))")
        }
        if parts.isEmpty, printedCode == nil { parts.append("Added \(Words.day(String(createdAt.prefix(10))) ?? "")") }
        return parts.joined(separator: ". ")
    }

    var spokenLabel: String {
        var parts = [factsLine, state.label]
        if let printedCode { parts.append(printedCode) }
        return parts.filter { !$0.isEmpty }.joined(separator: ", ")
    }
}

/// The level as an ink arc and the word beside it; Low and Empty keep their word colour so the
/// colour is never the only carrier (docs/advice v3 4.1).
struct LevelLabel: View {
    let state: BottleState

    var body: some View {
        HStack(spacing: 6) {
            LevelArc(fraction: state.fraction)
            Text(state.label)
                .font(.subheadline)
                .foregroundStyle(state == .empty ? Color.bad : state == .low ? Color.warn : Color.ink2)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(state.label)
    }
}

/// One shade in a list: the lit tip, the name (with the matched letters washed), the wish heart
/// and the price; under it the status word, the finishes and the count owned.
struct ShadeRowView: View {
    let shade: ShadeRow
    var showsMarks = true

    var body: some View {
        HStack(spacing: 14) {
            TipView(shade.recipe, size: .m)
                .tipSource(shade.id)
                .padding(.vertical, 6)
                .padding(.horizontal, 2)
            VStack(alignment: .leading, spacing: 3) {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Group {
                        if showsMarks { Text(shade.markedTitle) } else { Text(shade.title) }
                    }
                    .font(.headline)
                    .foregroundStyle(Color.ink)
                    .lineLimit(2)
                    if shade.wishlisted {
                        Image(systemName: "heart.fill")
                            .font(.footnote)
                            .foregroundStyle(Color.heart)
                            .accessibilityHidden(true)
                    }
                    Spacer(minLength: 8)
                    if let cents = shade.priceCents {
                        Text(Words.money(cents))
                            .font(.subheadline)
                            .monospacedDigit()
                            .foregroundStyle(Color.ink2)
                    }
                }
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    subtitle
                    Spacer(minLength: 8)
                    if shade.ownedCount > 0 {
                        Text("×\(shade.ownedCount)")
                            .font(.footnote)
                            .monospacedDigit()
                            .foregroundStyle(Color.ink2)
                    }
                }
            }
        }
        .contentShape(Rectangle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(shade.spokenLabel)
    }

    private var subtitle: some View {
        // Colour is the tip's job; a status word is the only coloured text in a row.
        let word = shade.statusWord
        let finishes = shade.finishLine
        return HStack(spacing: 6) {
            if let word {
                Text(word)
                    .fontWeight(.medium)
                    .foregroundStyle(shade.status == nil ? Color.ink3 : shade.statusColor)
            }
            if !finishes.isEmpty {
                Text(finishes).foregroundStyle(Color.ink2)
            }
        }
        .font(.subheadline)
        .lineLimit(1)
    }
}

/// A photo from the shop's CDN, cropped to its frame; the Fill colour while it arrives. The CDN
/// resizes on request, so a phone asks for the pixels it shows.
struct ShopPhoto: View {
    let url: String
    var width = 840
    var height = 1120

    var body: some View {
        AsyncImage(url: sized) { phase in
            switch phase {
            case .success(let image):
                image.resizable().scaledToFill()
            case .failure:
                Color.fill.overlay { Image(systemName: "photo").foregroundStyle(Color.ink3) }
            default:
                Color.fill
            }
        }
    }

    private var sized: URL? {
        URL(string: url + (url.contains("?") ? "&" : "?") + "width=\(width)&height=\(height)&crop=center")
    }
}

/// Under the title when a refresh failed but a snapshot is on screen: what is shown is a moment
/// old, said once and quietly, never a blocking page (docs/NATIVE.md 5.9).
struct OfflineLine: View {
    var body: some View {
        Label("Showing what was here a moment ago", systemImage: "wifi.slash")
            .font(.footnote)
            .foregroundStyle(Color.ink2)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .accessibilityElement(children: .combine)
    }
}

/// A load that failed with nothing to show: what happened and one button.
struct LoadFailure: View {
    let error: APIError
    let retry: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            TipView.unpainted(size: .l)
                .padding(.bottom, 8)
            Text(error == .offline ? "You're offline" : "Couldn't load this")
                .font(.headline)
                .foregroundStyle(Color.ink)
            Text(error == .offline ? "Connect to the internet and try again." : error.message)
                .font(.subheadline)
                .foregroundStyle(Color.ink2)
                .multilineTextAlignment(.center)
            Button("Try again", action: retry)
                .buttonStyle(SecondaryButtonStyle())
        }
        .padding(32)
        .frame(maxWidth: .infinity)
    }
}
