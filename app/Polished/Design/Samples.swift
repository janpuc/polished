import NailTips
import SwiftUI

/// Invented shades for the placeholder screens and the widget until the API feeds them (run 2).
struct SampleShade: Identifiable {
    var id: Int { tip.id }
    var name: String
    var tip: TipShade
    var detail: String

    var recipe: TipRecipe { TipRecipe(tip) }

    static let spiritFingers = SampleShade(
        name: "Spirit Fingers", tip: TipShade(id: 12, hex: "#c72bb9", finishes: ["glitter", "holographic"]),
        detail: "Glitter, holographic")
    static let acidDrip = SampleShade(
        name: "Acid Drip",
        tip: TipShade(id: 31, hex: "#7be0c3", finishes: ["holographic", "metallic", "shimmer"]),
        detail: "Holographic, metallic, shimmer")
    static let herb = SampleShade(
        name: "Herb Your Enthusiasm", tip: TipShade(id: 4, hex: "#71ad44", finishes: ["creme"]), detail: "Creme")
    static let castASpell = SampleShade(
        name: "Cast a Spell", tip: TipShade(id: 17, hex: "#5a3a8c", finishes: ["magnetic"]), detail: "Magnetic")
    static let retina = SampleShade(
        name: "Retina Burner", tip: TipShade(id: 22, hex: "#ff4d6a", finishes: ["creme", "shimmer"]),
        detail: "Creme, shimmer")
    static let blackout = SampleShade(
        name: "One-Coat Black", tip: TipShade(id: 3, hex: "#16121a", finishes: ["creme"]), detail: "Creme")
    static let overstimulated = SampleShade(
        name: "Overstimulated", tip: TipShade(id: 40, hex: "#d9467e", finishes: ["jelly"]), detail: "Jelly")
    static let flakieHolo = SampleShade(
        name: "Flakie Holo Taco",
        tip: TipShade(id: 44, hex: "#e8e2f0", finishes: ["flakie", "holographic"], topper: true, colours: ["clear"]),
        detail: "Flakie, holographic topper")

    static let all = [spiritFingers, acidDrip, herb, castASpell, retina, blackout, overstimulated, flakieHolo]
}
