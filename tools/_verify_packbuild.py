# -*- coding: utf-8 -*-
"""探针15：packbuild 现场生成的指针，和仓库里那份是不是同一套东西？

比两件事：
  1. **画面**：逐帧 icon 载荷（那一整份 .cur）必须逐字节相同；
  2. **播放**：帧数、每帧实际延时（jiffy）必须相同。

第 2 条不能直接比 rate 块 —— 仓库里那份把「所有帧节拍一样」的情况折进了
`anih.iDispRate`（省掉 rate 块），生成的这份一律写显式 rate 块。两者的
播放效果完全一样（例如 No：iDispRate=4 与 rate=4 等价），所以校验的是
**折算后的每帧延时**，不是字节。

静态角色的 .cur 则要求逐字节相同（没有节拍这层歧义）。
"""
import hashlib
import os
import shutil
import struct
import sys
import tempfile
import time

ROOT = r"E:\Qianmory\Desktop\Mouse"
sys.path.insert(0, os.path.join(ROOT, "src", "arkmouse"))

import cursorwin as cw          # noqa: E402
import packbuild                # noqa: E402

ART = os.path.join(ROOT, "src", "arkmouse", "art.bin")
REPO_PACK = os.path.join(ROOT, "cursors")
TIER = "p72"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ani_parts(path):
    raw = open(path, "rb").read()
    if raw[:4] != b"RIFF":
        raise ValueError("不是 RIFF：%s" % path)
    q = 12
    anih = None
    rate = None
    frames = []
    while q + 8 <= len(raw):
        cid = raw[q:q + 4]
        sz = struct.unpack_from("<I", raw, q + 4)[0]
        payload = raw[q + 8:q + 8 + sz]
        if cid == b"anih":
            anih = struct.unpack("<9I", payload)
        elif cid == b"rate":
            rate = list(struct.unpack("<%dI" % (sz // 4), payload))
        elif cid == b"LIST":
            p, end = q + 12, q + 8 + sz
            while p + 8 <= end:
                fsz = struct.unpack_from("<I", raw, p + 4)[0]
                frames.append(raw[p + 8:p + 8 + fsz])
                p += 8 + fsz + (fsz & 1)
        q += 8 + sz + (sz & 1)
    return anih, rate, frames


def delays(anih, rate, n):
    """折算成每帧实际延时（jiffy）。没有 rate 块时全帧都用 iDispRate。"""
    disp = anih[7] if anih else 1
    if rate is None:
        return [disp] * n
    return (list(rate[:n]) + [rate[-1]] * max(0, n - len(rate)))


def main():
    tier = [t for t in cw.PACK_TIERS if t[0] == TIER][0]
    print("档位 = %s（gain=%.4f）" % (tier[0], tier[1]))

    tmp = tempfile.mkdtemp(prefix="probe15_")
    try:
        t0 = time.time()
        n = packbuild.build_tier(ART, tmp, tier[0], tier[1])
        print("生成 %d 个文件，用时 %.2f 秒\n" % (n, time.time() - t0))

        mine = packbuild.tier_dir(tmp, tier[0])
        repo = packbuild.tier_dir(REPO_PACK, tier[0])

        ok = bad = 0
        raw_same = 0
        for r in cw.ROLES:
            key = r[0]
            animated = key in cw.ANIMATED
            name = packbuild.file_name(key, tier[0], animated)
            a = os.path.join(mine, name)
            b = os.path.join(repo, name)
            if not os.path.isfile(b):
                print("  %-36s 仓库里没有" % name)
                bad += 1
                continue

            if sha(a) == sha(b):
                raw_same += 1

            if not animated:
                same = sha(a) == sha(b)
                print("  %-36s CUR  %s" % (name, "逐字节相同" if same else "不同！"))
                ok, bad = (ok + 1, bad) if same else (ok, bad + 1)
                continue

            an_a, rt_a, fr_a = ani_parts(a)
            an_b, rt_b, fr_b = ani_parts(b)
            frames_same = fr_a == fr_b
            d_a = delays(an_a, rt_a, len(fr_a))
            d_b = delays(an_b, rt_b, len(fr_b))
            delay_same = d_a == d_b
            tag = "逐字节相同" if sha(a) == sha(b) else "字节不同但语义相同"
            if frames_same and delay_same:
                ok += 1
                print("  %-36s ANI  %s  帧 %d · 节拍 %s jiffy"
                      % (name, tag, len(fr_a), sorted(set(d_a))))
            else:
                bad += 1
                print("  %-36s ANI  不一致！ 帧相同=%s 节拍相同=%s (新%s 旧%s)"
                      % (name, frames_same, delay_same,
                         sorted(set(d_a))[:4], sorted(set(d_b))[:4]))

        print("\n语义一致 %d / 不一致 %d   （其中逐字节相同 %d）"
              % (ok, bad, raw_same))
        print("结论：%s" % ("生成器与仓库产品等价" if bad == 0 else "有问题"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
