@testable import NailTips
import SwiftUI
import Testing

@Suite("TipShape")
struct TipShapeTests {
    private static let frames = [
        CGRect(x: 0, y: 0, width: 102, height: 168),
        CGRect(x: 0, y: 0, width: 28, height: 46),
        CGRect(x: 10, y: 20, width: 96, height: 158),
    ]

    @Test(arguments: frames)
    func boundingBoxIsTheFrame(_ frame: CGRect) {
        let box = TipShape().path(in: frame).boundingRect
        #expect(abs(box.minX - frame.minX) < 0.01)
        #expect(abs(box.minY - frame.minY) < 0.01)
        #expect(abs(box.maxX - frame.maxX) < 0.01)
        #expect(abs(box.maxY - frame.maxY) < 0.01)
    }

    @Test(arguments: frames)
    func isSymmetricAboutTheVerticalAxis(_ frame: CGRect) {
        let path = TipShape().path(in: frame)
        let mirror = path.applying(CGAffineTransform(a: -1, b: 0, c: 0, d: 1, tx: 2 * frame.midX, ty: 0))
        // Same silhouette: every sampled point is inside both or neither.
        for row in 0...40 {
            for column in 0...40 {
                let point = CGPoint(
                    x: frame.minX + frame.width * (Double(column) + 0.37) / 41,
                    y: frame.minY + frame.height * (Double(row) + 0.41) / 41)
                #expect(path.contains(point) == mirror.contains(point), "\(point)")
            }
        }
    }

    @Test func cornersFollowTheCSSRadii() {
        let frame = CGRect(x: 0, y: 0, width: 100, height: 100)
        let path = TipShape().path(in: frame)
        #expect(path.contains(CGPoint(x: 50, y: 1)))  // the apex
        #expect(!path.contains(CGPoint(x: 5, y: 5)))  // the top corners are 50% by 62%
        #expect(path.contains(CGPoint(x: 5, y: 80)))  // the sides are straight between 62% and 70%
        #expect(!path.contains(CGPoint(x: 2, y: 98)))  // the bottom corners are 38% by 30%
        #expect(path.contains(CGPoint(x: 50, y: 99)))
    }
}

@Suite("SVG path data")
struct SVGPathTests {
    @Test func parsesMinusSignsAsSeparators() {
        let bands = SVGPath.tightBounds(of: SVGPath.parse("M-8 150Q51 52 112 96L112 128Q51 84-8 176Z"))
        #expect(bands.minX == -8 && bands.maxX == 112)
        #expect(bands.maxY == 176)
    }

    @Test func tightBoundsExcludeControlPoints() {
        // The gloss highlight's controls reach y 20, the curve itself only about y 22.5.
        let box = SVGPath.tightBounds(of: SVGPath.parse("M25 30C26 20 37 20 39 30L36 98C35 106 29 105 28 97Z"))
        #expect(box.minY > 22 && box.minY < 23.5)
        #expect(box.minX == 25 || box.minX == 28 || box.minX < 28.01)
    }
}
