# -*- coding: utf-8 -*-
"""
VV Generator - Autodesk Fusion 360 add-in.

Creates adaptive lightweight patterns (Voronoi, rounded Voronoi, honeycomb, triangular mesh, circles)
on a planar face and cuts them through the body.  All geometry is computed by vv_engine.py (pure
Python, unit-tested outside Fusion); this file only talks to the Fusion API and the user.

NOTE: the "analysis" is geometric (proximity to holes / reinforcement faces). It is NOT a finite
element analysis - validate structural performance with a simulation study.

Created and maintained by Flashbio #31888.
"""
import importlib
import math
import os
import random
import sys
import traceback

import adsk.core
import adsk.fusion

_HERE = os.path.dirname(os.path.realpath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import vv_engine  # noqa: E402

VERSION = '1.7.1'
CMD_ID = 'vvGeneratorCmd'
CMD_NAME = 'VV Generator'
PANEL_ID = 'SolidCreatePanel'
RES = os.path.join(_HERE, 'resources')
ICON_DIR = os.path.join(RES, '')          # trailing separator, as Autodesk's own add-in template does
FOOTER = 'Created and maintained by Flashbio #31888'
SHAPE_KEYS = ('voronoi', 'rounded', 'hex', 'tri', 'circle')

_app = None
_ui = None
_handlers = []

# ----------------------------------------------------------------------------
# Translations (English / Portugues-BR / Espanol, chosen from Fusion's language)
# ----------------------------------------------------------------------------
_T = {
    'desc': ('Cuts an adaptive lightweight pattern into a planar face, denser around holes and reinforcement faces.',
             'Corta um padrão leve adaptativo em uma face plana, mais denso ao redor de furos e faces de reforço.',
             'Corta un patrón ligero adaptativo en una cara plana, más denso alrededor de agujeros y caras de refuerzo.'),
    'face': ('Planar face', 'Face plana', 'Cara plana'),
    'face_tip': ('Face where the pattern is drawn and cut', 'Face onde o padrão será desenhado e cortado',
                 'Cara donde se dibuja y se corta el patrón'),
    'reinf': ('Reinforcement faces (optional)', 'Faces de reforço (opcional)', 'Caras de refuerzo (opcional)'),
    'reinf_tip': ('Supports, load areas or bosses: the pattern is denser near them',
                  'Apoios, áreas de carga ou ressaltos: o padrão fica mais denso perto deles',
                  'Apoyos, zonas de carga o salientes: el patrón es más denso cerca de ellos'),
    'auto': ('Detect holes automatically', 'Detectar furos automaticamente', 'Detectar agujeros automáticamente'),
    'shape': ('Shape', 'Formato', 'Formato'),
    'shape_0': ('Voronoi (sharp corners)', 'Voronoi (pontas vivas)', 'Voronoi (esquinas vivas)'),
    'shape_1': ('Voronoi (rounded corners)', 'Voronoi (pontas arredondadas)', 'Voronoi (esquinas redondeadas)'),
    'shape_2': ('Hexagons (honeycomb)', 'Hexágonos (favo de mel)', 'Hexágonos (panal)'),
    'shape_3': ('Triangles (triangular mesh)', 'Triângulos (malha triangular)', 'Triángulos (malla triangular)'),
    'shape_4': ('Circles', 'Círculos', 'Círculos'),
    'corner': ('Corner radius (0 = sharp)', 'Raio dos cantos (0 = vivos)', 'Radio de esquinas (0 = vivas)'),
    'wall': ('Wall thickness', 'Espessura da parede', 'Espesor de pared'),
    'wall_tip': ('Exact wall for Voronoi, minimum gap for circles, thinnest wall for tilings.',
                 'Parede exata no Voronoi, folga mínima nos círculos, parede mais fina nas malhas.',
                 'Pared exacta en Voronoi, holgura mínima en círculos, pared más fina en las mallas.'),
    'tile': ('Tile side', 'Lado do ladrilho', 'Lado de la baldosa'),
    'wmax': ('Wall near reinforcement', 'Parede perto do reforço', 'Pared cerca del refuerzo'),
    'angle': ('Mesh rotation', 'Rotação da malha', 'Rotación de la malla'),
    'hmin': ('Minimum cell (near reinforcement)', 'Célula mínima (perto do reforço)', 'Celda mínima (cerca del refuerzo)'),
    'hmax': ('Maximum cell (far from reinforcement)', 'Célula máxima (longe do reforço)', 'Celda máxima (lejos del refuerzo)'),
    'infl': ('Transition distance', 'Distância de transição', 'Distancia de transición'),
    'keep': ('Solid zone around holes', 'Zona sólida ao redor dos furos', 'Zona sólida alrededor de agujeros'),
    'rim': ('Solid rim', 'Borda sólida', 'Borde sólido'),
    'maxc': ('Cell limit', 'Limite de células', 'Límite de celdas'),
    'seed': ('Random seed', 'Semente aleatória', 'Semilla aleatoria'),
    'mode': ('Depth', 'Profundidade', 'Profundidad'),
    'mode_0': ('Through all', 'Atravessar tudo', 'Atravesar todo'),
    'mode_1': ('Distance', 'Distância', 'Distancia'),
    'depth': ('Cut distance', 'Distância do corte', 'Distancia de corte'),
    'busy': ('Generating the pattern...', 'Gerando o padrão...', 'Generando el patrón...'),
    # ---- problems ----
    'e_expr': ('One of the values is not a valid number or expression.',
               'Algum valor não é um número ou expressão válida.',
               'Algún valor no es un número o expresión válida.'),
    'e_no_outline': ('Could not read the outline of the selected face.',
                     'Não foi possível ler o contorno da face selecionada.',
                     'No se pudo leer el contorno de la cara seleccionada.'),
    'e_bad_wall': ('The wall thickness must be greater than zero.', 'A espessura da parede deve ser maior que zero.',
                   'El espesor de pared debe ser mayor que cero.'),
    'e_bad_params': ('Invalid parameters (check size, transition, rim, solid zone and cell limit).',
                     'Parâmetros inválidos (confira tamanho, transição, borda, zona sólida e limite de células).',
                     'Parámetros no válidos (revise tamaño, transición, borde, zona sólida y límite de celdas).'),
    'e_hmin_ge_hmax': ('The minimum cell must be smaller than the maximum cell.',
                       'A célula mínima deve ser menor que a máxima.',
                       'La celda mínima debe ser menor que la máxima.'),
    'e_wall_too_thick_cell': ('The wall is too thick for the minimum cell (maximum about {maximum:.1f} mm).',
                              'A parede está grossa demais para a célula mínima (máximo cerca de {maximum:.1f} mm).',
                              'La pared es demasiado gruesa para la celda mínima (máximo unos {maximum:.1f} mm).'),
    'e_wall_too_thick_tile': ('The wall near reinforcement is too thick for this tile (maximum about {maximum:.1f} mm).',
                              'A parede perto do reforço está grossa demais para esse ladrilho (máximo cerca de {maximum:.1f} mm).',
                              'La pared cerca del refuerzo es demasiado gruesa para esta baldosa (máximo unos {maximum:.1f} mm).'),
    'e_too_many_cells': ('This face needs about {needed} cells, above the limit of {limit}. Increase the cell size or raise the limit (maximum 1500).',
                         'Esta face precisa de cerca de {needed} células, acima do limite de {limit}. Aumente o tamanho da célula ou o limite (máximo 1500).',
                         'Esta cara necesita unas {needed} celdas, por encima del límite de {limit}. Aumente el tamaño de celda o el límite (máximo 1500).'),
    'e_too_many_tiles': ('About {needed} tiles would be needed. Increase the tile side.',
                         'Seriam necessários cerca de {needed} ladrilhos. Aumente o lado do ladrilho.',
                         'Se necesitarían unas {needed} baldosas. Aumente el lado de la baldosa.'),
    'e_tiles_over_limit': ('{count} tiles exceed the limit of {limit}. Increase the tile side or raise the cell limit.',
                           '{count} ladrilhos passam do limite de {limit}. Aumente o lado do ladrilho ou o limite de células.',
                           '{count} baldosas superan el límite de {limit}. Aumente el lado de la baldosa o el límite de celdas.'),
    'e_no_cells': ('No valid cell fits in this face. Reduce the solid rim / wall or the cell size.',
                   'Nenhuma célula válida cabe nesta face. Reduza a borda sólida / parede ou o tamanho da célula.',
                   'Ninguna celda válida cabe en esta cara. Reduzca el borde sólido / pared o el tamaño de celda.'),
    'e_few_seeds': ('Too few cells fit in this face. Reduce the solid rim or the cell size.',
                    'Poucas células cabem nesta face. Reduza a borda sólida ou o tamanho da célula.',
                    'Caben muy pocas celdas en esta cara. Reduzca el borde sólido o el tamaño de celda.'),
    'e_cut_failed': ('The sketch was created ({cells} shapes, {profiles} profiles) but the cut failed.\n\nLast Fusion error:\n{err}',
                     'O esboço foi criado ({cells} formas, {profiles} perfis), mas o corte falhou.\n\nÚltimo erro do Fusion:\n{err}',
                     'Se creó el boceto ({cells} formas, {profiles} perfiles), pero el corte falló.\n\nÚltimo error de Fusion:\n{err}'),
    'e_no_profiles': ('The sketch was created but Fusion found no closed profile ({cells} shapes drawn).',
                      'O esboço foi criado, mas o Fusion não encontrou nenhum perfil fechado ({cells} formas desenhadas).',
                      'Se creó el boceto, pero Fusion no encontró ningún perfil cerrado ({cells} formas dibujadas).'),
    'e_not_planar': ('Select a planar face.', 'Selecione uma face plana.', 'Seleccione una cara plana.'),
    'no_volume': ('(no error; the cut did not remove volume)', '(nenhum erro; o corte não removeu volume)',
                  '(sin error; el corte no quitó volumen)'),
    # ---- report ----
    'r_title': ('VV Generator - analysis and result', 'VV Generator - análise e resultado', 'VV Generator - análisis y resultado'),
    'r_part': ('PART', 'PEÇA', 'PIEZA'),
    'r_body': ('Body: {body}  |  Component: {comp}', 'Corpo: {body}  |  Componente: {comp}',
               'Cuerpo: {body}  |  Componente: {comp}'),
    'r_face': ('Face: {area:.2f} cm2, {w:.1f} x {h:.1f} mm bounding box, outline {length:.1f} mm in {segs} segments, {holes} inner loop(s)',
               'Face: {area:.2f} cm2, caixa {w:.1f} x {h:.1f} mm, contorno {length:.1f} mm em {segs} segmentos, {holes} laço(s) interno(s)',
               'Cara: {area:.2f} cm2, caja {w:.1f} x {h:.1f} mm, contorno {length:.1f} mm en {segs} segmentos, {holes} lazo(s) interno(s)'),
    'r_reinf': ('Reinforcement: {holes} hole(s) detected, {sel} face(s) selected, {zones} keep-out zone(s)',
                'Reforço: {holes} furo(s) detectado(s), {sel} face(s) selecionada(s), {zones} zona(s) protegida(s)',
                'Refuerzo: {holes} agujero(s) detectado(s), {sel} cara(s) seleccionada(s), {zones} zona(s) protegida(s)'),
    'r_reinf_none': ('Reinforcement: none found - the pattern is uniform. Select faces or keep hole detection on to concentrate material where it is needed.',
                     'Reforço: nenhum encontrado - o padrão é uniforme. Selecione faces ou mantenha a detecção de furos para concentrar material onde precisa.',
                     'Refuerzo: ninguno encontrado - el patrón es uniforme. Seleccione caras o mantenga la detección de agujeros para concentrar material donde se necesita.'),
    'r_ignored': ('Ignored: {n} inner fillet(s); {m} reinforcement face(s) from other components',
                  'Ignorado: {n} raio(s) interno(s); {m} face(s) de reforço de outros componentes',
                  'Ignorado: {n} radio(s) interno(s); {m} cara(s) de refuerzo de otros componentes'),
    'r_pattern': ('PATTERN', 'PADRÃO', 'PATRÓN'),
    'r_items': ('{shape}: {n} shapes (size {smin:.1f} / {smean:.1f} / {smax:.1f} mm min / mean / max)',
                '{shape}: {n} formas (tamanho {smin:.1f} / {smean:.1f} / {smax:.1f} mm mín / médio / máx)',
                '{shape}: {n} formas (tamaño {smin:.1f} / {smean:.1f} / {smax:.1f} mm mín / medio / máx)'),
    'r_zones': ('{a} shape(s) in the reinforced zone, {b} in the light zone',
                '{a} forma(s) na zona reforçada, {b} na zona leve',
                '{a} forma(s) en la zona reforzada, {b} en la zona ligera'),
    'r_walls': ('Measured minimum wall between shapes: {mw} mm (target {tw:.2f} mm). Solid rim: {rim:.1f} mm',
                'Parede mínima medida entre as formas: {mw} mm (alvo {tw:.2f} mm). Borda sólida: {rim:.1f} mm',
                'Pared mínima medida entre las formas: {mw} mm (objetivo {tw:.2f} mm). Borde sólido: {rim:.1f} mm'),
    'r_open': ('Open area: {open:.2f} cm2 = {pf:.0f}% of the face ({pp:.0f}% of the patterned region)',
               'Área aberta: {open:.2f} cm2 = {pf:.0f}% da face ({pp:.0f}% da região com padrão)',
               'Área abierta: {open:.2f} cm2 = {pf:.0f}% de la cara ({pp:.0f}% de la región con patrón)'),
    'r_cov': ('Coverage: {u:.1f}% of the patterned region is farther than a wall from any cell; largest gap {g:.1f} mm',
              'Cobertura: {u:.1f}% da região com padrão está além de uma parede de qualquer célula; maior lacuna {g:.1f} mm',
              'Cobertura: {u:.1f}% de la región con patrón está más lejos que una pared de cualquier celda; mayor hueco {g:.1f} mm'),
    'r_material': ('MATERIAL', 'MATERIAL', 'MATERIAL'),
    'r_vol': ('Volume: {v0:.2f} -> {v1:.2f} cm3 (removed {dv:.2f} cm3 = {pc:.1f}%)',
              'Volume: {v0:.2f} -> {v1:.2f} cm3 (removido {dv:.2f} cm3 = {pc:.1f}%)',
              'Volumen: {v0:.2f} -> {v1:.2f} cm3 (retirado {dv:.2f} cm3 = {pc:.1f}%)'),
    'r_mass': ('Mass: {m0:.1f} -> {m1:.1f} g (saved {dm:.1f} g)', 'Massa: {m0:.1f} -> {m1:.1f} g (economia {dm:.1f} g)',
               'Masa: {m0:.1f} -> {m1:.1f} g (ahorro {dm:.1f} g)'),
    'r_op': ('OPERATION', 'OPERAÇÃO', 'OPERACIÓN'),
    'r_cut': ('{profiles} profiles in the sketch, {cut} cut', '{profiles} perfis no esboço, {cut} cortados',
              '{profiles} perfiles en el boceto, {cut} cortados'),
    'r_warn': ('WARNINGS', 'AVISOS', 'AVISOS'),
    'w_gaps': ('Some regions stayed solid (narrow necks, sharp inner corners or tiny fragments).',
               'Algumas regiões ficaram sólidas (pescoços estreitos, cantos internos vivos ou fragmentos minúsculos).',
               'Algunas regiones quedaron sólidas (cuellos estrechos, esquinas internas vivas o fragmentos diminutos).'),
    'w_cap': ('Cell limit reached: part of the face may have no pattern. Raise the limit or the cell size.',
              'Limite de células atingido: parte da face pode ficar sem padrão. Aumente o limite ou o tamanho da célula.',
              'Límite de celdas alcanzado: parte de la cara puede quedar sin patrón. Aumente el límite o el tamaño de celda.'),
    'w_dropped': ('{n} shape(s) failed the final safety check and were discarded.',
                  '{n} forma(s) falharam na verificação de segurança e foram descartadas.',
                  '{n} forma(s) no pasaron la verificación de seguridad y se descartaron.'),
    'w_draw': ('{n} shape(s) could not be drawn by Fusion and were skipped.',
               '{n} forma(s) não puderam ser desenhadas pelo Fusion e foram ignoradas.',
               '{n} forma(s) no pudo(ieron) dibujarse en Fusion y se omitieron.'),
    'w_uncut': ('{n} profile(s) could not be cut.', '{n} perfil(is) não pôde(puderam) ser cortado(s).',
                '{n} perfil(es) no se pudo(pudieron) cortar.'),
    'w_wall': ('The measured wall is below the target: check the result.',
               'A parede medida ficou abaixo do alvo: verifique o resultado.',
               'La pared medida quedó por debajo del objetivo: revise el resultado.'),
    'w_native': ('The face belongs to a component occurrence: the change applies to the component itself (all copies).',
                 'A face pertence a uma ocorrência de componente: a alteração vale para o próprio componente (todas as cópias).',
                 'La cara pertenece a una ocurrencia de componente: el cambio se aplica al propio componente (todas las copias).'),
    'r_disclaimer': ('Geometric analysis, not FEA: validate with a simulation study.',
                     'Análise geométrica, não MEF: valide com um estudo de simulação.',
                     'Análisis geométrico, no FEM: valide con un estudio de simulación.'),
    # ---- v1.7 ----
    'relax': ('Relaxation (smoothing steps)', 'Relaxamento (passos de suavização)', 'Relajación (pasos de suavizado)'),
    'relax_tip': ('Lloyd relaxation: evens out the cell sizes (0 = off).',
                  'Relaxamento de Lloyd: deixa os tamanhos das células mais uniformes (0 = desligado).',
                  'Relajación de Lloyd: uniformiza el tamaño de las celdas (0 = desactivada).'),
    'sites': ('Seed points (optional)', 'Pontos de semente (opcional)', 'Puntos semilla (opcional)'),
    'sites_tip': ('Sketch points that become cell centres (Voronoi and circles).',
                  'Pontos de esboço que viram centros de célula (Voronoi e círculos).',
                  'Puntos de boceto que serán centros de celda (Voronoi y círculos).'),
    'sites_only': ('Use only my points', 'Usar somente meus pontos', 'Usar solo mis puntos'),
    'preview': ('Preview (slower)', 'Pré-visualizar (mais lento)', 'Vista previa (más lenta)'),
    'e_no_sites': ('No usable seed point: select sketch points inside the face (at least the solid rim away from the outline).',
                   'Nenhum ponto de semente utilizável: selecione pontos de esboço dentro da face (a pelo menos a borda sólida do contorno).',
                   'Ningún punto semilla utilizable: seleccione puntos de boceto dentro de la cara (a al menos el borde sólido del contorno).'),
    'r_uniform': ('Cell-size variation: {cv:.0f}% (lower = more even), {n} relaxation step(s)',
                  'Variação do tamanho das células: {cv:.0f}% (menor = mais uniforme), {n} passo(s) de relaxamento',
                  'Variación del tamaño de celdas: {cv:.0f}% (menor = más uniforme), {n} paso(s) de relajación'),
    'r_sites': ('Seed points: {used} used, {ign} unusable (outside the face, inside the rim or too close)',
                'Pontos de semente: {used} usado(s), {ign} inutilizável(is) (fora da face, dentro da borda ou perto demais)',
                'Puntos semilla: {used} usado(s), {ign} inutilizable(s) (fuera de la cara, dentro del borde o demasiado cerca)'),
    'w_sites_gaps': ('With only your points, regions far from them stay solid (a cell is always convex). Add more points or turn off "Use only my points".',
                     'Só com os seus pontos, as regiões distantes deles ficam sólidas (uma célula é sempre convexa). Adicione mais pontos ou desligue "Usar somente meus pontos".',
                     'Solo con sus puntos, las regiones lejanas quedan sólidas (una celda siempre es convexa). Añada más puntos o desactive "Usar solo mis puntos".'),
    'sketch_only': ('Sketch only (do not cut)', 'Somente esboço (não cortar)', 'Solo boceto (no cortar)'),
    'sketch_only_tip': ('Creates the sketch and leaves the cut to you (Extrude > Cut).',
                        'Cria o esboço e deixa o corte por sua conta (Extrusão > Corte).',
                        'Crea el boceto y deja el corte por su cuenta (Extrusión > Corte).'),
    'r_sketch_only': ('Sketch only: no cut was made. Use Extrude > Cut on the sketch profiles.',
                      'Somente esboço: nenhum corte foi feito. Use Extrusão > Corte nos perfis do esboço.',
                      'Solo boceto: no se hizo ningún corte. Use Extrusión > Corte en los perfiles del boceto.'),
    'e_fusion': ('Fusion reported an error at the step "{stage}":\n{err}\n\nThe sketch was kept visible in the model. Check the timeline to see whether the cut was applied.',
                 'O Fusion informou um erro na etapa "{stage}":\n{err}\n\nO esboço foi mantido visível no modelo. Confira a linha do tempo para ver se o corte foi aplicado.',
                 'Fusion informó un error en el paso "{stage}":\n{err}\n\nEl boceto se mantuvo visible en el modelo. Revise la línea de tiempo para ver si se aplicó el corte.'),
    'r_fallback': ('Pattern created: {n} shapes, {cut} profile(s) cut. The detailed report could not be built ({err}).',
                   'Padrão criado: {n} formas, {cut} perfil(is) cortado(s). O relatório detalhado não pôde ser montado ({err}).',
                   'Patrón creado: {n} formas, {cut} perfil(es) cortado(s). No se pudo construir el informe detallado ({err}).'),
    'r_time': ('Generated in {sec:.1f} s', 'Gerado em {sec:.1f} s', 'Generado en {sec:.1f} s'),
}
_LANG_IDX = {'en': 0, 'pt': 1, 'es': 2}


def _lang():
    try:
        ul = _app.preferences.generalPreferences.userLanguage
        UL = adsk.core.UserLanguages
        if ul == getattr(UL, 'PortugueseBrazilianLanguage', -1):
            return 'pt'
        if ul == getattr(UL, 'SpanishLanguage', -1):
            return 'es'
    except Exception:
        pass
    return 'en'


def tr(key, **kw):
    s = _T[key][_LANG_IDX[_lang()]]
    return s.format(**kw) if kw else s


def _log(text):
    try:
        _app.log(text)
    except Exception:
        pass


# ----------------------------------------------------------------------------
# Reading the part
# ----------------------------------------------------------------------------
def _frame_and_converter(sk):
    P = adsk.core.Point3D.create
    o = sk.sketchToModelSpace(P(0, 0, 0))
    px = sk.sketchToModelSpace(P(1, 0, 0))
    py = sk.sketchToModelSpace(P(0, 1, 0))
    ex = (px.x - o.x, px.y - o.y, px.z - o.z)
    ey = (py.x - o.x, py.y - o.y, py.z - o.z)
    frame = {'o': (o.x, o.y, o.z), 'ex': ex, 'ey': ey}
    n1 = math.sqrt(sum(c * c for c in ex))
    n2 = math.sqrt(sum(c * c for c in ey))
    dot = sum(a * b for a, b in zip(ex, ey))
    if abs(n1 - 1) < 1e-6 and abs(n2 - 1) < 1e-6 and abs(dot) < 1e-6:
        def to2d(p):
            vx, vy, vz = p.x - o.x, p.y - o.y, p.z - o.z
            return (vx * ex[0] + vy * ex[1] + vz * ex[2], vx * ey[0] + vy * ey[1] + vz * ey[2])
    else:
        def to2d(p):
            q = sk.modelToSketchSpace(p)
            return (q.x, q.y)
    return frame, to2d


def face_segments(face, to2d):
    """Outline of every loop of the face as 2D segments (sketch space)."""
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
            q = [to2d(p) for p in pts]
            for i in range(len(q) - 1):
                segs.append((q[i][0], q[i][1], q[i + 1][0], q[i + 1][1]))
    return segs


def classify_cylinder(body, f):
    """'hole' (inner cylinder spanning >= ~160 deg), 'fillet' (inner, shorter) or None (outer / other)."""
    try:
        if f.geometry.surfaceType != adsk.core.SurfaceTypes.CylinderSurfaceType:
            return None
        cyl = f.geometry
        pt = f.pointOnFace
        ok, n = f.evaluator.getNormalAtPoint(pt)
        if not ok:
            return None
        nx, ny, nz = n.x, n.y, n.z
        try:   # make the normal point out of the material (do not trust face orientation)
            q = adsk.core.Point3D.create(pt.x + nx * 0.01, pt.y + ny * 0.01, pt.z + nz * 0.01)
            PC = getattr(adsk.fusion, 'PointContainment', None) or getattr(adsk.core, 'PointContainment', None)
            if body.pointContainment(q) == PC.PointInsidePointContainment:
                nx, ny, nz = -nx, -ny, -nz
        except Exception:
            pass
        o, ax = cyl.origin, cyl.axis
        v = (pt.x - o.x, pt.y - o.y, pt.z - o.z)
        t = v[0] * ax.x + v[1] * ax.y + v[2] * ax.z
        rad = (v[0] - t * ax.x, v[1] - t * ax.y, v[2] - t * ax.z)
        if rad[0] * nx + rad[1] * ny + rad[2] * nz >= 0:
            return None
        span = 2 * math.pi
        try:
            rng = f.evaluator.parametricRange()
            span = abs(rng.maxPoint.x - rng.minPoint.x)
        except Exception:
            pass
        return 'hole' if span >= 2.8 else 'fillet'
    except Exception:
        return None


def site_to_2d(sp, to2d, comp_token):
    """Sketch point -> 2D coordinates in the pattern sketch (None if it lives in another component)."""
    try:
        native = sp.nativeObject if getattr(sp, 'nativeObject', None) else sp
        other = native.parentSketch
        if comp_token and _token(other.parentComponent) != comp_token:
            return None
        return to2d(other.sketchToModelSpace(native.geometry))
    except Exception:
        return None


def sample_face(f, maxpts=600):
    """3D sample points of a face (mesh nodes, evenly subsampled)."""
    calc = f.meshManager.createMeshCalculator()
    calc.surfaceTolerance = 0.02
    try:
        calc.maxSideLength = 0.3
    except Exception:
        pass
    mesh = calc.calculate()
    c = mesh.nodeCoordinatesAsDouble
    pts = [(c[i], c[i + 1], c[i + 2]) for i in range(0, len(c) - 2, 3)]
    if len(pts) > maxpts:
        pts = random.Random(1).sample(pts, maxpts)
    return pts


# ----------------------------------------------------------------------------
# Drawing and cutting
# ----------------------------------------------------------------------------
def draw_item(sk, item):
    """Draw one shape. Returns True on success; on failure removes the curves it created."""
    Pt = adsk.core.Point3D.create
    lines = sk.sketchCurves.sketchLines
    arcs = sk.sketchCurves.sketchArcs
    created = []
    try:
        if item[0] == 'C':
            created.append(sk.sketchCurves.sketchCircles.addByCenterRadius(Pt(item[1], item[2], 0), item[3]))
            return True
        prims = vv_engine.path_prims(item[1], item[2])
        first = prev = None
        for idx, pr in enumerate(prims):
            last = (idx == len(prims) - 1)
            start = Pt(pr[1][0], pr[1][1], 0) if prev is None else prev.endSketchPoint
            if pr[0] == 'L':
                end = first.startSketchPoint if (last and first is not None) else Pt(pr[2][0], pr[2][1], 0)
                obj = lines.addByTwoPoints(start, end)
            else:
                obj = arcs.addByThreePoints(start, Pt(pr[2][0], pr[2][1], 0), Pt(pr[3][0], pr[3][1], 0))
            created.append(obj)
            if first is None:
                first = obj
            prev = obj
        return True
    except Exception:
        for c in created:
            try:
                c.deleteMe()
            except Exception:
                pass
        return False


class VVError(Exception):
    """A user-facing problem (the message is already translated)."""


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _body_depth(body, nrm):
    """Extent of the body along the cut direction (finite fallback for 'through all')."""
    try:
        bb = body.boundingBox
        size = (bb.maxPoint.x - bb.minPoint.x, bb.maxPoint.y - bb.minPoint.y, bb.maxPoint.z - bb.minPoint.z)
        return abs(nrm[0]) * size[0] + abs(nrm[1]) * size[1] + abs(nrm[2]) * size[2] + 0.2
    except Exception:
        return 100.0


def cut_profiles(comp, body, face, nrm, profiles, through, depth):
    """Extrude-cut the profiles with a chain of fallbacks. Returns (count_cut, last_error).

    Order: whole set at once -> batches of 20 -> 5 -> single profiles (only if few remain).
    Each attempt tries both directions and, for 'through all', first the 'all' extent and then a finite
    depth equal to the body's extent (some kernel errors only happen with the 'all' extent).
    Every attempt checks that the volume really dropped and removes a feature that did nothing."""
    ext = comp.features.extrudeFeatures
    D = adsk.fusion.ExtentDirections
    first, second = D.NegativeExtentDirection, D.PositiveExtentDirection
    try:
        ok, fn = face.evaluator.getNormalAtPoint(face.pointOnFace)
        if ok and (fn.x * nrm[0] + fn.y * nrm[1] + fn.z * nrm[2]) < 0:
            first, second = second, first
    except Exception:
        pass
    modes = ['all', 'dist'] if through else ['dist']
    dist_value = _body_depth(body, nrm) if through else depth
    state = {'order': [first, second], 'modes': modes, 'err': ''}

    def make_cut(plist, direction, mode):
        col = adsk.core.ObjectCollection.create()
        for p in plist:
            col.add(p)
        inp = ext.createInput(col, adsk.fusion.FeatureOperations.CutFeatureOperation)
        if mode == 'all':
            inp.setAllExtent(direction)
        else:
            dd = adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByReal(dist_value))
            inp.setOneSideExtent(dd, direction)
        inp.participantBodies = [body]
        return ext.add(inp)

    def attempt(plist):
        vol0 = _safe(lambda: body.volume)
        for mode in list(state['modes']):
            for direction in list(state['order']):
                try:
                    feat = make_cut(plist, direction, mode)
                except Exception:
                    state['err'] = traceback.format_exc()
                    continue
                vol1 = _safe(lambda: body.volume)
                if vol0 is None or vol1 is None or vol1 < vol0 - 1e-9:
                    state['order'] = [direction] + [d for d in state['order'] if d != direction]
                    state['modes'] = [mode] + [m for m in state['modes'] if m != mode]
                    return True
                try:
                    feat.deleteMe()
                except Exception:
                    pass
        return False

    done = 0
    remaining = list(profiles)
    for size in (len(profiles), 20, 5, 1):
        if not remaining:
            break
        if size == 1 and len(remaining) > 60:
            break
        failed = []
        step = max(1, size)
        for k in range(0, len(remaining), step):
            chunk = remaining[k:k + step]
            if attempt(chunk):
                done += len(chunk)
            else:
                failed.extend(chunk)
        remaining = failed
    return done, state['err']


def _token(obj):
    try:
        return obj.entityToken
    except Exception:
        return None


def _mass_g(body):
    try:
        m = body.physicalProperties.mass     # kg
        return m * 1000.0 if m and m > 0 else None
    except Exception:
        return None


# ----------------------------------------------------------------------------
# Main operation
# ----------------------------------------------------------------------------
def build(vals, preview=False):
    """Create the sketch (always left visible) and, unless 'sketch only', cut it.
    Fusion errors are turned into a friendly message that names the step; the sketch stays visible."""
    ctx = {'sk': None, 'stage': 'init'}
    try:
        return _build_impl(vals, preview, ctx)
    except (VVError, vv_engine.EngineError):
        raise
    except Exception as e:
        sk = ctx['sk']
        if sk is not None:
            try:
                sk.isLightBulbOn = True
            except Exception:
                pass
        _log(traceback.format_exc())
        raise VVError(tr('e_fusion', stage=ctx['stage'], err=str(e)))


def _build_impl(vals, preview, ctx):
    face_in = vals['face']
    face = face_in.nativeObject if getattr(face_in, 'nativeObject', None) else face_in
    from_occurrence = face is not face_in
    body = face.body
    comp = body.parentComponent

    design = adsk.fusion.Design.cast(_app.activeProduct)
    tl = None
    try:
        if design is not None and design.designType == adsk.fusion.DesignTypes.ParametricDesignType:
            tl = design.timeline
    except Exception:
        tl = None
    tl_start = tl.count if tl is not None else 0

    # Everything about the face / body that the report needs is read NOW: the cut consumes the original
    # face, and reading it afterwards raises "InternalValidationError : asmFace".
    ctx['stage'] = 'read'
    info = {
        'body': _safe(lambda: body.name, '?'), 'comp': _safe(lambda: comp.name, '?'),
        'face_area': _safe(lambda: face.area, 0.0),
        'holes_loops': _safe(lambda: sum(1 for l in face.loops if not l.isOuter), 0),
        'vol0': _safe(lambda: body.volume), 'mass0': _mass_g(body),
        'from_occurrence': from_occurrence,
    }

    ctx['stage'] = 'sketch'
    sk = comp.sketches.add(face)
    ctx['sk'] = sk
    sk.name = 'VV Generator'
    frame, to2d = _frame_and_converter(sk)
    segs = face_segments(face, to2d)
    if not segs:
        sk.deleteMe()
        ctx['sk'] = None
        raise vv_engine.EngineError('no_outline')

    # ---- reinforcement ----
    ctx['stage'] = 'reinforcement'
    n_holes = n_fillets = n_foreign = 0
    rfaces = []
    comp_token = _token(comp)
    face_token = _token(face)
    for f in vals['extra']:
        nf = f.nativeObject if getattr(f, 'nativeObject', None) else f
        if face_token and _token(nf) == face_token:
            continue                      # the pattern face itself is not a reinforcement
        try:
            if comp_token and _token(nf.body.parentComponent) != comp_token:
                n_foreign += 1            # coordinates would be in another component's space
                continue
        except Exception:
            pass
        rfaces.append(nf)
    n_sel = len(rfaces)
    if vals['auto']:
        for f in body.faces:
            kind = classify_cylinder(body, f)
            if kind == 'hole':
                rfaces.append(f)
                n_holes += 1
            elif kind == 'fillet':
                n_fillets += 1
    rpts = []
    for f in rfaces:
        try:
            rpts.extend(sample_face(f))
        except Exception:
            pass

    sites = []
    n_bad_sites = 0
    for sp in vals['sites']:
        pt = site_to_2d(sp, to2d, comp_token)
        if pt is None:
            n_bad_sites += 1
        else:
            sites.append(pt)

    ctx['stage'] = 'engine'
    P = vv_engine.Params(shape=vals['shape'], wall=vals['wall'], hmin=vals['hmin'], hmax=vals['hmax'],
                         infl=vals['infl'], rim=vals['rim'], keep=vals['keep'], max_cells=vals['maxc'],
                         seed=vals['seed'], corner_r=vals['corner'], tile=vals['tile'],
                         wall_max=vals['wmax'], angle=vals['angle'], relax=vals['relax'],
                         sites=sites, sites_only=bool(vals['sites_only']))
    try:
        items, st = vv_engine.generate(segs, rpts, frame, P)
    except Exception:
        try:
            sk.deleteMe()
        except Exception:
            pass
        ctx['sk'] = None
        raise

    # ---- draw ----
    ctx['stage'] = 'draw'
    failed = 0
    sk.isComputeDeferred = True
    try:
        for it in items:
            if not draw_item(sk, it):
                failed += 1
    finally:
        sk.isComputeDeferred = False
    sk.isLightBulbOn = True               # the sketch is always left visible for the user
    profiles = [p for p in sk.profiles]
    if not profiles:
        raise VVError(tr('e_no_profiles', cells=len(items)))

    info.update({'rpts': len(rpts), 'n_holes': n_holes, 'n_sel': n_sel, 'n_fillets': n_fillets,
                 'n_foreign': n_foreign, 'n_bad_sites': n_bad_sites, 'failed': failed, 'profiles': len(profiles),
                 'cut': 0, 'items': len(items)})

    # ---- cut ----
    if not vals['sketch_only']:
        ctx['stage'] = 'cut'
        n = (frame['ex'][1] * frame['ey'][2] - frame['ex'][2] * frame['ey'][1],
             frame['ex'][2] * frame['ey'][0] - frame['ex'][0] * frame['ey'][2],
             frame['ex'][0] * frame['ey'][1] - frame['ex'][1] * frame['ey'][0])
        nl = math.sqrt(sum(c * c for c in n)) or 1.0
        nrm = (n[0] / nl, n[1] / nl, n[2] / nl)
        cut, err = cut_profiles(comp, body, face, nrm, profiles, vals['through'], vals['depth'])
        if cut == 0:
            raise VVError(tr('e_cut_failed', cells=len(items), profiles=len(profiles),
                             err=err or tr('no_volume')))
        info['cut'] = cut
        info['vol1'] = _safe(lambda: body.volume)
        info['mass1'] = _mass_g(body)
    if preview:
        return None

    ctx['stage'] = 'group'
    if tl is not None:
        try:
            if tl.count - 1 >= tl_start:
                tl.timelineGroups.add(tl_start, tl.count - 1).name = 'VV Generator'
        except Exception:
            pass

    ctx['stage'] = 'report'
    try:
        text = _report(vals, st, info)
    except Exception as e:
        text = tr('r_fallback', n=len(items), cut=info['cut'], err=str(e))
    _log(text)
    return text


def _report(vals, st, info):
    """Build the text report from values captured BEFORE the cut (never touches the consumed face)."""
    face_area = info['face_area']
    bx0, by0, bx1, by1 = st['bbox']
    lines = [tr('r_title') + '  v' + VERSION, '', tr('r_part'),
             tr('r_body', body=info['body'], comp=info['comp']),
             tr('r_face', area=face_area, w=(bx1 - bx0) * 10, h=(by1 - by0) * 10, length=st['outline_length'] * 10,
                segs=st['outline_segments'], holes=info['holes_loops'])]
    if info['rpts']:
        lines.append(tr('r_reinf', holes=info['n_holes'], sel=info['n_sel'], zones=st['zones']))
    else:
        lines.append(tr('r_reinf_none'))
    if info['n_fillets'] or info['n_foreign']:
        lines.append(tr('r_ignored', n=info['n_fillets'], m=info['n_foreign']))
    shape_name = tr('shape_%d' % SHAPE_KEYS.index(vals['shape']))
    lines += ['', tr('r_pattern'),
              tr('r_items', shape=shape_name, n=st['items'], smin=st['size_min'] * 10, smean=st['size_mean'] * 10,
                 smax=st['size_max'] * 10)]
    if info['rpts']:
        lines.append(tr('r_zones', a=st['reinforced_items'], b=st['light_items']))
    if vals['shape'] in ('voronoi', 'rounded', 'circle'):
        lines.append(tr('r_uniform', cv=100.0 * st['uniformity_cv'], n=st['relax_iterations']))
    if vals['sites']:
        lines.append(tr('r_sites', used=st['sites_used'], ign=st['sites_ignored'] + info['n_bad_sites']))
    mw = '%.2f' % (st['min_gap'] * 10) if st['min_gap'] is not None else '-'
    lines.append(tr('r_walls', mw=mw, tw=vals['wall'] * 10, rim=vals['rim'] * 10))
    lines.append(tr('r_open', open=st['open_area'], pf=100.0 * st['open_area'] / face_area if face_area > 0 else 0.0,
                    pp=100.0 * st['open_ratio_free']))
    lines.append(tr('r_cov', u=st['uncovered_pct'], g=st['gap_max'] * 10))
    if vals['sketch_only']:
        lines += ['', tr('r_op'), tr('r_sketch_only'), tr('r_time', sec=st['seconds'])]
    else:
        vol0, vol1 = info.get('vol0'), info.get('vol1')
        if vol0 is not None and vol1 is not None:
            dv = vol0 - vol1
            lines += ['', tr('r_material'),
                      tr('r_vol', v0=vol0, v1=vol1, dv=dv, pc=100.0 * dv / vol0 if vol0 > 0 else 0.0)]
            if info.get('mass0') and info.get('mass1'):
                lines.append(tr('r_mass', m0=info['mass0'], m1=info['mass1'], dm=info['mass0'] - info['mass1']))
        lines += ['', tr('r_op'), tr('r_cut', profiles=info['profiles'], cut=info['cut']), tr('r_time', sec=st['seconds'])]
    warn = []
    if st['uncovered_pct'] > 2.0:
        warn.append(tr('w_sites_gaps') if vals['sites_only'] and vals['sites'] else tr('w_gaps'))
    if st['hit_cap']:
        warn.append(tr('w_cap'))
    if st['dropped']:
        warn.append(tr('w_dropped', n=st['dropped']))
    if info['failed']:
        warn.append(tr('w_draw', n=info['failed']))
    if not vals['sketch_only'] and info['cut'] < info['profiles']:
        warn.append(tr('w_uncut', n=info['profiles'] - info['cut']))
    if st['min_gap'] is not None and st['min_gap'] < vals['wall'] - 1e-4 and not vals['shape'] == 'circle':
        warn.append(tr('w_wall'))
    if info['from_occurrence']:
        warn.append(tr('w_native'))
    if warn:
        lines += ['', tr('r_warn')] + ['- ' + w for w in warn]
    lines += ['', tr('r_disclaimer')]
    return '\n'.join(lines)


# ----------------------------------------------------------------------------
# Command inputs
# ----------------------------------------------------------------------------
def read_values(inputs):
    """Read the dialog. Raises ValueError if any numeric field is not a valid expression."""
    def val(id_):
        inp = inputs.itemById(id_)
        if not inp.isValidExpression:
            raise ValueError('expr')
        return inp.value

    sel = inputs.itemById('reinf')
    sites_in = inputs.itemById('sites')
    face_in = inputs.itemById('face')
    return {
        'face': face_in.selection(0).entity if face_in.selectionCount == 1 else None,
        'extra': [sel.selection(k).entity for k in range(sel.selectionCount)],
        'sites': [sites_in.selection(k).entity for k in range(sites_in.selectionCount)],
        'sites_only': inputs.itemById('sites_only').value,
        'sketch_only': inputs.itemById('sketch_only').value,
        'relax': inputs.itemById('relax').value,
        'auto': inputs.itemById('auto').value,
        'shape': SHAPE_KEYS[inputs.itemById('shape').selectedItem.index],
        'corner': max(0.0, val('corner')),
        'wall': val('wall'), 'tile': val('tile'), 'wmax': val('wmax'), 'angle': val('angle'),
        'hmin': val('hmin'), 'hmax': val('hmax'), 'infl': val('infl'), 'keep': val('keep'), 'rim': val('rim'),
        'maxc': inputs.itemById('maxc').value, 'seed': inputs.itemById('seed').value,
        'through': inputs.itemById('mode').selectedItem.index == 0,
        'depth': val('depth'),
    }


def check_values(v):
    """Returns (code, info) for the first problem, or (None, None)."""
    tiling = v['shape'] in ('hex', 'tri')
    if v['sites_only'] and not tiling and not v['sites']:
        return 'no_sites', {}
    if v['wall'] <= 0:
        return 'bad_wall', {}
    if v['rim'] < 0 or v['keep'] < 0 or v['infl'] <= 0:
        return 'bad_params', {}
    if not v['through'] and v['depth'] <= 0:
        return 'bad_params', {}
    if tiling:
        if v['tile'] <= 0:
            return 'bad_params', {}
        apo = v['tile'] * math.sqrt(3) / 2.0 if v['shape'] == 'hex' else v['tile'] / (2 * math.sqrt(3))
        if max(v['wall'], v['wmax']) > 1.2 * apo:
            return 'wall_too_thick_tile', {'maximum': 12 * apo}
    else:
        if v['hmin'] <= 0 or v['hmax'] <= 0:
            return 'bad_params', {}
        if v['hmin'] >= v['hmax']:
            return 'hmin_ge_hmax', {}
        if v['wall'] > 0.6 * v['hmin']:
            return 'wall_too_thick_cell', {'maximum': 6 * v['hmin']}
    return None, None


def problem_text(code, info):
    return tr('e_' + code, **info) if info else tr('e_' + code)


def _update_status(inputs):
    st = inputs.itemById('status')
    try:
        code, info = check_values(read_values(inputs))
        text = problem_text(code, info) if code else ''
    except ValueError:
        text = tr('e_expr')
    except Exception:
        text = ''
    st.formattedText = ('\u26a0 ' + text) if text else ''
    st.isVisible = bool(text)


class ExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            vals = read_values(args.command.commandInputs)
            code, info = check_values(vals)
            if code:
                _ui.messageBox(problem_text(code, info), CMD_NAME)
                return
            if vals['face'] is None:
                _ui.messageBox(tr('e_not_planar'), CMD_NAME)
                return
            report = build(vals)
            _log(report)
            _ui.messageBox(report, CMD_NAME)
        except vv_engine.EngineError as e:
            _ui.messageBox(problem_text(e.code, e.info), CMD_NAME)
        except VVError as e:
            _ui.messageBox(str(e), CMD_NAME)
        except ValueError:
            _ui.messageBox(tr('e_expr'), CMD_NAME)
        except Exception:
            tb = traceback.format_exc()
            _log(tb)
            _ui.messageBox('Error:\n{}'.format(tb), CMD_NAME)


class PreviewHandler(adsk.core.CommandEventHandler):
    """Optional live preview: runs the real build inside Fusion's preview transaction (rolled back by Fusion)."""

    def notify(self, args):
        try:
            i = args.command.commandInputs
            if not i.itemById('preview').value:
                return
            vals = read_values(i)
            code, _ = check_values(vals)
            if code or vals['face'] is None:
                return
            build(vals, preview=True)
        except Exception:
            pass                      # a preview must never show an error dialog
        try:
            args.isValidResult = False  # OK always runs the normal execute (with report)
        except Exception:
            pass


class ValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            v = read_values(args.inputs)
            code, _ = check_values(v)
            args.areInputsValid = (code is None and v['face'] is not None)
        except Exception:
            args.areInputsValid = False


class InputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        try:
            i = args.inputs
            if args.input.id == 'mode':
                i.itemById('depth').isVisible = (i.itemById('mode').selectedItem.index != 0)
            elif args.input.id == 'shape':
                key = SHAPE_KEYS[i.itemById('shape').selectedItem.index]
                i.itemById('corner').isVisible = key in ('rounded', 'hex', 'tri')
                til = key in ('hex', 'tri')
                for id_ in ('relax', 'sites', 'sites_only'):
                    i.itemById(id_).isVisible = not til
                for id_ in ('tile', 'wmax', 'angle'):
                    i.itemById(id_).isVisible = til
                for id_ in ('hmin', 'hmax'):
                    i.itemById(id_).isVisible = not til
            _update_status(i)
        except Exception:
            pass


class CreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            i = cmd.commandInputs
            VI = adsk.core.ValueInput.createByString

            logo_path = os.path.join(RES, 'logo.png')
            if os.path.isfile(logo_path):
                try:
                    i.addImageCommandInput('logo', '', logo_path).isFullWidth = True
                except Exception:
                    pass

            f = i.addSelectionInput('face', tr('face'), tr('face_tip'))
            f.addSelectionFilter('PlanarFaces')
            f.setSelectionLimits(1, 1)

            r = i.addSelectionInput('reinf', tr('reinf'), tr('reinf_tip'))
            r.addSelectionFilter('Faces')
            r.setSelectionLimits(0, 0)

            i.addBoolValueInput('auto', tr('auto'), True, '', True)

            sp = i.addSelectionInput('sites', tr('sites'), tr('sites_tip'))
            sp.addSelectionFilter('SketchPoints')
            sp.setSelectionLimits(0, 0)
            i.addBoolValueInput('sites_only', tr('sites_only'), True, '', False)

            sd = i.addDropDownCommandInput('shape', tr('shape'), adsk.core.DropDownStyles.TextListDropDownStyle)
            for k in range(len(SHAPE_KEYS)):
                sd.listItems.add(tr('shape_%d' % k), k == 0)
            cr = i.addValueInput('corner', tr('corner'), 'mm', VI('1.5 mm'))
            cr.isVisible = False

            w = i.addValueInput('wall', tr('wall'), 'mm', VI('1.2 mm'))
            w.tooltip = tr('wall_tip')
            t1 = i.addValueInput('tile', tr('tile'), 'mm', VI('9 mm'))
            t2 = i.addValueInput('wmax', tr('wmax'), 'mm', VI('2.5 mm'))
            t3 = i.addValueInput('angle', tr('angle'), 'deg', VI('0 deg'))
            for t_ in (t1, t2, t3):
                t_.isVisible = False
            i.addValueInput('hmin', tr('hmin'), 'mm', VI('6 mm'))
            i.addValueInput('hmax', tr('hmax'), 'mm', VI('16 mm'))
            i.addValueInput('infl', tr('infl'), 'mm', VI('30 mm'))
            i.addValueInput('keep', tr('keep'), 'mm', VI('4 mm'))
            i.addValueInput('rim', tr('rim'), 'mm', VI('4 mm'))
            rx = i.addIntegerSpinnerCommandInput('relax', tr('relax'), 0, 10, 1, 3)
            rx.tooltip = tr('relax_tip')
            i.addIntegerSpinnerCommandInput('maxc', tr('maxc'), 10, 1500, 10, 400)
            i.addIntegerSpinnerCommandInput('seed', tr('seed'), 1, 9999, 1, 1)

            dd = i.addDropDownCommandInput('mode', tr('mode'), adsk.core.DropDownStyles.TextListDropDownStyle)
            dd.listItems.add(tr('mode_0'), True)
            dd.listItems.add(tr('mode_1'), False)
            i.addValueInput('depth', tr('depth'), 'mm', VI('3 mm')).isVisible = False

            so = i.addBoolValueInput('sketch_only', tr('sketch_only'), True, '', False)
            so.tooltip = tr('sketch_only_tip')
            i.addBoolValueInput('preview', tr('preview'), True, '', False)
            st = i.addTextBoxCommandInput('status', '', '', 3, True)
            st.isVisible = False
            st.isFullWidth = True
            foot = i.addTextBoxCommandInput('footer', '', '<div align="center"><i>' + FOOTER + '</i></div>', 1, True)
            foot.isFullWidth = True

            for handler, event in ((ExecuteHandler(), cmd.execute), (InputChangedHandler(), cmd.inputChanged),
                                   (ValidateHandler(), cmd.validateInputs), (PreviewHandler(), cmd.executePreview)):
                event.add(handler)
                _handlers.append(handler)
        except Exception:
            _ui.messageBox('Error:\n{}'.format(traceback.format_exc()), CMD_NAME)


# ----------------------------------------------------------------------------
# Add-in lifecycle
# ----------------------------------------------------------------------------
def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface
        importlib.reload(vv_engine)          # pick up a new engine after Stop/Run without restarting Fusion

        icon_ok = os.path.isfile(os.path.join(RES, '16x16.png')) and os.path.isfile(os.path.join(RES, '32x32.png'))
        panel = _ui.allToolbarPanels.itemById(PANEL_ID)
        if panel is None:
            raise RuntimeError('Toolbar panel %s not found (open the Design workspace).' % PANEL_ID)
        old_ctrl = panel.controls.itemById(CMD_ID)
        if old_ctrl:                         # stale control / definition from a previous run
            old_ctrl.deleteMe()
        cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()
        cmd_def = _ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, tr('desc'),
                                                             ICON_DIR if icon_ok else '')
        try:
            cmd_def.toolClipFilename = os.path.join(RES, 'logo.png')
        except Exception:
            pass
        handler = CreatedHandler()
        cmd_def.commandCreated.add(handler)
        _handlers.append(handler)

        ctrl = panel.controls.addCommand(cmd_def)
        ctrl.isPromoted = True
    except Exception:
        if _ui:
            _ui.messageBox('Error starting {}:\n{}'.format(CMD_NAME, traceback.format_exc()), CMD_NAME)


def stop(context):
    try:
        panel = _ui.allToolbarPanels.itemById(PANEL_ID)
        ctrl = panel.controls.itemById(CMD_ID)
        if ctrl:
            ctrl.deleteMe()
        cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()
        del _handlers[:]
    except Exception:
        if _ui:
            _ui.messageBox('Error stopping {}:\n{}'.format(CMD_NAME, traceback.format_exc()), CMD_NAME)
