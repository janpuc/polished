"""Renames the files `xcresulttool export attachments` wrote (UUID names) to the attachment names
of manifest.json, e.g. gallery-03.png, and removes the manifest's UUID leftovers.

    python3 rename_attachments.py <export dir>
"""

import json
import re
import sys
from pathlib import Path

folder = Path(sys.argv[1])
manifest = json.loads((folder / "manifest.json").read_text())
for test in manifest:
    for item in test["attachments"]:
        source = folder / item["exportedFileName"]
        # "gallery-30_0_<uuid>.png" -> "gallery-30.png"
        name = re.sub(r"_\d+_[0-9A-F-]{36}(?=\.)", "", item["suggestedHumanReadableName"])
        if source.exists():
            source.rename(folder / name)
