# -*- coding: utf-8 -*-
"""自包含美术包 art.bin 的读取器。

art.bin 布局（小端）：
  magic  b'AKPT1\\x00\\x00\\x00'        8 字节
  jlen   uint32                       JSON 索引字节数
  jdata  jlen 字节 UTF-8 JSON
  blobs  依次拼接的 PNG

索引结构：
  {"roles": {"Arrow": {"hot": [28,20], "rate": null|[...],
                       "frames": [[off, len], ...]}, ...}}
"""
import io
import json
import struct

from PIL import Image

MAGIC = b'AKPT1\x00\x00\x00'
_PACKS = {}
_FRAME_CACHE = {}


class ArtPack(object):
    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as f:
            raw = f.read()
        if raw[:8] != MAGIC:
            raise ValueError('不是 art.bin（magic 不符）')
        jlen = struct.unpack_from('<I', raw, 8)[0]
        self.index = json.loads(raw[12:12 + jlen].decode('utf-8'))
        self.base = 12 + jlen
        self._raw = raw
        # 索引可以是 {"roles": {...}}，也可以直接是 {角色: {...}}
        if 'roles' in self.index and isinstance(self.index['roles'], dict):
            self._roles = self.index['roles']
        else:
            self._roles = self.index

    @property
    def roles(self):
        return list(self._roles.keys())

    def info(self, key):
        return self._roles.get(key)

    def hotspot(self, key):
        info = self._roles.get(key)
        if not info:
            return None
        h = info['hot']
        return (int(h[0]), int(h[1]))

    def frame_count(self, key):
        info = self._roles.get(key)
        return len(info['frames']) if info else 0

    def rates_ms(self, key):
        """返回每帧延时列表；None 表示静态或用默认节拍。"""
        info = self._roles.get(key)
        if not info:
            return None
        return info.get('rate')

    def frame_image(self, key, idx):
        info = self._roles.get(key)
        if not info:
            return None
        fr = info['frames']
        if not fr:
            return None
        off, ln = fr[idx % len(fr)]
        return Image.open(io.BytesIO(
            self._raw[self.base + off:self.base + off + ln])).convert('RGBA')

    def frames(self, key):
        """返回 [(Image, hotx, hoty), ...]，带缓存。"""
        ck = (self.path, key)
        if ck in _FRAME_CACHE:
            return _FRAME_CACHE[ck]
        info = self._roles.get(key)
        if not info:
            _FRAME_CACHE[ck] = []
            return []
        hx, hy = self.hotspot(key)
        out = []
        for i in range(len(info['frames'])):
            im = self.frame_image(key, i)
            if im is not None:
                out.append((im, hx, hy))
        _FRAME_CACHE[ck] = out
        return out


def load(path):
    p = _PACKS.get(path)
    if p is None:
        p = ArtPack(path)
        _PACKS[path] = p
    return p
