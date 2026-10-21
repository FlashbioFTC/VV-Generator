# -*- coding: utf-8 -*-
"""
Tests for vv_engine (run:  python3 -m unittest discover -s tests -v   from the repository root).

The checks use brute-force implementations that do NOT share code with the engine's spatial indexes,
so they act as an independent oracle for: containment, rim distance, keep-out zones, minimum wall
between items, path closure and determinism.  A random "fuzz" test throws irregular / imprecise
outlines at every shape.
"""
import math
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'VVGenerator'))
import vv_engine as E  # noqa: E402

FRAME = {'o': (0.0, 0.0, 0.0), 'ex': (1.0, 0.0, 0.0), 'ey': (0.0, 1.0, 0.0)}
KNOWN_ERRORS = {'too_many_cells', 'too_many_tiles', 'tiles_over_limit', 'no_cells', 'no_tiles', 'few_seeds',
                'wall_too_thick_tile', 'wall_too_thick_cell', 'hmin_ge_hmax'}


# --------------------------------------------------------------------------- outlines
def loop_segs(pts):
    return [(pts[i][0], pts[i][1], pts[(i + 1) % len(pts)][0], pts[(i + 1) % len(pts)][1]) for i in range(len(pts))]


def circle_pts(cx, cy, r, n=96, noise=0.0, rnd=None):
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n
        rr = r * (1 + (rnd.uniform(-noise, noise) if rnd else 0.0))
        out.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return out


def rect_outline(w=20, h=12):
    return [[(0, 0), (w, 0), (w, h), (0, h)]]


def trapezoid_with_hole():
    return [[(0, 0), (22, 3), (22, 13), (0, 16)], circle_pts(16, 8, 1.5)]


def l_shape():
    return [[(0, 0), (20, 0), (20, 8), (8, 8), (8, 20), (0, 20)]]


def star(n=5, R=14, r=6):
    pts = []
    for k in range(2 * n):
        a = math.pi * k / n
        rr = R if k % 2 == 0 else r
        pts.append((rr * math.cos(a), rr * math.sin(a)))
    return [pts]


def dumbbell():
    left = circle_pts(0, 0, 7, 72)
    right = circle_pts(26, 0, 7, 72)
    # blobs joined by a narrow neck (1.8 cm wide)
    pts = []
    for (x, y) in left:
        if x > 0 and abs(y) < 0.9 + 0 and x > 6.5:
            continue
        pts.append((x, y))
    # simple explicit outline instead of boolean ops
    return [[(-7, -3), (-3, -7), (3, -7), (7, -3), (7, -0.9), (19, -0.9), (19, -3), (23, -7), (29, -7), (33, -3),
             (33, 3), (29, 7), (23, 7), (19, 3), (19, 0.9), (7, 0.9), (7, 3), (3, 7), (-3, 7), (-7, 3)]]


def annulus():
    return [circle_pts(0, 0, 14, 120), circle_pts(0, 0, 6, 80)]


def noisy_with_holes(seed):
    rnd = random.Random(seed)
    outer = circle_pts(0, 0, 13, 140, noise=0.18, rnd=rnd)
    holes = [circle_pts(-4, 3, 1.4, 40), circle_pts(5, -2, 2.1, 40), circle_pts(2, 6, 0.9, 30)]
    return [outer] + holes


def imprecise():
    """Duplicated points, collinear points and micro-segments."""
    base = [(0, 0), (10, 0), (20, 0), (20, 0.00001), (20, 10), (10, 10), (10.000001, 10), (0, 10), (0, 5)]
    hole = circle_pts(10, 5, 2, 50)
    hole = hole[:10] + [hole[10], hole[10]] + hole[11:]
    return [base, hole]


def segs_of(loops):
    out = []
    for lp in loops:
        out.extend(loop_segs(lp))
    return out


# --------------------------------------------------------------------------- brute-force oracle
def b_inside(segs, x, y):
    c = 0
    for ax, ay, bx, by in segs:
        if (ay > y) != (by > y) and ax + (y - ay) * (bx - ax) / (by - ay) > x:
            c += 1
    return c & 1 == 1


def b_dist(segs, x, y):
    best = 1e18
    for ax, ay, bx, by in segs:
        qx, qy = E.seg_nearest(x, y, ax, ay, bx, by)
        best = min(best, math.hypot(x - qx, y - qy))
    return best


def reinf_ring(cx, cy, r, n=48, z=0.0):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n), z) for k in range(n)]


def check_items(tc, segs, items, P, reinf, label):
    tol = 1e-6
    rim = max(P.rim, 0.01)
    polys = []
    for it in items:
        if it[0] == 'C':
            _, x, y, r = it
            tc.assertTrue(r > 0 and math.isfinite(r), label + ': bad circle')
            tc.assertTrue(b_inside(segs, x, y), label + ': circle centre outside face')
            tc.assertGreaterEqual(b_dist(segs, x, y), rim + r - tol, label + ': circle violates rim')
            for p in reinf:   # in-plane distance to the disc (sphere of radius keep cut by the plane)
                dp = abs(p[2])
                if dp < P.keep:
                    tc.assertGreaterEqual(math.hypot(p[0] - x, p[1] - y), math.sqrt(P.keep ** 2 - dp ** 2) + r - 1e-5,
                                          label + ': circle inside keep-out')
        else:
            poly = it[1]
            tc.assertGreaterEqual(len(poly), 3, label)
            tc.assertGreater(E.poly_area(poly), 1e-8, label + ': degenerate polygon')
            for (x, y) in poly:
                tc.assertTrue(math.isfinite(x) and math.isfinite(y), label + ': NaN')
                tc.assertTrue(b_inside(segs, x, y), label + ': vertex outside face')
                tc.assertGreaterEqual(b_dist(segs, x, y), rim - tol, label + ': vertex violates rim')
                for p in reinf:
                    tc.assertGreaterEqual(math.sqrt((p[0] - x) ** 2 + (p[1] - y) ** 2 + p[2] ** 2), P.keep - 1e-5,
                                          label + ': vertex inside keep-out')
            n = len(poly)
            for k in range(n):   # convexity (same orientation for all turns)
                a, b, c = poly[k], poly[(k + 1) % n], poly[(k + 2) % n]
                cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
                tc.assertGreater(cr, -1e-9, label + ': non-convex / clockwise polygon')
            # path closure
            prims = E.path_prims(poly, it[2])
            tc.assertGreaterEqual(len(prims), 3, label)
            for k, pr in enumerate(prims):
                end = pr[2] if pr[0] == 'L' else pr[3]
                nxt = prims[(k + 1) % len(prims)]
                tc.assertLess(math.hypot(end[0] - nxt[1][0], end[1] - nxt[1][1]), 0.0061, label + ': open path')
            polys.append(poly)
    # minimum wall between every pair of polygons (bounding-box prefilter)
    gap_limit = P.wall - 1e-6
    boxes = [(min(v[0] for v in p), max(v[0] for v in p), min(v[1] for v in p), max(v[1] for v in p)) for p in polys]
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            a, b = boxes[i], boxes[j]
            if a[1] + gap_limit < b[0] or b[1] + gap_limit < a[0] or a[3] + gap_limit < b[2] or b[3] + gap_limit < a[2]:
                continue
            tc.assertGreaterEqual(E.poly_poly_dist(polys[i], polys[j]), gap_limit, label + ': wall too thin')


def run(loops, shape, reinf=(), **kw):
    P = E.Params(shape=shape, **kw)
    segs = segs_of(loops)
    items, stats = E.generate(segs, list(reinf), FRAME, P)
    return P, segs, items, stats


class EngineTests(unittest.TestCase):
    SHAPES = ('voronoi', 'rounded', 'hex', 'tri', 'circle')

    def _all_shapes(self, loops, reinf=(), label='', **kw):
        res = {}
        for sh in self.SHAPES:
            extra = dict(kw)
            if sh in ('rounded', 'hex', 'tri'):
                extra.setdefault('corner_r', 0.12)
            if sh == 'tri':
                extra.setdefault('tile', 1.8)
            if sh == 'hex':
                extra.setdefault('tile', 1.0)
            P, segs, items, stats = run(loops, sh, reinf, **extra)
            check_items(self, segs, items, P, reinf, '%s/%s' % (label, sh))
            self.assertLessEqual(len(items), P.max_cells)
            self.assertEqual(stats['dropped'], 0, '%s/%s: safety net dropped items' % (label, sh))
            res[sh] = stats
        return res

    # ------------------------------------------------------------------ regular outlines
    def test_rectangle(self):
        st = self._all_shapes(rect_outline(), label='rect')
        self.assertLess(st['voronoi']['uncovered_pct'], 1.5)

    def test_trapezoid_hole_with_reinforcement(self):
        reinf = reinf_ring(16, 8, 1.5)
        st = self._all_shapes(trapezoid_with_hole(), reinf, label='trap')
        self.assertLess(st['voronoi']['uncovered_pct'], 2.0)

    # ------------------------------------------------------------------ irregular outlines
    def test_l_shape_concave(self):
        st = self._all_shapes(l_shape(), label='L', max_cells=800)
        self.assertLess(st['voronoi']['uncovered_pct'], 3.0)

    def test_star_concave(self):
        self._all_shapes(star(), label='star', max_cells=800)

    def test_dumbbell_narrow_neck(self):
        self._all_shapes(dumbbell(), label='dumbbell', max_cells=1200)

    def test_annulus_big_hole(self):
        self._all_shapes(annulus(), reinf_ring(0, 0, 6, 80), label='annulus', max_cells=1200)

    def test_noisy_outline_many_holes(self):
        for s in (1, 2, 3):
            self._all_shapes(noisy_with_holes(s), reinf_ring(-4, 3, 1.4) + reinf_ring(5, -2, 2.1),
                             label='noisy%d' % s, max_cells=900)

    def test_imprecise_geometry(self):
        self._all_shapes(imprecise(), label='imprecise')

    def test_offplane_reinforcement(self):
        """Reinforcement points above the sketch plane (e.g. a boss) create partial keep-out discs."""
        reinf = reinf_ring(10, 6, 2.0, z=0.3) + reinf_ring(10, 6, 1.0, z=1.0)
        self._all_shapes(rect_outline(), reinf, label='offplane')

    # ------------------------------------------------------------------ behaviour
    def test_deterministic_and_seed_changes_layout(self):
        a = run(rect_outline(), 'voronoi', seed=5)[2]
        b = run(rect_outline(), 'voronoi', seed=5)[2]
        c = run(rect_outline(), 'voronoi', seed=6)[2]
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_density_follows_reinforcement(self):
        reinf = reinf_ring(10, 6, 1.0)
        P, segs, items, stats = run(rect_outline(), 'voronoi', reinf, hmin=0.5, hmax=1.8, infl=4.0, keep=0.4)

        def dist(it):
            cx = sum(v[0] for v in it[1]) / len(it[1])
            cy = sum(v[1] for v in it[1]) / len(it[1])
            return math.hypot(cx - 10, cy - 6)
        near = [E.poly_area(i[1]) for i in items if dist(i) < 3.5]
        far = [E.poly_area(i[1]) for i in items if dist(i) > 7.5]
        self.assertTrue(near and far)
        self.assertLess(sum(near) / len(near), sum(far) / len(far))

    def test_tiling_wall_grows_near_reinforcement(self):
        reinf = reinf_ring(10, 6, 1.0)
        P, segs, items, stats = run(rect_outline(), 'hex', reinf, tile=0.9, wall=0.12, wall_max=0.3)
        walls = []
        # nominal hexagon area = 2.598 * L^2 ; shrinking by wall w removes ~ perimeter*w/2 -> smaller near reinforcement
        near = [E.poly_area(i[1]) for i in items if len(i[1]) == 6 and 2.3 < math.hypot(
            sum(v[0] for v in i[1]) / 6 - 10, sum(v[1] for v in i[1]) / 6 - 6) < 3.6]
        far = [E.poly_area(i[1]) for i in items if len(i[1]) == 6 and math.hypot(
            sum(v[0] for v in i[1]) / 6 - 10, sum(v[1] for v in i[1]) / 6 - 6) > 8]
        self.assertTrue(near and far)
        self.assertLess(max(near), max(far))

    def test_errors_are_explicit(self):
        for kw, code in (({'hmin': 1.0, 'hmax': 0.5}, 'hmin_ge_hmax'), ({'wall': 0.5, 'hmin': 0.6}, 'wall_too_thick_cell')):
            with self.assertRaises(E.EngineError) as cm:
                run(rect_outline(), 'voronoi', **kw)
            self.assertEqual(cm.exception.code, code)
        with self.assertRaises(E.EngineError) as cm:
            run(rect_outline(), 'hex', tile=0.9, wall=0.12, wall_max=2.0)
        self.assertEqual(cm.exception.code, 'wall_too_thick_tile')
        with self.assertRaises(E.EngineError) as cm:     # impossible request must not silently produce a partial pattern
            run(rect_outline(200, 120), 'voronoi', hmin=0.5, hmax=0.6, max_cells=100)
        self.assertEqual(cm.exception.code, 'too_many_cells')

    def test_independent_coverage_check(self):
        """Brute-force coverage: free points far from every cell must be rare."""
        loops = l_shape()
        P, segs, items, stats = run(loops, 'voronoi', max_cells=800)
        polys = [i[1] for i in items]
        rnd = random.Random(3)
        free = bad = 0
        for _ in range(1500):
            x, y = rnd.uniform(0, 20), rnd.uniform(0, 20)
            if not b_inside(segs, x, y) or b_dist(segs, x, y) < P.rim:
                continue
            free += 1
            d = min(E.poly_point_dist(p, x, y) for p in polys)
            if d > 0.5 * P.wall + 0.2 * 1.1 + 0.25:
                bad += 1
        self.assertGreater(free, 300)
        self.assertLess(bad / float(free), 0.03)

    # ------------------------------------------------------------------ v1.7 features
    def test_lloyd_relaxation_makes_cells_more_uniform(self):
        for loops, reinf in ((l_shape(), ()), (trapezoid_with_hole(), reinf_ring(16, 8, 1.5))):
            cv = {}
            for r in (0, 3):
                P, segs, items, stats = run(loops, 'voronoi', reinf, relax=r, max_cells=800)
                check_items(self, segs, items, P, reinf, 'relax%d' % r)
                cv[r] = stats['uniformity_cv']
                self.assertEqual(stats['relax_iterations'] >= (1 if r else 0), True)
            self.assertLess(cv[3], 0.9 * cv[0], 'relaxation should reduce size variation by >10%%: %s' % cv)

    def test_user_sites_mixed_with_automatic_seeds(self):
        sites = [(5.0, 6.0), (10.0, 6.0), (15.0, 6.0), (100.0, 100.0)]    # last one is outside the face
        P, segs, items, stats = run(rect_outline(), 'voronoi', (), sites=sites)
        check_items(self, segs, items, P, (), 'sites-mixed')
        self.assertEqual(stats['sites_used'], 3)
        self.assertEqual(stats['sites_ignored'], 1)
        polys = [i[1] for i in items]
        for (x, y) in sites[:3]:
            self.assertTrue(any(E.convex_contains(p, x, y) for p in polys), 'site %s must be inside a cell' % ((x, y),))
        self.assertGreater(len(items), 10)

    def test_user_sites_only(self):
        sites = [(5.0, 6.0), (10.0, 6.0), (15.0, 6.0), (10.0, 3.0), (10.0, 9.0)]
        P, segs, items, stats = run(rect_outline(), 'voronoi', (), sites=sites, sites_only=True, wall=0.12)
        check_items(self, segs, items, P, (), 'sites-only')
        self.assertEqual(len(items), 5)
        self.assertEqual(stats['sites_used'], 5)
        with self.assertRaises(E.EngineError) as cm:
            run(rect_outline(), 'voronoi', (), sites=[(100.0, 100.0)], sites_only=True)
        self.assertEqual(cm.exception.code, 'no_sites')
        with self.assertRaises(E.EngineError) as cm:
            run(rect_outline(), 'voronoi', (), sites=None, sites_only=True)
        self.assertEqual(cm.exception.code, 'no_sites')

    def test_circles_with_relaxation_and_sites(self):
        P, segs, items, stats = run(trapezoid_with_hole(), 'circle', reinf_ring(16, 8, 1.5),
                                    relax=2, sites=[(4.0, 8.0)], max_cells=600)
        check_items(self, segs, items, P, reinf_ring(16, 8, 1.5), 'circles-v17')
        self.assertEqual(stats['sites_used'], 1)

    def test_speed_budget(self):
        """Guard against performance regressions (generous limits: the CI machine may be slow)."""
        import time
        t = time.time()
        run(trapezoid_with_hole(), 'voronoi', reinf_ring(16, 8, 1.5))
        self.assertLess(time.time() - t, 8.0)
        t = time.time()
        run(noisy_with_holes(1), 'voronoi', reinf_ring(-4, 3, 1.4) + reinf_ring(5, -2, 2.1), max_cells=900)
        self.assertLess(time.time() - t, 20.0)

    # ------------------------------------------------------------------ fuzz
    def test_fuzz_irregular_outlines(self):
        rnd = random.Random(2024)
        ok_runs = 0
        for case in range(60):
            kind = rnd.choice(('noisy', 'poly', 'rect', 'holes'))
            if kind == 'noisy':
                loops = [circle_pts(0, 0, rnd.uniform(6, 14), rnd.randint(30, 160), noise=rnd.uniform(0.0, 0.3), rnd=rnd)]
            elif kind == 'poly':
                n = rnd.randint(5, 14)
                R = rnd.uniform(6, 14)
                ang = sorted(rnd.uniform(0, 2 * math.pi) for _ in range(n))
                loops = [[(R * rnd.uniform(0.45, 1.0) * math.cos(a), R * rnd.uniform(0.45, 1.0) * math.sin(a)) for a in ang]]
            elif kind == 'rect':
                loops = rect_outline(rnd.uniform(6, 25), rnd.uniform(6, 18))
            else:
                loops = [circle_pts(0, 0, 13, 100, noise=0.1, rnd=rnd)]
                for _ in range(rnd.randint(1, 4)):
                    loops.append(circle_pts(rnd.uniform(-6, 6), rnd.uniform(-6, 6), rnd.uniform(0.5, 1.8), 36))
            # a star-shaped polygon with random radii can self-intersect: skip invalid outlines
            if not self._simple(loops[0]):
                continue
            segs = segs_of(loops)
            reinf = []
            for lp in loops[1:]:
                cx = sum(p[0] for p in lp) / len(lp)
                cy = sum(p[1] for p in lp) / len(lp)
                r = max(math.hypot(p[0] - cx, p[1] - cy) for p in lp)
                reinf += reinf_ring(cx, cy, r, 24, z=rnd.choice([0.0, 0.0, 0.2]))
            shape = rnd.choice(self.SHAPES)
            kw = dict(wall=rnd.uniform(0.08, 0.2), rim=rnd.uniform(0.2, 0.6), keep=rnd.uniform(0.2, 0.6),
                      infl=rnd.uniform(1.5, 4.0), seed=rnd.randint(1, 9999), max_cells=900,
                      corner_r=rnd.choice([0.0, 0.1, 0.25]))
            if shape in ('hex', 'tri'):
                kw['tile'] = rnd.uniform(0.8, 1.6)
                kw['wall_max'] = kw['wall'] * rnd.uniform(1.0, 2.2)
                kw['angle'] = rnd.uniform(0, math.pi)
            else:
                kw['hmin'] = rnd.uniform(max(0.5, kw['wall'] / 0.55), 0.9)
                kw['hmax'] = kw['hmin'] + rnd.uniform(0.3, 1.2)
            try:
                P, s, items, stats = run(loops, shape, reinf, **kw)
            except E.EngineError as e:
                self.assertIn(e.code, KNOWN_ERRORS, 'unexpected engine error code %s' % e.code)
                continue
            check_items(self, s, items, P, reinf, 'fuzz#%d/%s/%s' % (case, kind, shape))
            self.assertEqual(stats['dropped'], 0)
            ok_runs += 1
        self.assertGreater(ok_runs, 25)

    @staticmethod
    def _simple(poly):
        n = len(poly)

        def ccw(a, b, c):
            return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])

        def inter(a, b, c, d):
            return ccw(a, c, d) != ccw(b, c, d) and ccw(a, b, c) != ccw(a, b, d)
        for i in range(n):
            for j in range(i + 2, n):
                if i == 0 and j == n - 1:
                    continue
                if inter(poly[i], poly[(i + 1) % n], poly[j], poly[(j + 1) % n]):
                    return False
        return True


if __name__ == '__main__':
    unittest.main(verbosity=2)
