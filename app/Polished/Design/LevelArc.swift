import SwiftUI

/// The bottle level: an arc in ink, clockwise from twelve o'clock, over a Line2 track. Never in
/// the shade's colour (a dark shade would vanish on the dark board); the word beside it, in the
/// row, is what carries the level for VoiceOver.
struct LevelArc: View {
    let fraction: Double
    var diameter: CGFloat = 20
    /// Selected segments draw it in the on-primary colour.
    var arc: Color = .ink

    var body: some View {
        let lineWidth = diameter * 0.16
        ZStack {
            Circle().stroke(Color.line2, lineWidth: lineWidth)
            Circle()
                .trim(from: 0, to: fraction)
                .stroke(arc, style: StrokeStyle(lineWidth: lineWidth, lineCap: .butt))
                .rotationEffect(.degrees(-90))
        }
        .padding(lineWidth / 2)
        .frame(width: diameter, height: diameter)
        .accessibilityHidden(true)
    }
}
