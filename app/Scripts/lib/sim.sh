# Sourced: finding and preparing simulators.

# udid_for "iPhone 18 Pro" 27.0
udid_for() {
  xcrun simctl list devices available -j | python3 -c '
import json, sys
name, os = sys.argv[1:3]
for runtime, devices in json.load(sys.stdin)["devices"].items():
    if runtime.endswith("iOS-" + os.replace(".", "-")):
        for d in devices:
            if d["name"] == name:
                print(d["udid"])
' "$1" "$2" | head -1
}

# boot_sim UDID: booted, with the slide-to-type introduction already dismissed (it covers the
# keyboard on a fresh simulator and the UI tests type into the search field).
boot_sim() {
  # A simulator that has been up for a while sometimes never starts the test runner (the Duo did):
  # every run starts from a fresh boot.
  xcrun simctl shutdown "$1" 2>/dev/null || true
  sleep 5
  xcrun simctl boot "$1" 2>/dev/null || true
  xcrun simctl bootstatus "$1" -b >/dev/null
  sleep 10
  xcrun simctl spawn "$1" defaults write com.apple.keyboard.preferences DidShowContinuousPathIntroduction -bool true
}
