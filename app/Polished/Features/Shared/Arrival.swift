import SwiftUI

/// The authored moment of the app (docs/NATIVE.md 5.7, moment 3): a tip that has just arrived in
/// the collection scales in on a spring (0.85, 1.04, 0.98, 1) while one band of light crosses it,
/// 600 ms in all, with the success haptic as it lands. Reduce Motion: opacity only, 150 ms, no
/// sweep. It starts once the sheet that caused it is gone.
private struct ArrivalModifier: ViewModifier {
    /// The shade whose bottle was just added.
    let shadeID: Int
    @Environment(AppModel.self) private var app
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var landed = 0
    @State private var sweep: CGFloat?

    private struct Pose {
        var scale = 1.0
        var opacity = 1.0
    }

    func body(content: Content) -> some View {
        let serial = app.arrival.shadeID == shadeID ? app.arrival.serial : 0
        Group {
            if reduceMotion {
                content.keyframeAnimator(initialValue: Pose(), trigger: landed) { view, pose in
                    view.opacity(pose.opacity)
                } keyframes: { _ in
                    KeyframeTrack(\.opacity) {
                        LinearKeyframe(0, duration: 0.001)
                        LinearKeyframe(1, duration: 0.15)
                    }
                }
            } else {
                content
                    .environment(\.tipSweep, sweep)
                    .keyframeAnimator(initialValue: Pose(), trigger: landed) { view, pose in
                        view.scaleEffect(pose.scale).opacity(pose.opacity)
                    } keyframes: { _ in
                        KeyframeTrack(\.scale) {
                            LinearKeyframe(0.85, duration: 0.001)
                            SpringKeyframe(1.04, duration: 0.18, spring: .smooth)
                            SpringKeyframe(0.98, duration: 0.15, spring: .smooth)
                            SpringKeyframe(1.0, duration: 0.27, spring: .smooth)
                        }
                        KeyframeTrack(\.opacity) {
                            LinearKeyframe(0, duration: 0.001)
                            LinearKeyframe(1, duration: 0.12)
                        }
                    }
            }
        }
        .task(id: serial) {
            guard serial > 0 else { return }
            // The sheet is still leaving; the arrival is the first thing she sees after it.
            try? await Task.sleep(for: .milliseconds(450))
            guard !Task.isCancelled else { return }
            sweep = -0.1
            landed = serial
            guard !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 0.7)) { sweep = 1.45 }
            try? await Task.sleep(for: .milliseconds(750))
            sweep = nil
        }
        .sensoryFeedback(.success, trigger: landed)
    }
}

extension View {
    /// This tip arrives (scales in, one sweep) when a bottle of `shadeID` is added.
    func arrival(of shadeID: Int) -> some View {
        modifier(ArrivalModifier(shadeID: shadeID))
    }
}

/// A one-off sweep across the tips inside, for "Another" on Home: set `trigger` to a new value.
private struct SweepModifier: ViewModifier {
    let trigger: Int
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var sweep: CGFloat?

    func body(content: Content) -> some View {
        content
            .environment(\.tipSweep, sweep)
            .task(id: trigger) {
                guard trigger > 0, !reduceMotion else { return }
                sweep = -0.1
                withAnimation(.easeInOut(duration: 0.7)) { sweep = 1.45 }
                try? await Task.sleep(for: .milliseconds(750))
                sweep = nil
            }
    }
}

extension View {
    func sweep(trigger: Int) -> some View {
        modifier(SweepModifier(trigger: trigger))
    }
}
