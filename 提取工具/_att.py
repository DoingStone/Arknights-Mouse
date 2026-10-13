import os, glob
from PIL import Image
A = r'C:\Users\22442\.dsh\attachments\v1\objects'
rows = []
for p in glob.glob(os.path.join(A, '*', '*')):
    try:
        im = Image.open(p)
        rows.append((im.width, im.height, im.mode, os.path.getsize(p), os.path.getmtime(p), p))
    except Exception:
        pass
rows.sort(key=lambda r: -r[4])
for w, h, m, sz, t, p in rows[:18]:
    import time
    print('%5dx%-5d %-5s %9d  %s  %s' % (w, h, m, sz, time.strftime('%m-%d %H:%M', time.localtime(t)), p[-24:]))
