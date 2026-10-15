# -*- coding: utf-8 -*-
"""
VV Generator v1.5 - Add-in para Fusion 360
Cria um padrão Voronoi adaptativo numa face plana:
  - células pequenas (mais paredes) perto de furos / faces de reforço
  - células grandes (mais leve) longe delas
  - parede de espessura constante, borda sólida e zona de proteção ao redor dos furos
Observação: a "análise" é geométrica (proximidade de furos/apoios), não é MEF.
Valide o resultado com um estudo de Simulação.
"""
import adsk.core, adsk.fusion, traceback, math, random, os

CMD_ID = 'vvGeneratorCmd'
CMD_NAME = 'VV Generator'
CMD_DESC = 'Corta um padrão Voronoi adaptativo numa face plana, reforçando as regiões próximas a furos e faces selecionadas.'
PANEL_ID = 'SolidCreatePanel'
RES = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources')
FOOTER = 'Created and maintained by Flashbio #31888'
SHAPES = {
    'Voronoi (pontas vivas)': 'voronoi',
    'Voronoi (pontas arredondadas)': 'rounded',
    'Hexágonos (favo de mel)': 'hex',
    'Triângulos (malha triangular)': 'tri',
    'Círculos': 'circle',
}

_app = None
_ui = None
_handlers = []


# ----------------------------------------------------------------------------
# Geometria 2D
# ----------------------------------------------------------------------------
def clip(poly, a, b, c):
    """Mantém a parte do polígono convexo com a*x + b*y <= c (Sutherland-Hodgman)."""
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
    for k in range(len(poly)):
        x1, y1 = poly[k]
        x2, y2 = poly[(k + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return abs(s) * 0.5


def dedupe(poly, tol):
    out = []
    for p in poly:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > tol:
            out.append(p)
    while len(out) > 1 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) <= tol:
        out.pop()
    return out


# ----------------------------------------------------------------------------
# Coleta de dados da peça
# ----------------------------------------------------------------------------
def face_segments(face, sk):
    """Segmentos 2D (espaço do sketch) de todos os contornos da face."""
    segs = []
    for loop in face.loops:
        for coedge in loop.coEdges:
            ev = coedge.edge.evaluator
            ok, p0, p1 = ev.getParameterExtents()
            if not ok:
                continue
            ok, pts = ev.getStrokes(p0, p1, 0.005)
            if not ok or len(pts) < 2:
                continue
            q = [sk.modelToSketchSpace(p) for p in pts]
            for i in range(len(q) - 1):
                segs.append((q[i].x, q[i].y, q[i + 1].x, q[i + 1].y))
    return segs


def is_hole(f):
    """True se a face cilíndrica for um furo (normal aponta para o eixo)."""
    try:
        cyl = f.geometry
        ok, n = f.evaluator.getNormalAtPoint(f.pointOnFace)
        if not ok:
            return False
        pt = f.pointOnFace
        o, ax = cyl.origin, cyl.axis
        v = (pt.x - o.x, pt.y - o.y, pt.z - o.z)
        t = v[0] * ax.x + v[1] * ax.y + v[2] * ax.z
        rad = (v[0] - t * ax.x, v[1] - t * ax.y, v[2] - t * ax.z)
        return (rad[0] * n.x + rad[1] * n.y + rad[2] * n.z) < 0
    except:
        return False


def sample_face(f, maxpts=250):
    """Pontos 3D amostrados na face (via malha)."""
    calc = f.meshManager.createMeshCalculator()
    calc.surfaceTolerance = 0.02
    try:
        calc.maxSideLength = 0.5
    except:
        pass
    mesh = calc.calculate()
    c = mesh.nodeCoordinatesAsDouble
    pts = [(c[i], c[i + 1], c[i + 2]) for i in range(0, len(c), 3)]
    stride = max(1, len(pts) // maxpts)
    return pts[::stride]



# ----------------------------------------------------------------------------
# Formatos: encaixe de polígonos/círculo na célula, cantos arredondados, desenho
# ----------------------------------------------------------------------------
def fit_shape(poly, sx, sy, n, wall, rmin):
    """Maior polígono regular de n lados (n=0: círculo) contido na célula.
    O centro é escolhido dentro da célula (semente, centróide ou centro de maior folga).
    Retorna ('C', x, y, r) ou ('P', vértices, 0) ou None se ficar menor que rmin."""
    edges = []
    m = len(poly)
    for k in range(m):
        x1, y1 = poly[k]
        x2, y2 = poly[(k + 1) % m]
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy)
        if L < 1e-9:
            continue
        edges.append((dy / L, -dx / L, x1, y1))     # normal para fora (polígono anti-horário)
    if not edges:
        return None

    def dmin(x, y):
        return min(nx * (x1 - x) + ny * (y1 - y) for nx, ny, x1, y1 in edges)

    if n == 0:
        xs = [v[0] for v in poly]
        ys = [v[1] for v in poly]
        cx, cy = sx, sy
        bd = dmin(cx, cy)
        x0, x1_, y0, y1_ = min(xs), max(xs), min(ys), max(ys)
        for level in range(2):
            if level == 0:
                gx = [x0 + (x1_ - x0) * k / 8.0 for k in range(9)]
                gy = [y0 + (y1_ - y0) * k / 8.0 for k in range(9)]
            else:
                stx, sty = (x1_ - x0) / 8.0, (y1_ - y0) / 8.0
                gx = [cx + stx * (k - 2) / 2.0 for k in range(5)]
                gy = [cy + sty * (k - 2) / 2.0 for k in range(5)]
            for x in gx:
                for y in gy:
                    d = dmin(x, y)
                    if d > bd:
                        bd, cx, cy = d, x, y
        return ('C', cx, cy, bd) if bd >= rmin else None

    centers = [(sx, sy), (sum(v[0] for v in poly) / m, sum(v[1] for v in poly) / m)]
    period = 2 * math.pi / n
    best = None
    for (cx, cy) in centers:
        if dmin(cx, cy) <= 0:
            continue
        for k in range(24):
            th = k * period / 24.0
            us = [(math.cos(th + j * period), math.sin(th + j * period)) for j in range(n)]
            R = 1e18
            for nx, ny, x1, y1 in edges:
                d = nx * (x1 - cx) + ny * (y1 - cy)
                mx = max(u[0] * nx + u[1] * ny for u in us)
                R = min(R, d / mx)
            if best is None or R > best[0]:
                best = (R, th, cx, cy)
    if best is None:
        return None
    R, th, cx, cy = best
    if R * math.cos(math.pi / n) < rmin:
        return None
    verts = [(cx + R * math.cos(th + j * period), cy + R * math.sin(th + j * period)) for j in range(n)]
    return ('P', verts, 0)


def path_prims(poly, r):
    """Contorno do polígono como lista de primitivas ('L',p0,p1) e ('A',p0,pmeio,p1),
    com cantos arredondados de raio r (por canto, limitado pelo tamanho das arestas)."""
    n = len(poly)
    A = [None] * n
    B = [None] * n
    M = [None] * n
    for i in range(n):
        v, p, q = poly[i], poly[i - 1], poly[(i + 1) % n]
        ax, ay, bx, by = p[0] - v[0], p[1] - v[1], q[0] - v[0], q[1] - v[1]
        la, lb = math.hypot(ax, ay), math.hypot(bx, by)
        ax, ay, bx, by = ax / la, ay / la, bx / lb, by / lb
        th = math.acos(max(-1.0, min(1.0, ax * bx + ay * by)))
        ri = 0.0
        if r > 0 and 0.05 < th < math.pi - 0.05:
            ri = min(r, 0.5 * min(la, lb) * math.tan(th / 2))
        if ri < 0.01:
            A[i] = B[i] = v
        else:
            t = ri / math.tan(th / 2)
            A[i] = (v[0] + ax * t, v[1] + ay * t)
            B[i] = (v[0] + bx * t, v[1] + by * t)
            sx_, sy_ = ax + bx, ay + by
            sl = math.hypot(sx_, sy_)
            dist = ri / math.sin(th / 2) - ri
            M[i] = (v[0] + sx_ / sl * dist, v[1] + sy_ / sl * dist)
    prims = []
    for i in range(n):
        if M[i] is not None:
            prims.append(('A', A[i], M[i], B[i]))
        nxt = A[(i + 1) % n]
        if math.hypot(nxt[0] - B[i][0], nxt[1] - B[i][1]) > 0.005:
            prims.append(('L', B[i], nxt))
    return prims


def draw_prims(sk, prims):
    """Desenha um contorno fechado (linhas e arcos encadeados) no sketch."""
    Pt = adsk.core.Point3D.create
    lines = sk.sketchCurves.sketchLines
    arcs = sk.sketchCurves.sketchArcs
    first = None
    prev = None
    for idx, pr in enumerate(prims):
        last = (idx == len(prims) - 1)
        start = Pt(pr[1][0], pr[1][1], 0) if prev is None else prev.endSketchPoint
        if pr[0] == 'L':
            end = first.startSketchPoint if (last and first is not None) else Pt(pr[2][0], pr[2][1], 0)
            obj = lines.addByTwoPoints(start, end)
        else:
            obj = arcs.addByThreePoints(start, Pt(pr[2][0], pr[2][1], 0), Pt(pr[3][0], pr[3][1], 0))
        if first is None:
            first = obj
        prev = obj

# ----------------------------------------------------------------------------
# Algoritmo principal
# ----------------------------------------------------------------------------
def build(face, extra_faces, auto_holes, wall, hmin, hmax, infl, rim, keep,
          max_cells, rnd_seed, through, depth, shape='voronoi', corner_r=0.0,
          tile=0.9, wall_max=0.25, angle=0.0):
    body = face.body
    comp = body.parentComponent
    sk = comp.sketches.add(face)
    sk.name = 'Voronoi'

    # base do sketch -> modelo (cálculo em Python puro, sem chamadas de API por ponto)
    P = adsk.core.Point3D.create
    o = sk.sketchToModelSpace(P(0, 0, 0))
    px = sk.sketchToModelSpace(P(1, 0, 0))
    py = sk.sketchToModelSpace(P(0, 1, 0))
    ex = (px.x - o.x, px.y - o.y, px.z - o.z)
    ey = (py.x - o.x, py.y - o.y, py.z - o.z)

    segs = face_segments(face, sk)
    if not segs:
        raise RuntimeError('Não foi possível ler o contorno da face.')
    xs = [s[0] for s in segs] + [s[2] for s in segs]
    ys = [s[1] for s in segs] + [s[3] for s in segs]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)

    def inside(x, y):
        cnt = 0
        for ax_, ay_, bx_, by_ in segs:
            if (ay_ > y) != (by_ > y):
                xi = ax_ + (y - ay_) * (bx_ - ax_) / (by_ - ay_)
                if xi > x:
                    cnt += 1
        return cnt % 2 == 1

    def dist_boundary(x, y):
        best = 1e18
        for ax_, ay_, bx_, by_ in segs:
            dx, dy = bx_ - ax_, by_ - ay_
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - ax_) * dx + (y - ay_) * dy) / L2))
            d = (x - ax_ - t * dx) ** 2 + (y - ay_ - t * dy) ** 2
            if d < best:
                best = d
        return math.sqrt(best)

    # regiões de reforço
    rfaces = list(extra_faces)
    if auto_holes:
        for f in body.faces:
            if f.geometry.surfaceType == adsk.core.SurfaceTypes.CylinderSurfaceType and is_hole(f):
                rfaces.append(f)
    rpts = []
    for f in rfaces:
        rpts.extend(sample_face(f))

    def dist_reinf(x, y):
        X = o.x + x * ex[0] + y * ey[0]
        Y = o.y + x * ex[1] + y * ey[1]
        Z = o.z + x * ex[2] + y * ey[2]
        best = 1e18
        for a, b, c in rpts:
            d = (a - X) ** 2 + (b - Y) ** 2 + (c - Z) ** 2
            if d < best:
                best = d
        return math.sqrt(best)

    def h_local(x, y):
        if not rpts:
            return 0.5 * (hmin + hmax)
        d = dist_reinf(x, y)
        s = min(1.0, max(0.0, (d - keep) / infl))
        s = s * s * (3 - 2 * s)
        return hmin + (hmax - hmin) * s

    # ---- dados de contorno: normal (para dentro da face) de cada segmento ----
    seginfo = []
    for ax_, ay_, bx_, by_ in segs:
        dx, dy = bx_ - ax_, by_ - ay_
        L = math.hypot(dx, dy)
        if L < 1e-9:
            continue
        nx, ny = -dy / L, dx / L
        mx, my = (ax_ + bx_) * 0.5, (ay_ + by_) * 0.5
        e = 0.002
        if not inside(mx + nx * e, my + ny * e):
            if inside(mx - nx * e, my - ny * e):
                nx, ny = -nx, -ny
            else:
                continue
        seginfo.append((ax_, ay_, dx, dy, nx, ny, L))

    # ---- zonas de proteção (discos no plano) ao redor das regiões de reforço ----
    nrm = (ex[1] * ey[2] - ex[2] * ey[1], ex[2] * ey[0] - ex[0] * ey[2], ex[0] * ey[1] - ex[1] * ey[0])
    nl = math.sqrt(nrm[0] ** 2 + nrm[1] ** 2 + nrm[2] ** 2) or 1.0
    nrm = (nrm[0] / nl, nrm[1] / nl, nrm[2] / nl)
    disc_map = {}
    cellk = max(0.3 * keep, 0.05)
    for (a, b, c) in rpts:
        vx, vy, vz = a - o.x, b - o.y, c - o.z
        dp = abs(vx * nrm[0] + vy * nrm[1] + vz * nrm[2])
        if dp >= keep:
            continue
        r = math.sqrt(keep * keep - dp * dp)
        x2 = vx * ex[0] + vy * ex[1] + vz * ex[2]
        y2 = vx * ey[0] + vy * ey[1] + vz * ey[2]
        key = (int(round(x2 / cellk)), int(round(y2 / cellk)))
        if key not in disc_map or disc_map[key][2] < r:
            disc_map[key] = (x2, y2, r)
    discs = list(disc_map.values())

    tiling = shape in ('hex', 'tri')
    hit_cap = False
    cells = []

    if tiling:
        # ---- malha regular (favo de mel / triangular) preenchendo toda a face ----
        L = tile
        cr_, sr_ = math.cos(angle), math.sin(angle)
        ox_, oy_ = 0.5 * (minx + maxx), 0.5 * (miny + maxy)
        gxs, gys = [], []
        for (x, y) in ((minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)):
            dx, dy = x - ox_, y - oy_
            gxs.append(dx * cr_ + dy * sr_)
            gys.append(-dx * sr_ + dy * cr_)
        gx0, gx1, gy0, gy1 = min(gxs), max(gxs), min(gys), max(gys)

        tiles = []        # (vértices no referencial da malha, apótema)
        if shape == 'hex':
            R_t = L
            apo = L * math.sqrt(3) / 2.0
            dxs, dys = 2 * apo, 1.5 * R_t
            for j in range(int(math.floor(gy0 / dys)) - 2, int(math.ceil(gy1 / dys)) + 3):
                cy_g = j * dys
                off = apo if (j % 2) else 0.0
                for i in range(int(math.floor((gx0 - off) / dxs)) - 2, int(math.ceil((gx1 - off) / dxs)) + 3):
                    cx_g = i * dxs + off
                    tiles.append(([(cx_g + R_t * math.cos(math.radians(30 + 60 * k)),
                                    cy_g + R_t * math.sin(math.radians(30 + 60 * k))) for k in range(6)], apo))
        else:
            ht = L * math.sqrt(3) / 2.0
            apo = L / (2 * math.sqrt(3))
            R_t = L / math.sqrt(3)

            def lp(i, j):
                return ((i + 0.5 * j) * L, j * ht)

            for j in range(int(math.floor(gy0 / ht)) - 2, int(math.ceil(gy1 / ht)) + 3):
                for i in range(int(math.floor(gx0 / L - 0.5 * j)) - 2, int(math.ceil(gx1 / L - 0.5 * j)) + 3):
                    tiles.append(([lp(i, j), lp(i + 1, j), lp(i, j + 1)], apo))
                    tiles.append(([lp(i + 1, j), lp(i + 1, j + 1), lp(i, j + 1)], apo))

        if len(tiles) > 6 * max_cells + 2000:
            raise RuntimeError('Ladrilhos demais (%d). Aumente o tamanho do ladrilho.' % len(tiles))

        for verts_g, apo in tiles:
            vs = [(ox_ + gx * cr_ - gy * sr_, oy_ + gx * sr_ + gy * cr_) for gx, gy in verts_g]
            tcx = sum(v[0] for v in vs) / len(vs)
            tcy = sum(v[1] for v in vs) / len(vs)
            if tcx < minx - R_t or tcx > maxx + R_t or tcy < miny - R_t or tcy > maxy + R_t:
                continue

            # parede local: grossa perto do reforço, fina longe dele
            if rpts:
                dr = dist_reinf(tcx, tcy)
                sm = min(1.0, max(0.0, (dr - keep) / infl))
                sm = sm * sm * (3 - 2 * sm)
                w_loc = wall_max + (wall - wall_max) * sm
            else:
                w_loc = wall
            f = (apo - 0.5 * w_loc) / apo
            if f <= 0.2:
                continue
            poly = [(tcx + (x - tcx) * f, tcy + (y - tcy) * f) for x, y in vs]
            a_full = poly_area(poly)

            # corte reto na borda (a 'rim' do contorno), valendo também para centros fora da face
            rr = R_t + rim + 0.2
            for (ax_, ay_, dx, dy, nx, ny, Ls) in seginfo:
                t = ((tcx - ax_) * dx + (tcy - ay_) * dy) / (Ls * Ls)
                t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
                qx, qy = ax_ + t * dx, ay_ + t * dy
                vx, vy = tcx - qx, tcy - qy
                dd = math.hypot(vx, vy)
                if dd > rr:
                    continue
                dot = vx * nx + vy * ny
                if abs(dot) < 0.35 * dd:
                    continue
                poly = clip(poly, -nx, -ny, -(nx * ax_ + ny * ay_) - rim)
                if len(poly) < 3:
                    break
            if len(poly) < 3:
                continue

            # zonas de proteção ao redor de furos / reforços
            for (cx, cy, r) in discs:
                vx, vy = tcx - cx, tcy - cy
                dd = math.hypot(vx, vy)
                if dd < 1e-9 or dd > r + R_t:
                    continue
                ux, uy = vx / dd, vy / dd
                poly = clip(poly, -ux, -uy, -(ux * cx + uy * cy) - r)
                if len(poly) < 3:
                    break
            if len(poly) < 3:
                continue

            poly = dedupe(poly, max(0.02, 0.4 * w_loc))
            if len(poly) < 3 or poly_area(poly) < max((1.5 * w_loc) ** 2, 0.12 * a_full):
                continue
            good = True
            for v in poly:
                if not inside(v[0], v[1]) or dist_boundary(v[0], v[1]) < rim * 0.95:
                    good = False
                    break
                if rpts and dist_reinf(v[0], v[1]) < keep * 0.95:
                    good = False
                    break
            if good:
                cells.append((poly, tcx, tcy))

        if not cells:
            raise RuntimeError('Nenhum ladrilho válido. Ajuste o tamanho, a parede ou a borda sólida.')
        if len(cells) > max_cells:
            raise RuntimeError('%d ladrilhos passam do limite de %d. Aumente o tamanho do ladrilho ou o limite de células.'
                               % (len(cells), max_cells))
    else:
        # ---- sementes (dart throwing com raio variável + grade espacial, 2 passadas) ----
        rnd = random.Random(rnd_seed)
        gs = hmax
        grid = {}
        seeds = []
        hit_cap = False
        for factor, fail_limit in ((0.9, 1500), (0.75, 5000), (0.62, 8000)):
            fails = 0
            while fails < fail_limit:
                if len(seeds) >= max_cells:
                    hit_cap = True
                    break
                x = rnd.uniform(minx, maxx)
                y = rnd.uniform(miny, maxy)
                h = h_local(x, y)
                gx, gy = int(math.floor(x / gs)), int(math.floor(y / gs))
                ok = True
                for ix in (gx - 1, gx, gx + 1):
                    for iy in (gy - 1, gy, gy + 1):
                        for (sx, sy, sh) in grid.get((ix, iy), ()):
                            r = factor * 0.5 * (h + sh)
                            if (x - sx) ** 2 + (y - sy) ** 2 < r * r:
                                ok = False
                                break
                        if not ok:
                            break
                    if not ok:
                        break
                if ok:
                    if not inside(x, y) or dist_boundary(x, y) < rim + 0.3 * h:
                        ok = False
                    elif rpts and dist_reinf(x, y) < keep + 0.3 * hmin:
                        ok = False
                if ok:
                    seeds.append((x, y, h))
                    grid.setdefault((gx, gy), []).append((x, y, h))
                    fails = 0
                else:
                    fails += 1
            if hit_cap:
                break

        if len(seeds) < 3:
            raise RuntimeError('Poucas sementes geradas. Reduza a borda sólida ou o tamanho das células.')

        # ---- células de Voronoi: bissetrizes (parede constante) + cortes retos na borda ----
        cells = []
        for i, (px_, py_, h) in enumerate(seeds):
            R = 2.0 * h
            poly = [(px_ - R, py_ - R), (px_ + R, py_ - R), (px_ + R, py_ + R), (px_ - R, py_ + R)]

            # vizinhos
            neigh = []
            for j, (qx, qy, qh) in enumerate(seeds):
                if j == i:
                    continue
                d = math.hypot(qx - px_, qy - py_)
                if 1e-9 < d < 2 * R:
                    neigh.append((d, qx, qy))
            neigh.sort()
            for d, qx, qy in neigh:
                nx, ny = (qx - px_) / d, (qy - py_) / d
                poly = clip(poly, nx, ny, nx * px_ + ny * py_ + (d - wall) * 0.5)
                if len(poly) < 3:
                    break
            if len(poly) < 3:
                continue

            # borda: a célula é cortada reta, paralela ao contorno, a 'rim' de distância
            rr = 1.5 * h
            for (ax_, ay_, dx, dy, nx, ny, L) in seginfo:
                t = ((px_ - ax_) * dx + (py_ - ay_) * dy) / (L * L)
                t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
                qx, qy = ax_ + t * dx, ay_ + t * dy
                vx, vy = px_ - qx, py_ - qy
                dd = math.hypot(vx, vy)
                if dd > rr:
                    continue
                dot = vx * nx + vy * ny
                if dot <= 0 or dot < 0.35 * dd:
                    continue
                poly = clip(poly, -nx, -ny, -(nx * ax_ + ny * ay_) - rim)
                if len(poly) < 3:
                    break
            if len(poly) < 3:
                continue

            # zonas de proteção ao redor de furos / faces de reforço
            for (cx, cy, r) in discs:
                vx, vy = px_ - cx, py_ - cy
                dd = math.hypot(vx, vy)
                if dd <= r or dd > r + 1.5 * h:
                    continue
                ux, uy = vx / dd, vy / dd
                poly = clip(poly, -ux, -uy, -(ux * cx + uy * cy) - r)
                if len(poly) < 3:
                    break
            if len(poly) < 3:
                continue

            # célula "truncada" pela caixa inicial = região sem sementes por perto
            if max(math.hypot(v[0] - px_, v[1] - py_) for v in poly) > 1.6 * h:
                continue
            poly = dedupe(poly, max(0.02, 0.4 * wall))
            if len(poly) < 3 or poly_area(poly) < (1.5 * wall) ** 2:
                continue

            # verificação final de segurança
            good = True
            for v in poly:
                if not inside(v[0], v[1]) or dist_boundary(v[0], v[1]) < rim * 0.95:
                    good = False
                    break
                if rpts and dist_reinf(v[0], v[1]) < keep * 0.95:
                    good = False
                    break
            if good:
                cells.append((poly, px_, py_))

        if not cells:
            raise RuntimeError('Nenhuma célula válida. Ajuste espessura da parede, borda ou tamanho das células.')

    # ---- converte cada célula no formato escolhido ----
    n_sides = {'circle': 0}
    prims_list = []
    for poly, sx, sy in cells:
        if shape in ('voronoi', 'rounded', 'hex', 'tri'):
            rr_ = corner_r if shape in ('rounded', 'hex', 'tri') else 0.0
            prims_list.append(('P', poly, rr_))
        else:
            sh = fit_shape(poly, sx, sy, n_sides[shape], wall, max(wall, 0.3 * hmin))
            if sh is None:
                continue
            if sh[0] == 'P':
                sh = ('P', sh[1], corner_r)
            prims_list.append(sh)
    if not prims_list:
        raise RuntimeError('Nenhuma forma coube nas células. Reduza a espessura da parede ou aumente o tamanho das células.')
    cells = prims_list

    # ---- desenha no sketch ----
    sk.isComputeDeferred = True
    circles = sk.sketchCurves.sketchCircles
    for item in cells:
        if item[0] == 'C':
            circles.addByCenterRadius(P(item[1], item[2], 0), item[3])
        else:
            draw_prims(sk, path_prims(item[1], item[2]))
    sk.isComputeDeferred = False

    # ---- corte: testa direções, confere volume e, se preciso, corta em lotes ----
    sk.isLightBulbOn = False
    plist = [p for p in sk.profiles]
    if not plist:
        sk.isLightBulbOn = True
        raise RuntimeError('O esboço foi criado, mas o Fusion não gerou nenhum perfil fechado (%d células desenhadas).' % len(cells))

    ext = comp.features.extrudeFeatures
    D = adsk.fusion.ExtentDirections
    first, second = D.NegativeExtentDirection, D.PositiveExtentDirection
    try:
        okn, fn = face.evaluator.getNormalAtPoint(face.pointOnFace)
        if okn and (fn.x * nrm[0] + fn.y * nrm[1] + fn.z * nrm[2]) < 0:
            first, second = second, first
    except:
        pass
    state = {'order': [first, second], 'err': ''}

    def make_cut(profile_list, direction):
        col = adsk.core.ObjectCollection.create()
        for p in profile_list:
            col.add(p)
        inp = ext.createInput(col, adsk.fusion.FeatureOperations.CutFeatureOperation)
        if through:
            inp.setAllExtent(direction)
        else:
            dd = adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(depth))
            inp.setOneSideExtent(dd, direction)
        inp.participantBodies = [body]
        return ext.add(inp)

    def cut_profiles(profile_list):
        vol0 = body.volume
        for direction in list(state['order']):
            try:
                f = make_cut(profile_list, direction)
            except:
                state['err'] = traceback.format_exc()
                continue
            try:
                vol1 = body.volume
            except:
                vol1 = None
            if vol1 is None or vol1 < vol0 - 1e-9:
                state['order'] = [direction] + [d for d in state['order'] if d != direction]
                return True
            try:
                f.deleteMe()
            except:
                pass
        return False

    cut_count = 0
    if cut_profiles(plist):
        cut_count = len(plist)
    else:
        for k in range(0, len(plist), 20):
            chunk = plist[k:k + 20]
            if cut_profiles(chunk):
                cut_count += len(chunk)

    if cut_count == 0:
        sk.isLightBulbOn = True
        raise RuntimeError('O esboço foi criado (%d células, %d perfis), mas o corte falhou.\n\nÚltimo erro do Fusion:\n%s'
                           % (len(cells), len(plist), state['err'] or '(nenhum erro; o corte não removeu volume)'))

    msg = '%d células no esboço, %d perfis, %d cortados (%d furos/faces de reforço consideradas).' % (
        len(cells), len(plist), cut_count, len(rfaces))
    if cut_count < len(plist):
        msg += '\nAtenção: %d perfis não puderam ser cortados.' % (len(plist) - cut_count)
    if hit_cap:
        msg += '\nLimite de células atingido: parte da face pode ter ficado sem padrão. Aumente o limite ou o tamanho das células.'
    return msg


# ----------------------------------------------------------------------------
# Interface do comando
# ----------------------------------------------------------------------------
class ExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            i = args.command.commandInputs
            face = i.itemById('face').selection(0).entity
            sel = i.itemById('reinf')
            extra = [sel.selection(k).entity for k in range(sel.selectionCount)]
            through = i.itemById('mode').selectedItem.name == 'Atravessar tudo'
            shape = SHAPES.get(i.itemById('shape').selectedItem.name, 'voronoi')
            corner_r = max(0.0, i.itemById('corner').value)

            wall = i.itemById('wall').value
            hmin = i.itemById('hmin').value
            hmax = i.itemById('hmax').value
            tile = i.itemById('tile').value
            wall_max = max(wall, i.itemById('wmax').value)
            angle = i.itemById('angle').value
            if shape in ('hex', 'tri'):
                apo = tile * math.sqrt(3) / 2.0 if shape == 'hex' else tile / (2 * math.sqrt(3))
                if wall_max > 1.2 * apo:
                    _ui.messageBox('A parede máxima está grossa demais para esse tamanho de ladrilho '
                                   '(máximo ~%.1f mm). Reduza a parede ou aumente o ladrilho.' % (12 * apo), CMD_NAME)
                    return
            else:
                if hmin >= hmax:
                    _ui.messageBox('A célula mínima deve ser menor que a máxima.', CMD_NAME)
                    return
                if wall > 0.6 * hmin:
                    _ui.messageBox('A parede está muito grossa para a célula mínima (use no máximo ~60% dela).', CMD_NAME)
                    return

            msg = build(face, extra, i.itemById('auto').value, wall, hmin, hmax,
                        i.itemById('infl').value, i.itemById('rim').value,
                        i.itemById('keep').value, i.itemById('maxc').value,
                        i.itemById('seed').value, through, i.itemById('depth').value,
                        shape, corner_r, tile, wall_max, angle)
            _ui.messageBox(msg, CMD_NAME)
        except:
            _ui.messageBox('Falha:\n{}'.format(traceback.format_exc()), CMD_NAME)


class InputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            i = args.inputs
            if args.input.id == 'mode':
                i.itemById('depth').isVisible = (i.itemById('mode').selectedItem.name != 'Atravessar tudo')
            elif args.input.id == 'shape':
                key = SHAPES.get(i.itemById('shape').selectedItem.name, 'voronoi')
                i.itemById('corner').isVisible = key in ('rounded', 'hex', 'tri')
                til = key in ('hex', 'tri')
                for id_ in ('tile', 'wmax', 'angle'):
                    i.itemById(id_).isVisible = til
                for id_ in ('hmin', 'hmax'):
                    i.itemById(id_).isVisible = not til
        except:
            pass


class CreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            i = cmd.commandInputs
            VI = adsk.core.ValueInput.createByString

            logo_path = os.path.join(RES, 'logo.png')
            if os.path.isfile(logo_path):
                logo = i.addImageCommandInput('logo', '', logo_path)
                try:
                    logo.isFullWidth = True
                except:
                    pass

            f = i.addSelectionInput('face', 'Face plana', 'Face onde o padrão será desenhado e cortado')
            f.addSelectionFilter('PlanarFaces')
            f.setSelectionLimits(1, 1)

            r = i.addSelectionInput('reinf', 'Faces de reforço (opcional)',
                                    'Faces de apoio/carga onde as células devem ficar menores')
            r.addSelectionFilter('Faces')
            r.setSelectionLimits(0, 0)

            i.addBoolValueInput('auto', 'Detectar furos automaticamente', True, '', True)

            sd = i.addDropDownCommandInput('shape', 'Formato',
                                           adsk.core.DropDownStyles.TextListDropDownStyle)
            for k_, name_ in enumerate(SHAPES):
                sd.listItems.add(name_, k_ == 0)
            cr = i.addValueInput('corner', 'Raio dos cantos (0 = vivos)', 'mm', VI('1.5 mm'))
            cr.isVisible = False

            i.addValueInput('wall', 'Espessura da parede', 'mm', VI('1.2 mm'))
            t1 = i.addValueInput('tile', 'Lado do ladrilho', 'mm', VI('9 mm'))
            t2 = i.addValueInput('wmax', 'Parede perto do reforço', 'mm', VI('2.5 mm'))
            t3 = i.addValueInput('angle', 'Rotação da malha', 'deg', VI('0 deg'))
            for t_ in (t1, t2, t3):
                t_.isVisible = False
            i.addValueInput('hmin', 'Célula mínima (perto do reforço)', 'mm', VI('6 mm'))
            i.addValueInput('hmax', 'Célula máxima (longe do reforço)', 'mm', VI('16 mm'))
            i.addValueInput('infl', 'Distância de transição', 'mm', VI('30 mm'))
            i.addValueInput('keep', 'Zona sólida ao redor dos furos', 'mm', VI('4 mm'))
            i.addValueInput('rim', 'Borda sólida', 'mm', VI('4 mm'))
            i.addIntegerSpinnerCommandInput('maxc', 'Limite de células', 10, 1500, 10, 400)
            i.addIntegerSpinnerCommandInput('seed', 'Semente aleatória', 1, 9999, 1, 1)

            dd = i.addDropDownCommandInput('mode', 'Profundidade',
                                           adsk.core.DropDownStyles.TextListDropDownStyle)
            dd.listItems.add('Atravessar tudo', True)
            dd.listItems.add('Distância', False)
            dep = i.addValueInput('depth', 'Distância do corte', 'mm', VI('3 mm'))
            dep.isVisible = False

            foot = i.addTextBoxCommandInput('footer', '', '<div align="center"><i>' + FOOTER + '</i></div>', 1, True)
            foot.isFullWidth = True

            ex = ExecuteHandler()
            cmd.execute.add(ex)
            _handlers.append(ex)
            ch = InputChangedHandler()
            cmd.inputChanged.add(ch)
            _handlers.append(ch)
        except:
            _ui.messageBox('Falha:\n{}'.format(traceback.format_exc()), CMD_NAME)


def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface
        cmdDef = _ui.commandDefinitions.itemById(CMD_ID)
        if not cmdDef:
            cmdDef = _ui.commandDefinitions.addButtonDefinition(
                CMD_ID, CMD_NAME, CMD_DESC, RES if os.path.isdir(RES) else '')
        h = CreatedHandler()
        cmdDef.commandCreated.add(h)
        _handlers.append(h)
        panel = _ui.allToolbarPanels.itemById(PANEL_ID)
        if not panel.controls.itemById(CMD_ID):
            ctrl = panel.controls.addCommand(cmdDef)
            ctrl.isPromoted = True
    except:
        if _ui:
            _ui.messageBox('Falha ao iniciar:\n{}'.format(traceback.format_exc()), CMD_NAME)


def stop(context):
    try:
        panel = _ui.allToolbarPanels.itemById(PANEL_ID)
        ctrl = panel.controls.itemById(CMD_ID)
        if ctrl:
            ctrl.deleteMe()
        cmdDef = _ui.commandDefinitions.itemById(CMD_ID)
        if cmdDef:
            cmdDef.deleteMe()
    except:
        if _ui:
            _ui.messageBox('Falha ao parar:\n{}'.format(traceback.format_exc()))
