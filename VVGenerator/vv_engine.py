# -*- coding: utf-8 -*-
"""
VV Generator - geometry engine.

Pure Python (no Autodesk modules), so it can be unit-tested outside Fusion 360.
All lengths are in centimetres (Fusion's internal unit).

Pipeline
    1. Domain      : the 2D outline of the planar face (outer contour + holes), with spatial indexes.
    2. Reinforcement: 3D sample points of holes / chosen faces -> density field and keep-out discs.
    3. Cells       : Voronoi cells (constant wall) or regular tiles (hexagon / triangle).
    4. Trimming    : every cell is cut by supporting half-planes of "capsules" built around the
                     outline (radius = solid rim) and of the keep-out discs.  Because each capsule
                     is convex, the resulting convex cell is *guaranteed* to stay inside the face,
                     at least `rim` away from the outline, even for concave / irregular faces.
    5. Verification: every item is re-checked against brute-force geometry before it is returned
                     and a measured analysis (areas, walls, coverage gaps) is produced.
"""
import math
import random
import time

__version__ = '1.7.0'

SQRT3 = math.sqrt(3.0)
SHAPES = ('voronoi', 'rounded', 'hex', 'tri', 'circle')


class EngineError(Exception):
    """Error with a machine-readable code (the Fusion layer translates it)."""

    def __init__(self, code, **info):
        Exception.__init__(self, code)
        self.code = code
        self.info = info


class Params(object):
    """All engine parameters (centimetres / radians)."""

    def __init__(self, **kw):
        self.shape = 'voronoi'
        self.wall = 0.12
        self.hmin = 0.6
        self.hmax = 1.6
        self.infl = 3.0
        self.rim = 0.4
        self.keep = 0.4
        self.max_cells = 400
        self.seed = 1
        self.corner_r = 0.0
        self.tile = 0.9
        self.wall_max = 0.25
        self.angle = 0.0
        self.relax = 3            # Lloyd relaxation iterations (Voronoi / circles), 0 = off
        self.sites = None         # optional user seed points [(x, y), ...] in the sketch plane
        self.sites_only = False   # use ONLY the user points (no automatic seeds)
        for k, v in kw.items():
            if not hasattr(self, k):
                raise TypeError('unknown parameter: %s' % k)
            setattr(self, k, v)

    @property
    def tiling(self):
        return self.shape in ('hex', 'tri')


# ----------------------------------------------------------------------------
# Basic 2D geometry
# ----------------------------------------------------------------------------
def clip(poly, a, b, c):
    """Keep the part of a convex polygon with a*x + b*y <= c (Sutherland-Hodgman)."""
    out = []
    n = len(poly)
    for k in range(n):
        p = poly[k]
        q = poly[(k + 1) % n]
        fp = a * p[0] + b * p[1] - c
        fq = a * q[0] + b * q[1] - c
        if fp <= 0:
            out.append(p)
        if (fp < 0 and fq > 0) or (fp > 0 and fq < 0):
            t = fp / (fp - fq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def poly_area(poly):
    s = 0.0
    n = len(poly)
    for k in range(n):
        x1, y1 = poly[k]
        x2, y2 = poly[(k + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) * 0.5


def poly_perimeter(poly):
    n = len(poly)
    return sum(math.hypot(poly[(k + 1) % n][0] - poly[k][0], poly[(k + 1) % n][1] - poly[k][1]) for k in range(n))


def dedupe(poly, tol):
    """Merge vertices closer than tol. For a convex polygon this can only shrink it."""
    out = []
    for p in poly:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > tol:
            out.append(p)
    while len(out) > 1 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) <= tol:
        out.pop()
    return out


def drop_collinear(poly, tol=1e-5):
    """Remove (nearly) collinear vertices of a convex polygon (shrinks it by < tol)."""
    pts = list(poly)
    changed = True
    while changed and len(pts) > 3:
        changed = False
        for i in range(len(pts)):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            ac = math.hypot(c[0] - a[0], c[1] - a[1])
            if ac < 1e-12:
                continue
            h = abs((c[0] - a[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (c[1] - a[1])) / ac
            if h < tol:
                del pts[i]
                changed = True
                break
    return pts


def seg_nearest(px, py, ax, ay, bx, by):
    """Nearest point of segment AB to P."""
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 <= 1e-18:
        return ax, ay
    t = ((px - ax) * dx + (py - ay) * dy) / l2
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return ax + t * dx, ay + t * dy


def convex_contains(poly, x, y, eps=1e-9):
    pos = neg = False
    n = len(poly)
    for k in range(n):
        x1, y1 = poly[k]
        x2, y2 = poly[(k + 1) % n]
        cr = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
        if cr > eps:
            pos = True
        elif cr < -eps:
            neg = True
        if pos and neg:
            return False
    return True


def poly_point_dist(poly, x, y):
    """Distance from a point to a convex polygon (0 if inside)."""
    if convex_contains(poly, x, y):
        return 0.0
    best = 1e18
    n = len(poly)
    for k in range(n):
        ax, ay = poly[k]
        bx, by = poly[(k + 1) % n]
        qx, qy = seg_nearest(x, y, ax, ay, bx, by)
        d = (x - qx) ** 2 + (y - qy) ** 2
        if d < best:
            best = d
    return math.sqrt(best)


def poly_poly_dist(pa, pb):
    """Distance between two disjoint convex polygons (vertex-to-edge is sufficient)."""
    best = 1e18
    for A, B in ((pa, pb), (pb, pa)):
        nb = len(B)
        for (x, y) in A:
            for k in range(nb):
                qx, qy = seg_nearest(x, y, B[k][0], B[k][1], B[(k + 1) % nb][0], B[(k + 1) % nb][1])
                d = (x - qx) ** 2 + (y - qy) ** 2
                if d < best:
                    best = d
    return math.sqrt(best)


def smooth(t):
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return t * t * (3.0 - 2.0 * t)


# ----------------------------------------------------------------------------
# Corner rounding (shared by drawing and area statistics)
# ----------------------------------------------------------------------------
def corner_data(poly, r):
    """Per-corner fillet data for a convex polygon.
    Returns a list of tuples (A, M, B, ri, theta) or None for sharp corners."""
    n = len(poly)
    out = []
    for i in range(n):
        v, p, q = poly[i], poly[i - 1], poly[(i + 1) % n]
        ax, ay, bx, by = p[0] - v[0], p[1] - v[1], q[0] - v[0], q[1] - v[1]
        la, lb = math.hypot(ax, ay), math.hypot(bx, by)
        if la < 1e-12 or lb < 1e-12:
            out.append(None)
            continue
        ax, ay, bx, by = ax / la, ay / la, bx / lb, by / lb
        th = math.acos(max(-1.0, min(1.0, ax * bx + ay * by)))
        ri = 0.0
        if r > 0 and 0.05 < th < math.pi - 0.05:
            ri = min(r, 0.5 * min(la, lb) * math.tan(th / 2))
        if ri < 0.01:
            out.append(None)
            continue
        t = ri / math.tan(th / 2)
        a_pt = (v[0] + ax * t, v[1] + ay * t)
        b_pt = (v[0] + bx * t, v[1] + by * t)
        sx, sy = ax + bx, ay + by
        sl = math.hypot(sx, sy)
        dist = ri / math.sin(th / 2) - ri
        m_pt = (v[0] + sx / sl * dist, v[1] + sy / sl * dist)
        out.append((a_pt, m_pt, b_pt, ri, th))
    return out


def path_prims(poly, r):
    """Closed outline as ('L', p0, p1) and ('A', p0, pmid, p1) primitives."""
    n = len(poly)
    cd = corner_data(poly, r)
    prims = []
    for i in range(n):
        if cd[i] is not None:
            prims.append(('A', cd[i][0], cd[i][1], cd[i][2]))
        end_i = cd[i][2] if cd[i] is not None else poly[i]
        j = (i + 1) % n
        start_j = cd[j][0] if cd[j] is not None else poly[j]
        if math.hypot(start_j[0] - end_i[0], start_j[1] - end_i[1]) > 0.005:
            prims.append(('L', end_i, start_j))
    return prims


def rounded_area(poly, r):
    a = poly_area(poly)
    for c in corner_data(poly, r):
        if c is not None:
            ri, th = c[3], c[4]
            t = ri / math.tan(th / 2)
            a -= t * ri - 0.5 * ri * ri * (math.pi - th)
    return a


# ----------------------------------------------------------------------------
# Spatial structures
# ----------------------------------------------------------------------------
class Domain(object):
    """2D face outline (all loops) with accelerated inside / distance queries."""

    def __init__(self, segs, cell):
        self.segs = [s for s in segs if math.hypot(s[2] - s[0], s[3] - s[1]) > 1e-7]
        if not self.segs:
            raise EngineError('no_outline')
        xs = [s[0] for s in self.segs] + [s[2] for s in self.segs]
        ys = [s[1] for s in self.segs] + [s[3] for s in self.segs]
        self.minx, self.maxx, self.miny, self.maxy = min(xs), max(xs), min(ys), max(ys)
        # horizontal bands for the even-odd test
        n = len(self.segs)
        self.nb = int(max(16, min(4096, math.sqrt(n) * 8)))
        self.bh = (self.maxy - self.miny) / self.nb or 1.0
        self.bands = [[] for _ in range(self.nb)]
        for k, (ax, ay, bx, by) in enumerate(self.segs):
            lo = self._band(min(ay, by))
            hi = self._band(max(ay, by))
            for b in range(lo, hi + 1):
                self.bands[b].append(k)
        # bucket grid for nearest-segment queries
        self.cs = max(cell, 1e-3)
        self.grid = {}
        cs = self.cs
        for k, (ax, ay, bx, by) in enumerate(self.segs):
            length = math.hypot(bx - ax, by - ay)
            steps = max(1, int(length / (cs * 0.5))) + 1
            for t in range(steps + 1):
                x = ax + (bx - ax) * t / steps
                y = ay + (by - ay) * t / steps
                self.grid.setdefault((int(math.floor(x / cs)), int(math.floor(y / cs))), set()).add(k)
        self.total_length = sum(math.hypot(s[2] - s[0], s[3] - s[1]) for s in self.segs)
        self._ncache = {}
        self.sd = [(a, b, c - a, d - b, 1.0 / ((c - a) ** 2 + (d - b) ** 2)) for a, b, c, d in self.segs]

    def _band(self, y):
        b = int((y - self.miny) / self.bh)
        return 0 if b < 0 else (self.nb - 1 if b >= self.nb else b)

    def inside(self, x, y):
        if y < self.miny or y > self.maxy or x < self.minx - 1e-9 or x > self.maxx + 1e-9:
            return False
        cnt = 0
        segs = self.segs
        for k in self.bands[self._band(y)]:
            ax, ay, bx, by = segs[k]
            if (ay > y) != (by > y):
                if ax + (y - ay) * (bx - ax) / (by - ay) > x:
                    cnt += 1
        return cnt & 1 == 1

    def near(self, x, y, r):
        cs = self.cs
        n = int(math.ceil(r / cs)) + 1
        gx, gy = int(math.floor(x / cs)), int(math.floor(y / cs))
        key = (gx, gy, n)
        hit = self._ncache.get(key)
        if hit is not None:
            return hit
        out = set()
        g = self.grid
        for ix in range(gx - n, gx + n + 1):
            for iy in range(gy - n, gy + n + 1):
                b = g.get((ix, iy))
                if b:
                    out.update(b)
        res = tuple(out)
        if len(self._ncache) < 400000:
            self._ncache[key] = res
        return res

    def dist(self, x, y, cap):
        """Distance to the outline, capped at `cap` (returns exactly cap if nothing is closer)."""
        best = cap * cap
        sd = self.sd
        for k in self.near(x, y, cap):
            ax, ay, dx, dy, il2 = sd[k]
            t = ((x - ax) * dx + (y - ay) * dy) * il2
            if t < 0.0:
                t = 0.0
            elif t > 1.0:
                t = 1.0
            ex = x - ax - t * dx
            ey = y - ay - t * dy
            d = ex * ex + ey * ey
            if d < best:
                best = d
        return math.sqrt(best)

    def near_sorted(self, x, y, r):
        out = []
        sd = self.sd
        r2 = r * r
        for k in self.near(x, y, r):
            ax, ay, dx, dy, il2 = sd[k]
            t = ((x - ax) * dx + (y - ay) * dy) * il2
            if t < 0.0:
                t = 0.0
            elif t > 1.0:
                t = 1.0
            qx = ax + t * dx
            qy = ay + t * dy
            d2 = (x - qx) ** 2 + (y - qy) ** 2
            if d2 <= r2:
                out.append((math.sqrt(d2), qx, qy))
        out.sort()
        return out


class DiscSet(object):
    """Keep-out discs (x, y, r) with a bucket grid."""

    def __init__(self, discs):
        self.discs = list(discs)
        self.maxr = max([d[2] for d in self.discs] or [0.0])
        self.cs = max(2 * self.maxr, 0.5)
        self.grid = {}
        for i, (x, y, r) in enumerate(self.discs):
            self.grid.setdefault((int(math.floor(x / self.cs)), int(math.floor(y / self.cs))), []).append(i)

    def __len__(self):
        return len(self.discs)

    def near(self, x, y, r):
        n = int(math.ceil((r + self.maxr) / self.cs)) + 1
        gx, gy = int(math.floor(x / self.cs)), int(math.floor(y / self.cs))
        out = []
        for ix in range(gx - n, gx + n + 1):
            for iy in range(gy - n, gy + n + 1):
                for i in self.grid.get((ix, iy), ()):
                    out.append(self.discs[i])
        return out

    def clearance(self, x, y, cap):
        """min(distance to any disc edge, cap) (negative if inside a disc)."""
        best = cap
        for (cx, cy, r) in self.near(x, y, cap):
            d = math.hypot(x - cx, y - cy) - r
            if d < best:
                best = d
        return best


class Reinforcement(object):
    """Reinforcement sample points (3D) and the sketch plane frame."""

    def __init__(self, pts, frame, reach):
        self.pts = list(pts)
        self.o, self.ex, self.ey = frame['o'], frame['ex'], frame['ey']
        n = (self.ex[1] * self.ey[2] - self.ex[2] * self.ey[1],
             self.ex[2] * self.ey[0] - self.ex[0] * self.ey[2],
             self.ex[0] * self.ey[1] - self.ex[1] * self.ey[0])
        nl = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
        self.nrm = (n[0] / nl, n[1] / nl, n[2] / nl)
        self.reach = max(reach, 1e-3)
        self.grid = {}
        self._nbc = {}
        cs = self.reach
        for p in self.pts:
            self.grid.setdefault((int(math.floor(p[0] / cs)), int(math.floor(p[1] / cs)), int(math.floor(p[2] / cs))),
                                 []).append(p)

    @property
    def present(self):
        return bool(self.pts)

    def to3d(self, x, y):
        o, ex, ey = self.o, self.ex, self.ey
        return (o[0] + x * ex[0] + y * ey[0], o[1] + x * ex[1] + y * ey[1], o[2] + x * ex[2] + y * ey[2])

    def dist(self, x, y):
        """Distance (3D) to the nearest reinforcement point, capped at `reach`."""
        if not self.pts:
            return self.reach
        X, Y, Z = self.to3d(x, y)
        cs = self.reach
        key = (int(math.floor(X / cs)), int(math.floor(Y / cs)), int(math.floor(Z / cs)))
        pts = self._nbc.get(key)
        if pts is None:
            g = self.grid
            lst = []
            for ix in (key[0] - 1, key[0], key[0] + 1):
                for iy in (key[1] - 1, key[1], key[1] + 1):
                    for iz in (key[2] - 1, key[2], key[2] + 1):
                        lst.extend(g.get((ix, iy, iz), ()))
            pts = tuple(lst)
            self._nbc[key] = pts
        best = cs * cs
        for (a, b, c) in pts:
            d = (a - X) ** 2 + (b - Y) ** 2 + (c - Z) ** 2
            if d < best:
                best = d
        return math.sqrt(best)

    def discs(self, keep):
        """Keep-out discs in the sketch plane (sphere of radius `keep` cut by the plane)."""
        if keep <= 0:
            return []
        o, ex, ey, nrm = self.o, self.ex, self.ey, self.nrm
        cellk = 0.01      # only merge (almost) coincident sample points
        out = {}
        for (a, b, c) in self.pts:
            vx, vy, vz = a - o[0], b - o[1], c - o[2]
            dp = abs(vx * nrm[0] + vy * nrm[1] + vz * nrm[2])
            if dp >= keep:
                continue
            r = math.sqrt(keep * keep - dp * dp)
            x2 = vx * ex[0] + vy * ex[1] + vz * ex[2]
            y2 = vx * ey[0] + vy * ey[1] + vz * ey[2]
            key = (int(round(x2 / cellk)), int(round(y2 / cellk)))
            if key not in out or out[key][2] < r:
                out[key] = (x2, y2, r)
        return list(out.values())


class SeedSet(object):
    def __init__(self, cell):
        self.cs = max(cell, 1e-3)
        self.grid = {}
        self.pts = []

    def __len__(self):
        return len(self.pts)

    def add(self, x, y, h):
        self.pts.append((x, y, h))
        self.grid.setdefault((int(math.floor(x / self.cs)), int(math.floor(y / self.cs))), []).append(len(self.pts) - 1)

    def near(self, x, y, r):
        cs = self.cs
        n = int(math.ceil(r / cs))
        gx, gy = int(math.floor(x / cs)), int(math.floor(y / cs))
        out = []
        for ix in range(gx - n, gx + n + 1):
            for iy in range(gy - n, gy + n + 1):
                for i in self.grid.get((ix, iy), ()):
                    out.append(i)
        return out

    def too_close(self, x, y, h, factor, min_abs=0.0):
        for i in self.near(x, y, max(self.cs, min_abs)):
            sx, sy, sh = self.pts[i]
            r = max(factor * 0.5 * (h + sh), min_abs)
            if (x - sx) ** 2 + (y - sy) ** 2 < r * r:
                return True
        return False


class PolyIndex(object):
    """Bucket index of convex polygons for 'is covered / distance to nearest' queries."""

    def __init__(self, polys, cell):
        self.polys = polys
        self.cs = max(cell, 1e-3)
        self.grid = {}
        self.boxes = []
        cs = self.cs
        for i, p in enumerate(polys):
            xs = [v[0] for v in p]
            ys = [v[1] for v in p]
            self.boxes.append((min(xs), max(xs), min(ys), max(ys)))
            for ix in range(int(math.floor(min(xs) / cs)), int(math.floor(max(xs) / cs)) + 1):
                for iy in range(int(math.floor(min(ys) / cs)), int(math.floor(max(ys) / cs)) + 1):
                    self.grid.setdefault((ix, iy), []).append(i)

    def dist(self, x, y, cap):
        cs = self.cs
        gx0, gx1 = int(math.floor((x - cap) / cs)), int(math.floor((x + cap) / cs))
        gy0, gy1 = int(math.floor((y - cap) / cs)), int(math.floor((y + cap) / cs))
        seen = set()
        best = cap
        boxes = self.boxes
        for ix in range(gx0, gx1 + 1):
            for iy in range(gy0, gy1 + 1):
                for i in self.grid.get((ix, iy), ()):
                    if i in seen:
                        continue
                    seen.add(i)
                    x0, x1, y0, y1 = boxes[i]
                    if x < x0 - best or x > x1 + best or y < y0 - best or y > y1 + best:
                        continue
                    d = poly_point_dist(self.polys[i], x, y)
                    if d < best:
                        best = d
                        if best <= 0.0:
                            return 0.0
        return best


# ----------------------------------------------------------------------------
# Context shared by the generators
# ----------------------------------------------------------------------------
class Ctx(object):
    def __init__(self, P, dom, reinf):
        self.P = P
        self.dom = dom
        self.reinf = reinf
        self.rim = max(P.rim, 0.01)
        self.wall = P.wall
        self.discs = DiscSet(reinf.discs(P.keep)) if reinf.present else DiscSet([])
        self.rnd = random.Random(P.seed)

    def h(self, x, y):
        """Local target cell size."""
        P = self.P
        if not self.reinf.present:
            return 0.5 * (P.hmin + P.hmax)
        d = self.reinf.dist(x, y)
        return P.hmin + (P.hmax - P.hmin) * smooth((d - P.keep) / P.infl)

    def wall_at(self, x, y):
        """Local wall thickness (tilings): thick near reinforcement, thin far from it."""
        P = self.P
        if not self.reinf.present:
            return P.wall
        d = self.reinf.dist(x, y)
        return P.wall_max + (P.wall - P.wall_max) * smooth((d - P.keep) / P.infl)

    def free_point(self, x, y, margin=0.0):
        """Inside the face, >= rim+margin from the outline and outside keep-out discs."""
        if not self.dom.inside(x, y):
            return False
        m = self.rim + margin
        if self.dom.dist(x, y, m) < m - 1e-12:
            return False
        if len(self.discs) and self.discs.clearance(x, y, margin + 1e-9) < margin - 1e-12:
            return False
        return True


def trim_poly(poly, ax, ay, ctx):
    """Cut a convex polygon that contains the anchor (ax, ay) with the supporting half-planes of
    (a) capsules of radius `rim` around every outline segment and (b) the keep-out discs.
    The anchor must be a free point. Returns the trimmed polygon or None."""
    rim = ctx.rim
    rc = max(math.hypot(x - ax, y - ay) for x, y in poly)
    for d, qx, qy in ctx.dom.near_sorted(ax, ay, rc + rim + 1e-9):
        if d < rim - 1e-9 or d < 1e-12:
            return None
        ux, uy = (ax - qx) / d, (ay - qy) / d
        c = ux * qx + uy * qy + rim
        if min(ux * x + uy * y for x, y in poly) >= c - 1e-12:
            continue
        poly = clip(poly, -ux, -uy, -c)
        if len(poly) < 3:
            return None
    if len(ctx.discs):
        for (cx, cy, r) in ctx.discs.near(ax, ay, rc):
            d = math.hypot(ax - cx, ay - cy)
            if d <= r + 1e-9:
                return None
            ux, uy = (ax - cx) / d, (ay - cy) / d
            c = ux * cx + uy * cy + r
            if min(ux * x + uy * y for x, y in poly) >= c - 1e-12:
                continue
            poly = clip(poly, -ux, -uy, -c)
            if len(poly) < 3:
                return None
    return poly


def _needs_trim(poly, ax, ay, ctx):
    rc = max(math.hypot(x - ax, y - ay) for x, y in poly)
    if ctx.dom.dist(ax, ay, ctx.rim + rc + 1e-6) < ctx.rim + rc + 1e-6 - 1e-12:
        return True
    if len(ctx.discs) and ctx.discs.clearance(ax, ay, rc + 1e-6) < rc + 1e-6 - 1e-12:
        return True
    return False


def _min_width(poly):
    """Lower bound for the inscribed-circle diameter of a convex polygon: 4A/P."""
    p = poly_perimeter(poly)
    return 4.0 * poly_area(poly) / p if p > 0 else 0.0


# ----------------------------------------------------------------------------
# Voronoi cells
# ----------------------------------------------------------------------------
def _place_seeds(ctx, sites, only=False):
    """Seeds by variable-radius Poisson-disk sampling (Bridson): every seed proposes candidates in the
    annulus [r, 2r] around itself, which fills the face in O(n) instead of throwing millions of darts.
    User sites are inserted first and are never moved or removed.
    Returns (SeedSet, hit_cap, n_sites_used, n_sites_ignored)."""
    P, dom, rnd = ctx.P, ctx.dom, ctx.rnd
    sset = SeedSet(P.hmax)
    wall16 = 1.6 * ctx.wall
    used = ignored = 0
    active = []
    for (x, y) in (sites or ()):
        h = ctx.h(x, y)
        if ctx.free_point(x, y, 0.05 * h) and not sset.too_close(x, y, h, 0.0, wall16):
            sset.add(x, y, h)
            active.append(len(sset) - 1)
            used += 1
        else:
            ignored += 1
    if only:
        return sset, False, used, ignored

    hit_cap = False
    K = 22
    for factor, darts in ((0.9, 300), (0.75, 150), (0.62, 150)):
        if len(sset) >= P.max_cells:
            hit_cap = True
            break
        for _ in range(darts):                       # random restarts reach disconnected regions
            x = rnd.uniform(dom.minx, dom.maxx)
            y = rnd.uniform(dom.miny, dom.maxy)
            if sset.too_close(x, y, P.hmin, factor, wall16):
                continue
            h = ctx.h(x, y)
            if sset.too_close(x, y, h, factor, wall16) or not ctx.free_point(x, y, 0.25 * h):
                continue
            sset.add(x, y, h)
            active.append(len(sset) - 1)
            if len(sset) >= P.max_cells:
                break
        if factor < 0.9:                             # gaps are next to existing seeds
            active = list(range(len(sset)))
        while active and len(sset) < P.max_cells:
            k = rnd.randrange(len(active))
            x0, y0, h0 = sset.pts[active[k]]
            found = False
            for _ in range(K):
                ang = rnd.uniform(0.0, 2.0 * math.pi)
                rad = rnd.uniform(1.0, 1.45) * factor * h0
                x, y = x0 + rad * math.cos(ang), y0 + rad * math.sin(ang)
                if x < dom.minx or x > dom.maxx or y < dom.miny or y > dom.maxy:
                    continue
                if sset.too_close(x, y, P.hmin, factor, wall16):
                    continue
                h = ctx.h(x, y)
                if sset.too_close(x, y, h, factor, wall16) or not ctx.free_point(x, y, 0.25 * h):
                    continue
                sset.add(x, y, h)
                active.append(len(sset) - 1)
                found = True
                break
            if not found:
                active[k] = active[-1]
                active.pop()
        if len(sset) >= P.max_cells:
            hit_cap = True
            break
    return sset, hit_cap, used, ignored


def _estimate_cells(ctx):
    """Rough number of cells the face needs (to refuse impossible requests early)."""
    dom, rnd, P = ctx.dom, random.Random(12345), ctx.P
    n, ins, hsum = 1500, 0, 0.0
    for _ in range(n):
        x = rnd.uniform(dom.minx, dom.maxx)
        y = rnd.uniform(dom.miny, dom.maxy)
        if ctx.free_point(x, y, 0.0):
            ins += 1
            hsum += ctx.h(x, y)
    if ins == 0:
        return 0, 0.0
    area = (dom.maxx - dom.minx) * (dom.maxy - dom.miny) * ins / float(n)
    hm = hsum / ins
    return area / (0.8 * hm * hm), area


def _build_cells(sset, ctx, big_box=False):
    """Voronoi cell (constant wall, trimmed against outline and zones) for every seed."""
    wall = ctx.wall
    dom = ctx.dom
    diag = math.hypot(dom.maxx - dom.minx, dom.maxy - dom.miny) + 2.0 * ctx.rim + 1.0
    cells = []
    pts = sset.pts
    for i, (ax, ay, h) in enumerate(pts):
        R = diag if big_box else 1.6 * h
        poly = [(ax - R, ay - R), (ax + R, ay - R), (ax + R, ay + R), (ax - R, ay + R)]
        rc = R * 1.4143
        scan = 2.9 * R if big_box else min(2.5 * h, 2.9 * R)
        ok = True
        while True:
            neigh = []
            for j in sset.near(ax, ay, scan):
                if j == i:
                    continue
                qx, qy, _ = pts[j]
                d = math.hypot(qx - ax, qy - ay)
                if d > 1e-9:
                    neigh.append((d, qx, qy))
            neigh.sort()
            for d, qx, qy in neigh:
                if 0.5 * (d - wall) >= rc:
                    break
                nx, ny = (qx - ax) / d, (qy - ay) / d
                poly = clip(poly, nx, ny, nx * ax + ny * ay + (d - wall) * 0.5)
                if len(poly) < 3:
                    ok = False
                    break
                rc = max(math.hypot(x - ax, y - ay) for x, y in poly)
            if not ok:
                break
            need = 2.0 * rc + wall
            if need <= scan or scan >= 2.9 * R:
                break
            scan = min(need, 2.9 * R)         # a neighbour farther than `scan` could still cut: look further
        if not ok:
            continue
        if _needs_trim(poly, ax, ay, ctx):
            poly = trim_poly(poly, ax, ay, ctx)
            if poly is None:
                continue
        # still touching the artificial box -> the cell is unbounded (a gap, not a real cell)
        if any(abs(x - ax) >= R - 1e-9 or abs(y - ay) >= R - 1e-9 for x, y in poly):
            continue
        poly = dedupe(poly, max(0.02, 0.4 * wall))
        if len(poly) < 3:
            continue
        poly = drop_collinear(poly)
        if len(poly) < 3 or _min_width(poly) < max(wall, 0.12 * h):
            continue
        cells.append({'poly': poly, 'x': ax, 'y': ay, 'h': h, 'i': i})
    return cells


def _sample_grid(dom, step):
    nx = max(1, int((dom.maxx - dom.minx) / step))
    ny = max(1, int((dom.maxy - dom.miny) / step))
    sx, sy = (dom.maxx - dom.minx) / nx, (dom.maxy - dom.miny) / ny
    return [(dom.minx + (i + 0.5) * sx, dom.miny + (j + 0.5) * sy) for i in range(nx) for j in range(ny)], sx * sy


def _coverage(cells, ctx, step, gap_fn, cell_hint):
    """Sample the free region of the face and measure how far each point is from the nearest cell.
    Returns (gap_points, stats)."""
    dom = ctx.dom
    polys = [c['poly'] for c in cells]
    index = PolyIndex(polys, cell_hint)
    pts, area_each = _sample_grid(dom, step)
    free = 0
    gaps = []
    dmax = 0.0
    cap = 1.0 * cell_hint
    for (x, y) in pts:
        if not ctx.free_point(x, y, 0.0):
            continue
        free += 1
        d = index.dist(x, y, cap)
        if d > dmax:
            dmax = d
        if d > gap_fn(x, y):
            gaps.append((x, y, d))
    return gaps, {'free_samples': free, 'free_area': free * area_each, 'gap_max': dmax,
                  'gap_points': len(gaps)}


def _fit_circle(poly, sx, sy, rmin):
    """Largest circle inside a convex cell (centre searched on a 2-level grid)."""
    edges = []
    m = len(poly)
    for k in range(m):
        x1, y1 = poly[k]
        x2, y2 = poly[(k + 1) % m]
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy)
        if L < 1e-9:
            continue
        edges.append((dy / L, -dx / L, x1, y1))
    if not edges:
        return None

    def dmin(x, y):
        return min(nx * (a - x) + ny * (b - y) for nx, ny, a, b in edges)

    xs = [v[0] for v in poly]
    ys = [v[1] for v in poly]
    cx, cy = sx, sy
    bd = dmin(cx, cy)
    x0, x1_, y0, y1_ = min(xs), max(xs), min(ys), max(ys)
    for level in range(3):
        if level == 0:
            gx = [x0 + (x1_ - x0) * k / 8.0 for k in range(9)]
            gy = [y0 + (y1_ - y0) * k / 8.0 for k in range(9)]
        else:
            f = 0.25 if level == 1 else 0.06
            gx = [cx + (x1_ - x0) * f * (k - 2) / 2.0 for k in range(5)]
            gy = [cy + (y1_ - y0) * f * (k - 2) / 2.0 for k in range(5)]
        for x in gx:
            for y in gy:
                d = dmin(x, y)
                if d > bd:
                    bd, cx, cy = d, x, y
    return (cx, cy, bd) if bd >= rmin else None


def _weighted_centroid(poly, ctx):
    """Centroid of a convex polygon weighted by the target density 1/h^2 (fan of triangles)."""
    n = len(poly)
    cx = sum(v[0] for v in poly) / n
    cy = sum(v[1] for v in poly) / n
    sw = sx = sy = 0.0
    for k in range(n):
        a, b = poly[k], poly[(k + 1) % n]
        area = 0.5 * abs((a[0] - cx) * (b[1] - cy) - (b[0] - cx) * (a[1] - cy))
        gx, gy = (cx + a[0] + b[0]) / 3.0, (cy + a[1] + b[1]) / 3.0
        h = ctx.h(gx, gy)
        w = area / (h * h)
        sw += w
        sx += w * gx
        sy += w * gy
    return (sx / sw, sy / sw) if sw > 0 else (cx, cy)


def _relax(sset, cells, ctx, fixed):
    """One Lloyd iteration: every free seed moves to the density-weighted centroid of its cell.
    The centroid of a trimmed cell is inside it, hence inside the face and >= rim from the outline."""
    new = SeedSet(ctx.P.hmax)
    target = {}
    for c in cells:
        if c['i'] >= fixed:
            target[c['i']] = _weighted_centroid(c['poly'], ctx)
    moved = 0.0
    for i, (x, y, h) in enumerate(sset.pts):
        if i in target:
            nx, ny = target[i]
            moved = max(moved, math.hypot(nx - x, ny - y))
            new.add(nx, ny, ctx.h(nx, ny))
        else:
            new.add(x, y, h)
    return new, moved


def _uniformity(cells):
    """Coefficient of variation of (equivalent cell diameter / target size): lower = more even."""
    r = []
    for c in cells:
        a = poly_area(c['poly'])
        if c['h'] > 0 and a > 0:
            r.append(2.0 * math.sqrt(a / math.pi) / c['h'])
    if len(r) < 3:
        return 0.0
    m = sum(r) / len(r)
    return math.sqrt(sum((v - m) ** 2 for v in r) / len(r)) / m if m > 0 else 0.0


def _voronoi_cells(ctx):
    P = ctx.P
    only = bool(P.sites_only)
    if only:
        if not P.sites:
            raise EngineError('no_sites')
        area = (ctx.dom.maxx - ctx.dom.minx) * (ctx.dom.maxy - ctx.dom.miny)
    else:
        est, area = _estimate_cells(ctx)
        if est > P.max_cells * 1.15:
            raise EngineError('too_many_cells', needed=int(est), limit=P.max_cells)
    sset, hit_cap, n_sites, n_ignored = _place_seeds(ctx, P.sites, only)
    if only and n_sites == 0:
        raise EngineError('no_sites')
    if len(sset) < (1 if only else 3):
        raise EngineError('few_seeds')
    cells = _build_cells(sset, ctx, only)

    iters = 0
    for _ in range(max(0, int(P.relax))):
        sset, moved = _relax(sset, cells, ctx, n_sites)
        cells = _build_cells(sset, ctx, only)
        iters += 1
        if moved < 0.01 * P.hmin:
            break

    step = max(0.35 * P.hmin, math.sqrt(max(area, 1e-6) / 12000.0))
    gap_fn = lambda x, y: 0.5 * ctx.wall + 0.2 * ctx.h(x, y)
    cell_hint = max(P.hmax, 1e-3)
    added_total = 0
    if only:
        gaps, cov = _coverage(cells, ctx, step, gap_fn, cell_hint)
    else:
        gaps, cov = _coverage(cells, ctx, step, gap_fn, cell_hint)
        for _ in range(3):
            if not gaps or len(sset) >= P.max_cells:
                break
            gaps.sort(key=lambda g: -g[2])
            budget = max(8, int(0.4 * len(sset)))
            added = 0
            for (x, y, d) in gaps:
                if len(sset) >= P.max_cells:
                    hit_cap = True
                    break
                if added >= budget:
                    break
                h = ctx.h(x, y)
                if sset.too_close(x, y, h, 0.5, 1.6 * ctx.wall):
                    continue
                if not ctx.free_point(x, y, 0.02):
                    continue
                sset.add(x, y, h)
                added += 1
            if not added:
                break
            added_total += added
            cells = _build_cells(sset, ctx, only)
            gaps, cov = _coverage(cells, ctx, step, gap_fn, cell_hint)
        if added_total and iters:                 # re-regularise after the gap-filling seeds were added
            keep_state = (sset, cells, gaps, cov)
            sset2, _ = _relax(sset, cells, ctx, n_sites)
            cells2 = _build_cells(sset2, ctx, only)
            gaps2, cov2 = _coverage(cells2, ctx, step, gap_fn, cell_hint)
            if cov2['gap_points'] <= cov['gap_points'] and _uniformity(cells2) <= _uniformity(cells):
                sset, cells, gaps, cov = sset2, cells2, gaps2, cov2   # only keep it if it does not hurt
                iters += 1
    cov['seeds'] = len(sset)
    cov['refine_added'] = added_total
    cov['hit_cap'] = hit_cap
    cov['relax_iterations'] = iters
    cov['sites_used'] = n_sites
    cov['sites_ignored'] = n_ignored
    cov['uniformity_cv'] = _uniformity(cells)
    return cells, cov


# ----------------------------------------------------------------------------
# Regular tilings (honeycomb / triangular mesh)
# ----------------------------------------------------------------------------
def _tile_polys(ctx):
    """All tiles of the rotated grid that may touch the face: (vertices, apothem, circumradius)."""
    P, dom = ctx.P, ctx.dom
    L = P.tile
    cr_, sr_ = math.cos(P.angle), math.sin(P.angle)
    ox, oy = 0.5 * (dom.minx + dom.maxx), 0.5 * (dom.miny + dom.maxy)
    gxs, gys = [], []
    for (x, y) in ((dom.minx, dom.miny), (dom.maxx, dom.miny), (dom.maxx, dom.maxy), (dom.minx, dom.maxy)):
        dx, dy = x - ox, y - oy
        gxs.append(dx * cr_ + dy * sr_)
        gys.append(-dx * sr_ + dy * cr_)
    gx0, gx1, gy0, gy1 = min(gxs), max(gxs), min(gys), max(gys)
    tiles = []
    if P.shape == 'hex':
        R_t = L
        apo = L * SQRT3 / 2.0
        dxs, dys = 2 * apo, 1.5 * R_t
        for j in range(int(math.floor(gy0 / dys)) - 2, int(math.ceil(gy1 / dys)) + 3):
            cy_g = j * dys
            off = apo if (j % 2) else 0.0
            for i in range(int(math.floor((gx0 - off) / dxs)) - 2, int(math.ceil((gx1 - off) / dxs)) + 3):
                cx_g = i * dxs + off
                tiles.append(([(cx_g + R_t * math.cos(math.radians(30 + 60 * k)),
                                cy_g + R_t * math.sin(math.radians(30 + 60 * k))) for k in range(6)], apo, R_t))
    else:
        ht = L * SQRT3 / 2.0
        apo = L / (2 * SQRT3)
        R_t = L / SQRT3

        def lp(i, j):
            return ((i + 0.5 * j) * L, j * ht)

        for j in range(int(math.floor(gy0 / ht)) - 2, int(math.ceil(gy1 / ht)) + 3):
            for i in range(int(math.floor(gx0 / L - 0.5 * j)) - 2, int(math.ceil(gx1 / L - 0.5 * j)) + 3):
                tiles.append(([lp(i, j), lp(i + 1, j), lp(i, j + 1)], apo, R_t))
                tiles.append(([lp(i + 1, j), lp(i + 1, j + 1), lp(i, j + 1)], apo, R_t))
    out = []
    for verts, apo_, R_ in tiles:
        vs = [(ox + gx * cr_ - gy * sr_, oy + gx * sr_ + gy * cr_) for gx, gy in verts]
        out.append((vs, apo_, R_))
    return out


def _pick_anchor(poly, ctx, R_t):
    """A free point inside the convex polygon with the largest clearance (None if there is none)."""
    cx = sum(v[0] for v in poly) / len(poly)
    cy = sum(v[1] for v in poly) / len(poly)
    cands = [(cx, cy)]
    n = len(poly)
    for k in range(n):
        v, w = poly[k], poly[(k + 1) % n]
        for f in (0.15, 0.5):
            cands.append((v[0] + (cx - v[0]) * f, v[1] + (cy - v[1]) * f))
        mx, my = 0.5 * (v[0] + w[0]), 0.5 * (v[1] + w[1])
        cands.append((mx + (cx - mx) * 0.15, my + (cy - my) * 0.15))
    xs = [v[0] for v in poly]
    ys = [v[1] for v in poly]
    for i in range(1, 5):
        for j in range(1, 5):
            cands.append((min(xs) + (max(xs) - min(xs)) * i / 5.0, min(ys) + (max(ys) - min(ys)) * j / 5.0))
    best, best_c = None, 1e-4
    cap = ctx.rim + 2 * R_t
    for (x, y) in cands:
        if not convex_contains(poly, x, y):
            continue
        if not ctx.dom.inside(x, y):
            continue
        cb = ctx.dom.dist(x, y, cap) - ctx.rim
        cz = ctx.discs.clearance(x, y, cap) if len(ctx.discs) else cap
        c = min(cb, cz)
        if c > best_c:
            best, best_c = (x, y), c
    return best


def _tiling_cells(ctx):
    P, dom = ctx.P, ctx.dom
    apo_nom = P.tile * SQRT3 / 2.0 if P.shape == 'hex' else P.tile / (2 * SQRT3)
    est_tiles = (dom.maxx - dom.minx + 4 * P.tile) * (dom.maxy - dom.miny + 4 * P.tile) / max(
        (2.598 if P.shape == 'hex' else 0.433) * P.tile * P.tile, 1e-9)
    if est_tiles > 25 * P.max_cells + 5000:
        raise EngineError('too_many_tiles', needed=int(est_tiles))
    cells = []
    for vs, apo, R_t in _tile_polys(ctx):
        tcx = sum(v[0] for v in vs) / len(vs)
        tcy = sum(v[1] for v in vs) / len(vs)
        if (tcx < dom.minx - R_t - ctx.rim or tcx > dom.maxx + R_t + ctx.rim or
                tcy < dom.miny - R_t - ctx.rim or tcy > dom.maxy + R_t + ctx.rim):
            continue
        w_loc = ctx.wall_at(tcx, tcy)
        f = (apo - 0.5 * w_loc) / apo
        if f <= 0.2:
            continue
        poly = [(tcx + (x - tcx) * f, tcy + (y - tcy) * f) for x, y in vs]
        a_full = poly_area(poly)
        interior = (dom.inside(tcx, tcy) and
                    dom.dist(tcx, tcy, ctx.rim + R_t + 1e-6) >= ctx.rim + R_t + 1e-6 - 1e-12 and
                    (not len(ctx.discs) or ctx.discs.clearance(tcx, tcy, R_t + 1e-6) >= R_t + 1e-6 - 1e-12))
        if not interior:
            anchor = _pick_anchor(poly, ctx, R_t)
            if anchor is None:
                continue
            poly = trim_poly(poly, anchor[0], anchor[1], ctx)
            if poly is None:
                continue
            poly = dedupe(poly, max(0.02, 0.4 * w_loc))
            if len(poly) < 3:
                continue
            poly = drop_collinear(poly)
            if len(poly) < 3:
                continue
            if _min_width(poly) < max(w_loc, 0.5 * apo_nom) or poly_area(poly) < 0.04 * a_full:
                continue
        cells.append({'poly': poly, 'x': tcx, 'y': tcy, 'h': 2 * apo, 'w': w_loc})
    if not cells:
        raise EngineError('no_tiles')
    if len(cells) > P.max_cells:
        raise EngineError('tiles_over_limit', count=len(cells), limit=P.max_cells)
    area = (dom.maxx - dom.minx) * (dom.maxy - dom.miny)
    step = max(0.3 * P.tile, math.sqrt(max(area, 1e-6) / 12000.0))
    gap_fn = lambda x, y: 0.5 * P.wall_max + 0.15 * P.tile
    _, cov = _coverage(cells, ctx, step, gap_fn, 2 * P.tile)
    cov['seeds'] = len(cells)
    cov['refine_added'] = 0
    cov['hit_cap'] = False
    cov['relax_iterations'] = 0
    cov['sites_used'] = 0
    cov['sites_ignored'] = 0
    cov['uniformity_cv'] = 0.0
    return cells, cov


# ----------------------------------------------------------------------------
# Verification and statistics
# ----------------------------------------------------------------------------
def _verify_item(item, dom, ctx):
    """Re-check one item against the outline and keep-out zones. True if valid."""
    rim = ctx.rim - 1e-6
    if item[0] == 'C':
        _, x, y, r = item
        if r <= 0 or not dom.inside(x, y):
            return False
        cap = rim + r + 1e-6
        if dom.dist(x, y, cap) < rim + r - 1e-9:
            return False
        return all(math.hypot(x - cx, y - cy) >= rr + r - 1e-6 for cx, cy, rr in ctx.discs.near(x, y, r + 1e-6))
    poly = item[1]
    if len(poly) < 3 or poly_area(poly) <= 1e-8:
        return False
    pts = list(poly)
    n = len(poly)
    for k in range(n):
        pts.append((0.5 * (poly[k][0] + poly[(k + 1) % n][0]), 0.5 * (poly[k][1] + poly[(k + 1) % n][1])))
    for (x, y) in pts:
        if not dom.inside(x, y) or dom.dist(x, y, rim + 1e-6) < rim - 1e-9:
            return False
        if len(ctx.discs):
            for cx, cy, rr in ctx.discs.near(x, y, 1e-6):
                if math.hypot(x - cx, y - cy) < rr - 1e-6:
                    return False
    return True


def measure_min_gap(items):
    """Smallest distance between any two items (polygons / circles)."""
    if len(items) < 2:
        return None
    sizes = []
    boxes = []
    for it in items:
        if it[0] == 'C':
            boxes.append((it[1] - it[3], it[1] + it[3], it[2] - it[3], it[2] + it[3]))
        else:
            xs = [v[0] for v in it[1]]
            ys = [v[1] for v in it[1]]
            boxes.append((min(xs), max(xs), min(ys), max(ys)))
        sizes.append(max(boxes[-1][1] - boxes[-1][0], boxes[-1][3] - boxes[-1][2]))
    cs = max(sizes) * 1.05 or 1.0
    grid = {}
    for i, (x0, x1, y0, y1) in enumerate(boxes):
        for ix in range(int(math.floor(x0 / cs)), int(math.floor(x1 / cs)) + 1):
            for iy in range(int(math.floor(y0 / cs)), int(math.floor(y1 / cs)) + 1):
                grid.setdefault((ix, iy), []).append(i)
    best = 1e18
    done = set()
    for key, lst in grid.items():
        cand = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cand.extend(grid.get((key[0] + dx, key[1] + dy), ()))
        for i in lst:
            for j in cand:
                if j <= i or (i, j) in done:
                    continue
                done.add((i, j))
                a, b = items[i], items[j]
                ba, bb = boxes[i], boxes[j]
                gx = max(ba[0] - bb[1], bb[0] - ba[1], 0.0)
                gy = max(ba[2] - bb[3], bb[2] - ba[3], 0.0)
                if gx * gx + gy * gy >= best * best:
                    continue                      # boxes already farther apart than the best gap found
                if a[0] == 'C' and b[0] == 'C':
                    d = math.hypot(a[1] - b[1], a[2] - b[2]) - a[3] - b[3]
                elif a[0] == 'C':
                    d = poly_point_dist(b[1], a[1], a[2]) - a[3]
                elif b[0] == 'C':
                    d = poly_point_dist(a[1], b[1], b[2]) - b[3]
                else:
                    d = poly_poly_dist(a[1], b[1])
                if d < best:
                    best = d
    return None if best >= 1e17 else best


def generate(segs, reinf_pts, frame, P):
    """Generate the pattern.

    segs      : list of (ax, ay, bx, by) outline segments (all loops) in the sketch plane.
    reinf_pts : list of (x, y, z) reinforcement sample points in model space.
    frame     : {'o': (x,y,z), 'ex': (x,y,z), 'ey': (x,y,z)} sketch plane (model units).
    Returns (items, stats). items: ('P', polygon, corner_radius) or ('C', x, y, r).
    """
    t0 = time.time()
    if P.shape not in SHAPES:
        raise EngineError('bad_shape')
    if P.sites_only and P.tiling:
        P.sites_only = False
    P.relax = max(0, min(20, int(P.relax or 0)))
    if P.wall <= 0:
        raise EngineError('bad_wall')
    if P.infl <= 0 or P.keep < 0 or P.rim < 0 or P.max_cells < 1:
        raise EngineError('bad_params')
    if P.tiling:
        if P.tile <= 0:
            raise EngineError('bad_params')
        if P.wall_max < P.wall:
            P.wall_max = P.wall
        apo = P.tile * SQRT3 / 2.0 if P.shape == 'hex' else P.tile / (2 * SQRT3)
        if P.wall_max > 1.2 * apo:
            raise EngineError('wall_too_thick_tile', maximum=1.2 * apo)
    else:
        if P.hmin >= P.hmax:
            raise EngineError('hmin_ge_hmax')
        if P.wall > 0.6 * P.hmin:
            raise EngineError('wall_too_thick_cell', maximum=0.6 * P.hmin)

    cell_sz = max(P.hmax, P.tile if P.tiling else 0.0)
    dom = Domain(segs, cell=0.5 * (P.rim + cell_sz) + 0.2)
    reach = P.keep + P.infl + 1e-3
    ctx = Ctx(P, dom, Reinforcement(reinf_pts, frame, reach))

    if P.tiling:
        cells, cov = _tiling_cells(ctx)
    else:
        cells, cov = _voronoi_cells(ctx)

    # ---- convert cells to drawable items ----
    items = []
    for c in cells:
        if P.shape in ('voronoi', 'rounded', 'hex', 'tri'):
            r = P.corner_r if P.shape in ('rounded', 'hex', 'tri') else 0.0
            items.append(('P', c['poly'], r))
        else:
            circ = _fit_circle(c['poly'], c['x'], c['y'], max(ctx.wall, 0.3 * P.hmin))
            if circ is not None:
                items.append(('C', circ[0], circ[1], circ[2]))

    # ---- independent verification (safety net) ----
    valid = [it for it in items if _verify_item(it, dom, ctx)]
    dropped = len(items) - len(valid)
    items = valid
    if not items:
        raise EngineError('no_cells')

    # ---- analysis ----
    open_area = 0.0
    diam = []
    n_reinf_zone = 0
    zone_limit = P.keep + 0.5 * P.infl
    for it in items:
        if it[0] == 'C':
            a = math.pi * it[3] ** 2
            cx, cy = it[1], it[2]
        else:
            a = rounded_area(it[1], it[2]) if it[2] > 0 else poly_area(it[1])
            cx = sum(v[0] for v in it[1]) / len(it[1])
            cy = sum(v[1] for v in it[1]) / len(it[1])
        open_area += a
        diam.append(2.0 * math.sqrt(a / math.pi))
        if ctx.reinf.present and ctx.reinf.dist(cx, cy) < zone_limit:
            n_reinf_zone += 1
    min_gap = measure_min_gap(items)
    stats = {
        'shape': P.shape,
        'items': len(items),
        'dropped': dropped,
        'open_area': open_area,
        'free_area': cov['free_area'],
        'open_ratio_free': open_area / cov['free_area'] if cov['free_area'] > 0 else 0.0,
        'gap_max': cov['gap_max'],
        'gap_points': cov['gap_points'],
        'free_samples': cov['free_samples'],
        'uncovered_pct': 100.0 * cov['gap_points'] / cov['free_samples'] if cov['free_samples'] else 0.0,
        'min_gap': min_gap,
        'size_min': min(diam), 'size_max': max(diam), 'size_mean': sum(diam) / len(diam),
        'reinforced_items': n_reinf_zone,
        'light_items': len(items) - n_reinf_zone,
        'seeds': cov['seeds'],
        'refine_added': cov['refine_added'],
        'relax_iterations': cov['relax_iterations'],
        'sites_used': cov['sites_used'],
        'sites_ignored': cov['sites_ignored'],
        'uniformity_cv': cov['uniformity_cv'],
        'seconds': time.time() - t0,
        'hit_cap': cov['hit_cap'],
        'outline_length': dom.total_length,
        'outline_segments': len(dom.segs),
        'zones': len(ctx.discs),
        'reinf_points': len(ctx.reinf.pts),
        'bbox': (dom.minx, dom.miny, dom.maxx, dom.maxy),
    }
    return items, stats
