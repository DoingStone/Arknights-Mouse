# -*- coding: utf-8 -*-
"""Map the PRTS pack's files onto the 21 Windows cursor ROLES, and list distinct art."""
import os, collections, re

ROOT = r"C:\Users\22442\AppData\Local\PRTS\Replica-v8-Windows\cursors-34497b84e5b0d7cf"

# Which .cur is bound to which registry role right now?
ROLES = {
    "Arrow": "normal", "Help": "helpsel", "AppStarting": "work", "Wait": "busy_static",
    "Crosshair": "cross", "IBeam": "beam", "NWPen": "pen", "No": "unavail1",
    "SizeNS": "sel_1", "SizeWE": "sel_2", "SizeNWSE": "sel_3", "SizeNESW": "sel_4",
    "SizeAll": "move", "UpArrow": "up", "Hand": "link", "Pin": "pin", "Person": "person",
}

names = sorted(os.listdir(ROOT))
stems = collections.Counter()
for fn in names:
    m = re.match(r"PRTS-Replica-v8-96x-(.+)\.(cur|ani)$", fn)
    if m:
        stems[m.group(1)] += 1

print("distinct stems: %d" % len(stems))
# group: static singles vs numbered frame runs
numbered = collections.Counter()
single = []
for s in stems:
    b = re.sub(r"_\d+$", "", s)
    if re.search(r"_\d+$", s):
        numbered[b] += 1
    else:
        single.append(s)

print("\nnon-numbered stems (%d):" % len(single))
for s in single:
    print("   ", s)
print("\nnumbered frame-run families (%d):" % len(numbered))
for b, c in sorted(numbered.items()):
    print("   %-34s x%d" % (b, c))

print("\n[Windows role -> exact file present in pack]")
for role, need in ROLES.items():
    hits = [f for f in names if re.match(r"PRTS-Replica-v8-96x-%s\.(cur|ani)$" % re.escape(need), f)]
    print("   %-13s %-14s -> %s" % (role, need, hits[0] if hits else "(MISSING)"))
