"""小型等角投影像素繪圖（給號誌、平交道等很小的物件用；這種尺寸用 Blender 渲染會糊掉）。

座標與 OpenLoco 相同（旋轉 0）：世界 (x, y, z) → 畫面 (sx, sy) = (y - x, (x + y) / 2 - z)，1 世界單位 = 1 px。
相機位於 (1, 1, 1) 方向，深度 = x + y + z（越大越靠近觀看者）。

  c = Canvas()
  c.box((x0, y0, z0), (x1, y1, z1), ramp=0x0A, base=5)      # 長方體：頂面最亮、+x 面次之、+y 面最暗
  c.segment((x0, y0, z0), (x1, y1, z1), colour, r=0.5)      # 粗線段（圓柱近似）
  c.dot((x, y, z), colour)                                  # 單一像素（燈號等），可加 bias 讓它浮在表面上
  w, h, xoff, yoff, px = c.render()                         # 自動裁切；xoff/yoff 為 sprite 的繪製偏移
"""
from __future__ import annotations

import math

SHADE_TOP, SHADE_X, SHADE_Y = 2, 0, -2   # 各面相對 base 的明暗


def project(x: float, y: float, z: float) -> tuple[float, float]:
    return y - x, (x + y) / 2 - z


class Canvas:
    def __init__(self):
        self.px: dict[tuple[int, int], tuple[float, int]] = {}

    def plot(self, x, y, z, colour, bias=0.0):
        sx, sy = project(x, y, z)
        key = (int(math.floor(sx + 0.5)), int(math.floor(sy + 0.5)))
        d = x + y + z + bias
        cur = self.px.get(key)
        if cur is None or d >= cur[0]:
            self.px[key] = (d, colour)

    def box(self, a, b, ramp, base=6, step=0.25, colours=None):
        """實心長方體（只畫看得到的三個面）。colours 可指定 {top|x|y: 色號} 覆蓋 ramp 明暗。"""
        (x0, y0, z0), (x1, y1, z1) = [tuple(map(float, p)) for p in (a, b)]
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        z0, z1 = sorted((z0, z1))

        def col(face, shade):
            if colours and face in colours:
                return colours[face]
            return ramp + max(0, min(11, base + shade))

        def rng(a, b):
            n = max(1, int(math.ceil((b - a) / step)))
            return [a + (b - a) * k / n for k in range(n + 1)]
        for u in rng(x0, x1):
            for v in rng(y0, y1):
                self.plot(u, v, z1, col("top", SHADE_TOP))
        for v in rng(y0, y1):
            for w in rng(z0, z1):
                self.plot(x1, v, w, col("x", SHADE_X))
        for u in rng(x0, x1):
            for w in rng(z0, z1):
                self.plot(u, y1, w, col("y", SHADE_Y))

    def segment(self, a, b, colour, r=0.0, step=0.2):
        (x0, y0, z0), (x1, y1, z1) = a, b
        n = max(1, int(math.ceil(math.dist(a, b) / step)))
        offs = [(0, 0, 0)]
        if r > 0:
            offs = [(dx, dy, dz) for dx in (-r, 0, r) for dy in (-r, 0, r) for dz in (-r, 0, r)]
        for k in range(n + 1):
            t = k / n
            p = (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, z0 + (z1 - z0) * t)
            for dx, dy, dz in offs:
                c = colour(t) if callable(colour) else colour
                self.plot(p[0] + dx, p[1] + dy, p[2] + dz, c)

    def plate(self, origin, u, v, colour_at, step=0.2):
        """平面四邊形：origin + s*u + t*v（s, t ∈ [0,1]）；colour_at(s, t) 回傳色號或 None。"""
        nu = max(1, int(math.ceil(math.hypot(*u) / step)))
        nv = max(1, int(math.ceil(math.hypot(*v) / step)))
        for i in range(nu + 1):
            for j in range(nv + 1):
                s, t = i / nu, j / nv
                c = colour_at(s, t)
                if c is None:
                    continue
                self.plot(origin[0] + s * u[0] + t * v[0], origin[1] + s * u[1] + t * v[1],
                          origin[2] + s * u[2] + t * v[2], c)

    def dot(self, p, colour, bias=0.5):
        self.plot(*p, colour, bias=bias)

    def render(self, min_size=(1, 1)):
        """回傳 (w, h, x_offset, y_offset, pixels)。空白時回傳 1×1 透明圖。"""
        if not self.px:
            return 1, 1, 0, 0, bytes(1)
        xs = [k[0] for k in self.px]
        ys = [k[1] for k in self.px]
        x0, y0 = min(xs), min(ys)
        w, h = max(xs) - x0 + 1, max(ys) - y0 + 1
        w, h = max(w, min_size[0]), max(h, min_size[1])
        out = bytearray(w * h)
        for (sx, sy), (_d, c) in self.px.items():
            out[(sy - y0) * w + (sx - x0)] = c
        return w, h, x0, y0, bytes(out)


def facing_camera(normal) -> bool:
    """水平法向量 (nx, ny) 是否朝向相機（相機在 +x+y 方向）。"""
    return normal[0] + normal[1] > 1e-6


def rot(v, ang):
    """水平向量繞 z 軸旋轉。"""
    c, s = math.cos(ang), math.sin(ang)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c)
