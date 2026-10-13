# -*- coding: utf-8 -*-
"""Hunt for a higher-resolution PRTS Replica source: installer URL, cached payloads,
   other variants (256x), and any leftover archives."""
import os, re, collections, subprocess

LOCAL = r"C:\Users\22442\AppData\Local"
PRTS = os.path.join(LOCAL, "PRTS")
CACHE = os.path.join(PRTS, "InstallerWebCache")

url_re = re.compile(rb"https?://[\x21-\x7e]{6,300}")
hits = collections.Counter()

print("[1] scanning WebView2 cache for URLs mentioning prts/replica/cursor")
scanned = 0
for dp, dn, fns in os.walk(CACHE):
    for fn in fns:
        p = os.path.join(dp, fn)
        try:
            if os.path.getsize(p) > 40 * 1024 * 1024:
                continue
            b = open(p, "rb").read()
        except OSError:
            continue
        scanned += 1
        for m in url_re.findall(b):
            u = m.decode("ascii", "replace")
            low = u.lower()
            if any(k in low for k in ("prts", "replica", "cursor", "cursors", "download",
                                      "release", "asset", "package", "pack")):
                hits[u] += 1
print("   files scanned:", scanned, " url hits:", len(hits))
for u, c in hits.most_common(40):
    print("   x%-4d %s" % (c, u[:200]))

print("\n[2] any PRTS-ish files left anywhere in LOCALAPPDATA / APPDATA / TEMP]")
pat = re.compile(r"prts|replica", re.I)
roots = [LOCAL, os.path.join(os.path.expanduser("~"), "AppData", "Roaming"),
         os.environ.get("TEMP", "")]
for root in roots:
    if not root or not os.path.isdir(root):
        continue
    for dp, dn, fns in os.walk(root):
        dn[:] = [d for d in dn if not d.startswith(".")]
        for fn in fns:
            if pat.search(fn):
                p = os.path.join(dp, fn)
                try:
                    print("   %10d  %s" % (os.path.getsize(p), p))
                except OSError:
                    pass

print("\n[3] uninstall / publisher registry entries mentioning PRTS")
ps = (r"$p='HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',"
      r"'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',"
      r"'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*';"
      r"Get-ItemProperty $p -EA 0 | Where-Object { $_.DisplayName -match 'PRTS|Replica|Cursor' } |"
      r" Select-Object DisplayName,DisplayVersion,InstallLocation,UninstallString,URLInfoAbout | Format-List")
r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True, text=True)
print(r.stdout.strip() or "(none)")

print("\n[4] HKCU:\\Control Panel\\Cursors\\Schemes  (all registered scheme names)")
ps2 = (r"Get-Item 'HKCU:\Control Panel\Cursors\Schemes' | "
       r"Select-Object -ExpandProperty Property")
r2 = subprocess.run(["powershell", "-NoProfile", "-Command", ps2],
                    capture_output=True, text=True)
for line in r2.stdout.splitlines():
    if line.strip():
        print("   ", line.strip()[:120])
