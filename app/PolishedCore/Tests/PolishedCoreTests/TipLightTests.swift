import Foundation
import Testing

@testable import NailTips

@Suite("Tip light")
struct TipLightTests {
    private func near(_ a: Double, _ b: Double) -> Bool { abs(a - b) < 1e-9 }

    @Test("the mapper: the held position is the static light, ±20° reach the ends, more is clamped")
    func mapper() {
        let centre = TipLightMapper.light(rollDegrees: 0, pitchDegrees: 0)
        #expect(centre == TipLight.static)
        let right = TipLightMapper.light(rollDegrees: 20, pitchDegrees: 0)
        #expect(near(right.lx, 0.25) && near(right.ly, -0.55))
        let left = TipLightMapper.light(rollDegrees: -20, pitchDegrees: 0)
        #expect(near(left.lx, -0.95))
        let toward = TipLightMapper.light(rollDegrees: 0, pitchDegrees: 20)
        #expect(near(toward.ly, -0.15) && near(toward.lx, -0.35))
        let away = TipLightMapper.light(rollDegrees: 0, pitchDegrees: -20)
        #expect(near(away.ly, -0.95))
        // 40° is the same as 20°, in both directions.
        #expect(TipLightMapper.light(rollDegrees: 40, pitchDegrees: 40) == TipLightMapper.light(rollDegrees: 20, pitchDegrees: 20))
        #expect(TipLightMapper.light(rollDegrees: -40, pitchDegrees: -40) == TipLightMapper.light(rollDegrees: -20, pitchDegrees: -20))
        let half = TipLightMapper.light(rollDegrees: 10, pitchDegrees: -10)
        #expect(near(half.lx, -0.05) && near(half.ly, -0.75))
    }

    @Test("the low-pass filter moves 18% of the way each sample and the reference drifts with a 4 s constant")
    func filters() {
        #expect(near(TipLightMapper.smoothed(previous: 0, sample: 10), 1.8))
        #expect(near(TipLightMapper.smoothed(previous: 10, sample: 10), 10))
        #expect(near(TipLightMapper.drifted(reference: 0, current: 10, dt: 0), 0))
        #expect(near(TipLightMapper.drifted(reference: 0, current: 10, dt: 4), 10 * (1 - exp(-1.0))))
        #expect(TipLightMapper.drifted(reference: 0, current: 10, dt: 60) > 9.99)
    }

    @Test("a held tilt settles back to the default light, so the light never sticks at the clamp")
    func recentres() {
        var filter = TipLightFilter()
        var light = TipLight.static
        // A sudden 30° roll: the light swings towards the clamp...
        for _ in 0..<15 { light = filter.update(rollDegrees: 30, pitchDegrees: 0, dt: 1.0 / 30) }
        #expect(light.lx > TipLight.static.lx + 0.2)
        // ...and, held there for half a minute, comes back.
        for _ in 0..<900 { light = filter.update(rollDegrees: 30, pitchDegrees: 0, dt: 1.0 / 30) }
        #expect(abs(light.lx - TipLight.static.lx) < 0.01)
        filter.recentre()
        #expect(filter == TipLightFilter())
    }

    @Test("the gate is live only when no reason to hold still applies")
    func gate() {
        #expect(LightGate().isLive)
        #expect(!LightGate(reduceMotion: true).isLive)
        #expect(!LightGate(lowPowerMode: true).isLive)
        #expect(!LightGate(thermalSerious: true).isLive)
        #expect(!LightGate(sceneActive: false).isLive)
        #expect(!LightGate(motionAvailable: false).isLive)
        #expect(!LightGate(simulator: true).isLive)
        #expect(!LightGate(reduceMotion: true, lowPowerMode: true, thermalSerious: true, sceneActive: false, motionAvailable: false, simulator: true).isLive)
    }

    private func recipe(_ layers: TipShade...) -> TipRecipe { TipRecipe(layers) }
    private func shade(_ finishes: Set<String>, topper: Bool = false, clear: Bool = false) -> TipShade {
        TipShade(id: 1, hex: "#aa3366", finishes: finishes, topper: topper, clear: clear)
    }

    @Test("strengths per finish: pool, holo band and gloss")
    func strengths() {
        func of(_ shade: TipShade) -> TipLightStrengths { TipLightStrengths(TipRecipe(shade)) }
        #expect(of(shade(["creme"])) == TipLightStrengths(specular: 0.35, holo: 0, gloss: 1))
        #expect(of(shade(["jelly"])).specular == 0.35)
        #expect(of(shade([])).specular == 0.35)
        for finish in ["metallic", "chrome", "reflective"] { #expect(of(shade([finish])).specular == 0.6) }
        #expect(of(shade(["glitter"])).specular == 0.45)
        #expect(of(shade(["matte"])) == TipLightStrengths(specular: 0, holo: 0, gloss: 0))
        #expect(of(shade(["holographic"])).holo == 0.22)
        #expect(of(shade(["iridescent"])).holo == 0.14)
        #expect(of(shade(["flakie"])).holo == 0.10)
        // Finishes add up and are clamped to 0.3.
        #expect(abs(of(shade(["iridescent", "flakie"])).holo - 0.24) < 1e-9)
        #expect(of(shade(["holographic", "iridescent", "flakie"])).holo == 0.3)
    }

    @Test("strengths of a stack: from the last opaque layer up, toppers count 60%")
    func stacks() {
        // A flakie topper over a creme: the pool of the top layer, the topper's holo × 0.6.
        let stack = TipLightStrengths(recipe(shade(["holographic"]), shade(["creme"]), shade(["flakie"], topper: true)))
        #expect(stack.specular == 0.35)
        #expect(abs(stack.holo - 0.06) < 1e-9, "the holographic below the opaque creme is hidden")
        // A clear topper adds no pool of its own: the layer below it lights the nail.
        let clear = TipLightStrengths(recipe(shade(["chrome"]), shade(["flakie"], topper: true, clear: true)))
        #expect(clear.specular == 0.6)
        // Matte on top: no pool, no gloss, whatever is below.
        let matte = TipLightStrengths(recipe(shade(["holographic"]), shade(["matte"])))
        #expect(matte.specular == 0 && matte.gloss == 0)
        #expect(TipLightStrengths(TipRecipe([])) == TipLightStrengths(specular: 0, holo: 0, gloss: 0))
    }
}
