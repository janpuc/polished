import SwiftUI
import UIKit

/// The hand on the layer rows: a tap, a long press that goes on to drag, and (while arranging) a
/// plain drag, as three UIKit recognizers on one clear view laid over the rows (docs/NATIVE.md 8,
/// run 8). SwiftUI's `LongPressGesture` sequenced before a `DragGesture` never fired under a real
/// finger inside the builder's `ScrollView` and sheet: the scroll view's pan and the sheet's own
/// drag arbitrate against SwiftUI gestures in ways a synthesized touch does not exercise. A UIKit
/// recognizer is the same thing the system's own reordering uses, and the delegate below makes the
/// scroll view's and the sheet's pans wait for it, so once it recognizes they never start.
///
/// Rows are `rowHeight` tall from the top of the view; positions are reported as row indices and
/// the finger's vertical travel since it went down.
struct ArrangeGestures: UIViewRepresentable {
    let rowHeight: CGFloat
    let rowCount: Int
    let arranging: Bool
    /// False while a popover is open: a popover keeps the view it points at (and so these rows)
    /// live, which would take the tap that should dismiss it.
    let enabled: Bool
    let onTap: (Int) -> Void
    let onHold: (Int) -> Void
    let onDragBegan: (Int) -> Void
    let onDragMoved: (CGFloat) -> Void
    let onDragEnded: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> UIView {
        let view = UIView()
        view.backgroundColor = .clear
        view.isAccessibilityElement = false
        let coordinator = context.coordinator

        let tap = UITapGestureRecognizer(target: coordinator, action: #selector(Coordinator.tapped(_:)))
        let hold = UILongPressGestureRecognizer(target: coordinator, action: #selector(Coordinator.held(_:)))
        hold.minimumPressDuration = 0.35
        hold.allowableMovement = 10
        let pan = UIPanGestureRecognizer(target: coordinator, action: #selector(Coordinator.panned(_:)))
        pan.maximumNumberOfTouches = 1
        for recognizer in [tap, hold, pan] {
            recognizer.delegate = coordinator
            view.addGestureRecognizer(recognizer)
        }
        coordinator.pan = pan
        return view
    }

    func updateUIView(_ view: UIView, context: Context) {
        context.coordinator.parent = self
        view.isUserInteractionEnabled = enabled
    }

    final class Coordinator: NSObject, UIGestureRecognizerDelegate {
        var parent: ArrangeGestures
        weak var pan: UIPanGestureRecognizer?
        private var startY: CGFloat = 0

        init(_ parent: ArrangeGestures) { self.parent = parent }

        private func index(atY y: CGFloat) -> Int {
            min(max(Int(y / parent.rowHeight), 0), max(parent.rowCount - 1, 0))
        }

        @objc func tapped(_ tap: UITapGestureRecognizer) {
            guard tap.state == .ended else { return }
            parent.onTap(index(atY: tap.location(in: tap.view).y))
        }

        /// Recognised after the press has been held; the same recognizer then reports the drag.
        @objc func held(_ hold: UILongPressGestureRecognizer) {
            let y = hold.location(in: hold.view).y
            switch hold.state {
            case .began:
                startY = y
                parent.onHold(index(atY: y))
            case .changed:
                parent.onDragMoved(y - startY)
            case .ended, .cancelled, .failed:
                parent.onDragEnded()
            default:
                break
            }
        }

        @objc func panned(_ pan: UIPanGestureRecognizer) {
            switch pan.state {
            case .began:
                startY = pan.location(in: pan.view).y - pan.translation(in: pan.view).y
                parent.onDragBegan(index(atY: startY))
                parent.onDragMoved(pan.translation(in: pan.view).y)
            case .changed:
                parent.onDragMoved(pan.translation(in: pan.view).y)
            case .ended, .cancelled, .failed:
                parent.onDragEnded()
            default:
                break
            }
        }

        // MARK: UIGestureRecognizerDelegate

        /// A plain drag is a drag of a row only while the rows jiggle; before that it is a scroll.
        func gestureRecognizerShouldBegin(_ recognizer: UIGestureRecognizer) -> Bool {
            recognizer === pan ? parent.arranging : true
        }

        /// Recognizers on the views behind ours wait for ours, and only those: a hold that is
        /// recognised takes the touch from the scroll view's pan and the sheet's drag, a finger
        /// that moves first fails the hold and they go on, and a tap on a row is never also a tap on
        /// the page (SwiftUI's own recognizer sits on the hosting view). A popover's dismissal
        /// region is not behind us and must not wait: it would never dismiss.
        func gestureRecognizer(
            _ recognizer: UIGestureRecognizer, shouldBeRequiredToFailBy other: UIGestureRecognizer
        ) -> Bool {
            guard let ours = recognizer.view, let theirs = other.view, theirs !== ours, ours.isDescendant(of: theirs)
            else { return false }
            return recognizer is UITapGestureRecognizer || other is UIPanGestureRecognizer
        }

        func gestureRecognizer(
            _ recognizer: UIGestureRecognizer, shouldRecognizeSimultaneouslyWith other: UIGestureRecognizer
        ) -> Bool {
            false
        }
    }
}
