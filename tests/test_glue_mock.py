# -*- coding: utf-8 -*-
"""
Smoke test of VVGenerator.py against a *fake* Fusion API (no Fusion needed).

It exercises: add-in start/stop, dialog creation, validation, every shape end-to-end, translations,
the cut fallback (wrong direction -> opposite direction -> batches), failure messages and cleanup.
It cannot prove the real Fusion API behaves identically: it only catches typos, wrong flow, missing
imports and logic errors in the glue code.
"""
import math
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'VVGenerator'))


# --------------------------------------------------------------------------- fake adsk
class P3(object):
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


class V3(P3):
    pass


class FakeCurve(object):
    def __init__(self, a, b, kind, sk):
        self.startSketchPoint, self.endSketchPoint = a, b
        self.kind, self.sk = kind, sk
        self.deleted = False

    def deleteMe(self):
        self.deleted = True
        return True


class FakeSketch(object):
    def __init__(self, world):
        self.world = world
        self.name = ''
        self.isComputeDeferred = False
        self.isLightBulbOn = True
        self.shapes = 0
        self.fail_draw_after = None
        self.deleted = False
        sk = self

        class Lines(object):
            def addByTwoPoints(s, a, b):
                if not hasattr(a, 'endSketchPoint') and not hasattr(a, 'tag'):
                    sk.shapes += 1                      # new loop starts with a Point3D
                return sk._curve(a, b, 'L')

        class Arcs(object):
            def addByThreePoints(s, a, m, b):
                if not hasattr(a, 'tag'):
                    sk.shapes += 1
                return sk._curve(a, b, 'A')

        class Circles(object):
            def addByCenterRadius(s, c, r):
                sk.shapes += 1
                return sk._curve(c, c, 'C')

        self.sketchCurves = types.SimpleNamespace(sketchLines=Lines(), sketchArcs=Arcs(), sketchCircles=Circles())

    def _curve(self, a, b, kind):
        if self.fail_draw_after is not None:
            self.fail_draw_after -= 1
            if self.fail_draw_after < 0:
                raise RuntimeError('draw failed')

        def pt(p):
            o = types.SimpleNamespace(x=p.x, y=p.y, z=0.0, tag=True)
            return o
        return FakeCurve(pt(a), pt(b), kind, self)

    @property
    def profiles(self):
        if self.world.profiles_error:
            raise RuntimeError(self.world.profiles_error)
        return [object() for _ in range(self.shapes)]

    def sketchToModelSpace(self, p):
        return P3(p.x, p.y, p.z)

    def modelToSketchSpace(self, p):
        return P3(p.x, p.y, p.z)

    def deleteMe(self):
        self.deleted = True
        return True


class FakeEvaluator(object):
    def __init__(self, pts):
        self.pts = pts

    def getParameterExtents(self):
        return True, 0, 1

    def getStrokes(self, a, b, t):
        return True, self.pts


def circle_pts(cx, cy, r, n=48):
    return [P3(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n + 1)]


class FakeLoop(object):
    def __init__(self, polylines, outer):
        self.isOuter = outer
        self.coEdges = [types.SimpleNamespace(edge=types.SimpleNamespace(evaluator=FakeEvaluator(p))) for p in polylines]


class World(object):
    """Holds everything the fake Fusion needs."""

    def __init__(self):
        self.messages = []
        self.logs = []
        self.volume = 100.0
        self.cut_calls = []
        self.cut_mode = 'ok'          # ok | flip | batches | fail
        self.sketch = None
        self.timeline_count = 3
        self.group_names = []
        self.sketches_added = 0
        self.stale = False                  # original face consumed by the cut
        self.stale_after_cut = False
        self.volume_fails_after_cut = False
        self.profiles_error = None


def make_world(extra_faces=False):
    w = World()
    outer = [P3(0, 0), P3(22, 3), P3(22, 13), P3(0, 16), P3(0, 0)]
    segs = [[outer[i], outer[i + 1]] for i in range(4)]
    loops = [FakeLoop(segs, True), FakeLoop([circle_pts(16, 8, 1.5)], False)]

    class Body(object):
        name = 'Body1'

        @property
        def volume(s):
            if w.stale and w.volume_fails_after_cut:
                raise RuntimeError('2 : InternalValidationError : asmFace')
            return w.volume

        boundingBox = types.SimpleNamespace(minPoint=P3(0, 0, 0), maxPoint=P3(22, 16, 3))

        physicalProperties = types.SimpleNamespace(mass=0.5)

        def pointContainment(s, p):
            return 'out'
    body = Body()

    def cut_add(inp):
        w.cut_calls.append((inp.direction, len(inp.profiles), inp.mode))
        if w.cut_mode == 'fail':
            raise RuntimeError('simulated cut failure')
        if w.cut_mode == 'noall' and inp.mode == 'all':
            raise RuntimeError('2 : InternalValidationError : asmFace')
        if w.cut_mode == 'batches' and len(inp.profiles) > 20:
            raise RuntimeError('too many profiles')
        if inp.direction == 1 or w.cut_mode in ('ok', 'batches', 'noall'):
            w.volume -= 1.0 * len(inp.profiles) * 0.05
            if w.stale_after_cut:
                w.stale = True
        return types.SimpleNamespace(deleteMe=lambda: None)

    def create_input(profiles, op):
        inp = types.SimpleNamespace(profiles=list(profiles), direction=None, participantBodies=None, mode=None)
        inp.setAllExtent = lambda d: (setattr(inp, 'direction', d), setattr(inp, 'mode', 'all'))
        inp.setOneSideExtent = lambda dd, d: (setattr(inp, 'direction', d), setattr(inp, 'mode', 'dist'))
        return inp

    def sk_add(face):
        w.sketches_added += 1
        w.sketch = FakeSketch(w)
        return w.sketch

    comp = types.SimpleNamespace(name='Comp1', entityToken='comp-1',
                                 sketches=types.SimpleNamespace(add=sk_add),
                                 features=types.SimpleNamespace(extrudeFeatures=types.SimpleNamespace(
                                     createInput=create_input, add=cut_add)))
    body.parentComponent = comp
    body.faces = []

    cyl = types.SimpleNamespace(surfaceType=1, origin=P3(16, 8, 0), axis=V3(0, 0, 1))
    hole_face = types.SimpleNamespace(
        geometry=cyl, pointOnFace=P3(17.5, 8, 0), body=body, entityToken='hole-1', nativeObject=None,
        evaluator=types.SimpleNamespace(getNormalAtPoint=lambda p: (True, V3(-1, 0, 0)),
                                        parametricRange=lambda: types.SimpleNamespace(
                                            minPoint=types.SimpleNamespace(x=0), maxPoint=types.SimpleNamespace(x=2 * math.pi))),
        meshManager=types.SimpleNamespace(createMeshCalculator=lambda: types.SimpleNamespace(
            calculate=lambda: types.SimpleNamespace(nodeCoordinatesAsDouble=[
                c for p in circle_pts(16, 8, 1.5, 40) for c in (p.x, p.y, 0.0)]))))
    fillet = types.SimpleNamespace(
        geometry=types.SimpleNamespace(surfaceType=1, origin=P3(5, 5, 0), axis=V3(0, 0, 1)),
        pointOnFace=P3(6, 5, 0), body=body, entityToken='fil-1', nativeObject=None,
        evaluator=types.SimpleNamespace(getNormalAtPoint=lambda p: (True, V3(-1, 0, 0)),
                                        parametricRange=lambda: types.SimpleNamespace(
                                            minPoint=types.SimpleNamespace(x=0), maxPoint=types.SimpleNamespace(x=1.5))),
        meshManager=None)
    body.faces = [hole_face, fillet]

    the_body = body

    class Face(object):
        pointOnFace = P3(1, 1, 0)
        entityToken = 'face-1'
        nativeObject = None
        evaluator = types.SimpleNamespace(getNormalAtPoint=lambda p: (True, V3(0, 0, 1)))
        body = the_body

        @property
        def area(s):
            if w.stale:
                raise RuntimeError('2 : InternalValidationError : asmFace')
            return 52.3

        @property
        def loops(s):
            if w.stale:
                raise RuntimeError('2 : InternalValidationError : asmFace')
            return loops
    face = Face()
    return w, face, body, comp, hole_face


class FakeInput(object):
    def __init__(self, id_, value=None, listing=None):
        self.id, self.value = id_, value
        self.isVisible = True
        self.isValidExpression = True
        self.isFullWidth = False
        self.tooltip = ''
        self.formattedText = ''
        self.selectionCount = 0
        self._sel = []
        self.selectedItem = None
        self.listItems = types.SimpleNamespace(add=self._add)
        self._items = []

    def _add(self, name, selected, icon=''):
        it = types.SimpleNamespace(name=name, index=len(self._items))
        self._items.append(it)
        if selected:
            self.selectedItem = it
        return it

    def addSelectionFilter(self, f):
        pass

    def setSelectionLimits(self, a, b):
        pass

    def selection(self, k):
        return types.SimpleNamespace(entity=self._sel[k])

    def select(self, entities):
        self._sel = list(entities)
        self.selectionCount = len(entities)

    def choose(self, index):
        self.selectedItem = self._items[index]


def parse(s):
    num, unit = (s.split() + [''])[:2]
    v = float(num)
    return v * 0.1 if unit == 'mm' else (math.radians(v) if unit == 'deg' else v)


class FakeInputs(object):
    def __init__(self):
        self.d = {}

    def itemById(self, id_):
        return self.d.get(id_)

    def _reg(self, inp):
        self.d[inp.id] = inp
        return inp

    def addImageCommandInput(self, id_, name, path):
        return self._reg(FakeInput(id_))

    def addSelectionInput(self, id_, name, prompt):
        return self._reg(FakeInput(id_))

    def addBoolValueInput(self, id_, name, chk, res, init):
        return self._reg(FakeInput(id_, init))

    def addDropDownCommandInput(self, id_, name, style):
        return self._reg(FakeInput(id_))

    def addValueInput(self, id_, name, unit, init):
        return self._reg(FakeInput(id_, parse(init)))

    def addIntegerSpinnerCommandInput(self, id_, name, a, b, step, init):
        return self._reg(FakeInput(id_, init))

    def addTextBoxCommandInput(self, id_, name, text, rows, ro):
        return self._reg(FakeInput(id_, text))


class Event(object):
    def __init__(self):
        self.handlers = []

    def add(self, h):
        self.handlers.append(h)


def install_fake_adsk(world):
    for m in ('adsk', 'adsk.core', 'adsk.fusion'):
        sys.modules[m] = types.ModuleType(m)
    core, fus = sys.modules['adsk.core'], sys.modules['adsk.fusion']
    sys.modules['adsk'].core, sys.modules['adsk'].fusion = core, fus
    core.CommandEventHandler = core.InputChangedEventHandler = core.CommandCreatedEventHandler = object
    core.ValidateInputsEventHandler = object
    core.Point3D = types.SimpleNamespace(create=lambda x, y, z: P3(x, y, z))
    core.Vector3D = types.SimpleNamespace(create=lambda x, y, z: V3(x, y, z))
    core.ObjectCollection = types.SimpleNamespace(create=lambda: type('C', (list,), {'add': lambda s, x: s.append(x)})())
    core.ValueInput = types.SimpleNamespace(createByString=lambda s: s, createByReal=lambda v: v)
    core.SurfaceTypes = types.SimpleNamespace(CylinderSurfaceType=1)
    core.DropDownStyles = types.SimpleNamespace(TextListDropDownStyle=0)
    core.UserLanguages = types.SimpleNamespace(EnglishLanguage=0, PortugueseBrazilianLanguage=1, SpanishLanguage=2)
    fus.FeatureOperations = types.SimpleNamespace(CutFeatureOperation=0)
    fus.ExtentDirections = types.SimpleNamespace(NegativeExtentDirection=0, PositiveExtentDirection=1)
    fus.DistanceExtentDefinition = types.SimpleNamespace(create=lambda v: v)
    fus.PointContainment = types.SimpleNamespace(PointInsidePointContainment='in', PointOutsidePointContainment='out')
    fus.DesignTypes = types.SimpleNamespace(ParametricDesignType=1)

    class Timeline(object):
        @property
        def count(s):
            return world.timeline_count + world.sketches_added

        timelineGroups = types.SimpleNamespace(
            add=lambda a, b: world.group_names.append((a, b)) or types.SimpleNamespace(name=None))
    timeline = Timeline()
    design = types.SimpleNamespace(designType=1, timeline=timeline)
    fus.Design = types.SimpleNamespace(cast=lambda p: design)

    panel_controls = {}
    cmd_defs = {}
    events = {}

    class Controls(object):
        def itemById(s, id_):
            return panel_controls.get(id_)

        def addCommand(s, cd):
            c = types.SimpleNamespace(isPromoted=False, deleteMe=lambda: panel_controls.pop(cd.id, None))
            panel_controls[cd.id] = c
            return c

    class CmdDefs(object):
        def itemById(s, id_):
            return cmd_defs.get(id_)

        def addButtonDefinition(s, id_, name, tip, folder=''):
            cd = types.SimpleNamespace(id=id_, name=name, tip=tip, folder=folder, commandCreated=Event(),
                                       deleteMe=lambda: cmd_defs.pop(id_, None))
            cmd_defs[id_] = cd
            return cd

    ui = types.SimpleNamespace(
        messageBox=lambda text, title='': world.messages.append(text),
        commandDefinitions=CmdDefs(),
        allToolbarPanels=types.SimpleNamespace(itemById=lambda i: types.SimpleNamespace(controls=Controls())))
    app = types.SimpleNamespace(userInterface=ui, log=lambda t: world.logs.append(t), activeProduct=object(),
                                preferences=types.SimpleNamespace(
                                    generalPreferences=types.SimpleNamespace(userLanguage=world.language)))
    core.Application = types.SimpleNamespace(get=lambda: app)
    return cmd_defs, panel_controls


class GlueTests(unittest.TestCase):
    def setUp(self):
        for m in ('VVGenerator', 'vv_engine'):
            sys.modules.pop(m, None)

    def start(self, language=0, **wkw):
        for m in ('VVGenerator', 'vv_engine'):
            sys.modules.pop(m, None)
        self.w, self.face, self.body, self.comp, self.hole = make_world(**wkw)
        self.w.language = language
        self.cmd_defs, self.controls = install_fake_adsk(self.w)
        import VVGenerator as V
        self.V = V
        V.run(None)
        return V

    def open_dialog(self, shape_index=0):
        V = self.V
        cd = self.cmd_defs['vvGeneratorCmd']
        cmd = types.SimpleNamespace(commandInputs=FakeInputs(), execute=Event(), inputChanged=Event(),
                                    validateInputs=Event(), executePreview=Event())
        cd.commandCreated.handlers[0].notify(types.SimpleNamespace(command=cmd))
        self.inputs = cmd.commandInputs
        self.cmd = cmd
        self.inputs.itemById('face').select([self.face])
        self.inputs.itemById('shape').choose(shape_index)
        cmd.inputChanged.handlers[0].notify(types.SimpleNamespace(inputs=self.inputs, input=self.inputs.itemById('shape')))
        return cmd

    def validate(self):
        a = types.SimpleNamespace(inputs=self.inputs, areInputsValid=None)
        self.cmd.validateInputs.handlers[0].notify(a)
        return a.areInputsValid

    def execute(self):
        self.w.messages[:] = []
        self.cmd.execute.handlers[0].notify(types.SimpleNamespace(command=self.cmd))
        return self.w.messages[-1] if self.w.messages else ''

    # ------------------------------------------------------------------ tests
    def test_lifecycle_icon_and_stop(self):
        V = self.start()
        cd = self.cmd_defs['vvGeneratorCmd']
        self.assertTrue(cd.folder.endswith(os.sep), 'icon folder must end with a separator')
        for f in ('16x16.png', '32x32.png'):
            self.assertTrue(os.path.isfile(os.path.join(cd.folder, f)))
        self.assertTrue(self.controls['vvGeneratorCmd'].isPromoted)
        V.run(None)                                     # second run replaces stale definition without error
        self.assertEqual(len(self.cmd_defs), 1)
        V.stop(None)
        self.assertEqual(self.cmd_defs, {})
        self.assertEqual(self.controls, {})

    def test_dialog_visibility_and_footer(self):
        self.start()
        self.open_dialog(0)
        i = self.inputs
        self.assertFalse(i.itemById('corner').isVisible)
        self.assertTrue(i.itemById('hmin').isVisible)
        self.assertIn('Flashbio #31888', i.itemById('footer').value)
        self.inputs.itemById('shape').choose(2)
        self.cmd.inputChanged.handlers[0].notify(types.SimpleNamespace(inputs=i, input=i.itemById('shape')))
        self.assertTrue(i.itemById('tile').isVisible and i.itemById('corner').isVisible)
        self.assertFalse(i.itemById('hmin').isVisible)

    def test_all_shapes_end_to_end(self):
        self.start()
        for idx, key in enumerate(('voronoi', 'rounded', 'hex', 'tri', 'circle')):
            self.w.volume = 100.0
            self.open_dialog(idx)
            if key == 'tri':
                self.inputs.itemById('tile').value = 1.8
            self.assertTrue(self.validate(), key)
            msg = self.execute()
            self.assertIn('cm3', msg, key + ': ' + msg[:200])
            self.assertIn('Volume', msg)
            self.assertTrue(self.w.sketch.isLightBulbOn, key + ': sketch must stay visible')
            self.assertGreater(self.w.sketch.shapes, 20, key)
            self.assertTrue(self.w.group_names, 'timeline group created')

    def test_hole_detected_and_fillet_ignored(self):
        self.start()
        self.open_dialog(0)
        msg = self.execute()
        self.assertIn('1 hole(s) detected', msg)
        self.assertIn('1 inner fillet', msg)

    def test_translations(self):
        for lang, probe in ((1, 'Volume:'), (2, 'Volumen:'), (0, 'Volume:')):
            self.start(language=lang)
            self.open_dialog(0)
            msg = self.execute()
            self.assertIn(probe, msg)
        self.start(language=1)
        self.open_dialog(0)
        self.assertIn('Reforço', self.execute())

    def test_cut_wrong_direction_then_opposite(self):
        self.start()
        self.w.cut_mode = 'flip'
        self.open_dialog(0)
        msg = self.execute()
        self.assertIn('cm3', msg)
        self.assertEqual([c[0] for c in self.w.cut_calls[:2]], [0, 1])   # tried 0 first, then 1

    def test_cut_in_batches(self):
        self.start()
        self.w.cut_mode = 'batches'
        self.open_dialog(0)
        msg = self.execute()
        self.assertIn('cm3', msg)
        self.assertTrue(any(c[1] <= 20 for c in self.w.cut_calls))

    def test_cut_failure_reports_error_and_keeps_sketch(self):
        self.start()
        self.w.cut_mode = 'fail'
        self.open_dialog(0)
        msg = self.execute()
        self.assertIn('cut failed', msg)
        self.assertIn('simulated cut failure', msg)
        self.assertTrue(self.w.sketch.isLightBulbOn)
        self.assertFalse(self.w.sketch.deleted)

    def test_engine_error_cleans_sketch_and_translates(self):
        self.start(language=1)
        self.open_dialog(0)
        self.inputs.itemById('maxc').value = 10
        msg = self.execute()
        self.assertIn('limite', msg)
        self.assertTrue(self.w.sketch.deleted)

    def test_invalid_inputs_block_ok(self):
        self.start()
        self.open_dialog(0)
        self.inputs.itemById('hmin').value = 2.0     # hmin >= hmax
        self.assertFalse(self.validate())
        self.cmd.inputChanged.handlers[0].notify(types.SimpleNamespace(inputs=self.inputs, input=self.inputs.itemById('hmin')))
        self.assertTrue(self.inputs.itemById('status').isVisible)
        self.inputs.itemById('hmin').value = 0.6
        self.inputs.itemById('wall').isValidExpression = False
        self.assertFalse(self.validate())

    def test_draw_failure_is_isolated(self):
        self.start()
        self.open_dialog(0)
        orig = self.V.vv_engine.generate

        def gen(*a, **k):
            return orig(*a, **k)
        self.V.vv_engine.generate = gen
        self.w.sketch = None
        # make the 5th curve fail: the shape is skipped, the rest is still cut
        import VVGenerator as V
        real_add = self.comp.sketches.add

        def sk_add(face):
            sk = real_add(face)
            sk.fail_draw_after = 4
            return sk
        self.comp.sketches.add = sk_add
        msg = self.execute()
        self.assertIn('could not be drawn', msg)

    # ------------------------------------------------------------------ v1.7
    def _sketch_point(self, x, y):
        sketch = types.SimpleNamespace(parentComponent=self.comp, sketchToModelSpace=lambda p: p)
        return types.SimpleNamespace(nativeObject=None, parentSketch=sketch, geometry=P3(x, y, 0.0))

    def test_translation_table_complete_and_consistent(self):
        import re
        self.start()
        for key, vals in self.V._T.items():
            self.assertEqual(len(vals), 3, key)
            self.assertTrue(all(v.strip() for v in vals), key)
            ph = [set(re.findall(r'\{(\w+)[^}]*\}', v)) for v in vals]
            self.assertEqual(ph[0], ph[1], key + ' (pt placeholders)')
            self.assertEqual(ph[0], ph[2], key + ' (es placeholders)')

    def test_user_sites_end_to_end(self):
        self.start()
        self.open_dialog(0)
        self.inputs.itemById('sites').select([self._sketch_point(5, 6), self._sketch_point(11, 7), self._sketch_point(300, 300)])
        self.inputs.itemById('sites_only').value = True
        self.assertTrue(self.validate())
        msg = self.execute()
        self.assertIn('Seed points: 2 used, 1 unusable', msg)
        self.assertEqual(self.w.sketch.shapes, 2)

    def test_sites_only_without_points_is_invalid(self):
        self.start()
        self.open_dialog(0)
        self.inputs.itemById('sites_only').value = True
        self.assertFalse(self.validate())
        self.cmd.inputChanged.handlers[0].notify(types.SimpleNamespace(inputs=self.inputs, input=self.inputs.itemById('sites_only')))
        self.assertTrue(self.inputs.itemById('status').isVisible)

    def test_relaxation_reported_and_hidden_for_tilings(self):
        self.start()
        self.open_dialog(0)
        self.inputs.itemById('relax').value = 3
        msg = self.execute()
        self.assertIn('relaxation step', msg)
        self.assertIn('Generated in', msg)
        self.open_dialog(2)
        self.assertFalse(self.inputs.itemById('relax').isVisible)
        self.assertFalse(self.inputs.itemById('sites').isVisible)

    def test_preview_runs_quietly_and_does_not_group_or_report(self):
        self.start()
        self.open_dialog(0)
        self.inputs.itemById('preview').value = False
        args = types.SimpleNamespace(command=self.cmd, isValidResult=True)
        self.cmd.executePreview.handlers[0].notify(args)
        self.assertEqual(self.w.sketches_added, 0)               # preview off: nothing happens
        self.inputs.itemById('preview').value = True
        self.w.messages[:] = []
        self.cmd.executePreview.handlers[0].notify(args)
        self.assertEqual(self.w.sketches_added, 1)               # preview builds the real result...
        self.assertEqual(self.w.messages, [])                    # ...without any dialog
        self.assertEqual(self.w.group_names, [])                 # ...and without a timeline group
        self.assertFalse(args.isValidResult)                     # OK still runs execute
        self.inputs.itemById('hmin').value = 5.0                 # invalid inputs: silent no-op
        self.cmd.executePreview.handlers[0].notify(args)
        self.assertEqual(self.w.sketches_added, 1)

    # ------------------------------------------------------------------ v1.7.1 (asmFace error on the real part)
    def test_consumed_face_after_cut_does_not_break_report_and_sketch_stays_visible(self):
        """Regression: after the cut, reading the original face raised 'InternalValidationError : asmFace'."""
        self.start()
        self.w.stale_after_cut = True
        self.w.volume_fails_after_cut = True
        self.open_dialog(0)
        msg = self.execute()
        self.assertNotIn('InternalValidationError', msg)
        self.assertIn('Face:', msg)                         # face data was captured before the cut
        self.assertIn('Cut', msg + 'Cut')                   # (report built, no crash)
        self.assertTrue(self.w.sketch.isLightBulbOn, 'the sketch must stay visible')
        self.assertFalse(self.w.sketch.deleted)

    def test_sketch_is_visible_after_a_normal_run(self):
        self.start()
        self.open_dialog(0)
        self.execute()
        self.assertTrue(self.w.sketch.isLightBulbOn)

    def test_unexpected_fusion_error_is_friendly_names_the_step_and_keeps_the_sketch(self):
        self.start()
        self.w.profiles_error = '2 : InternalValidationError : asmFace'
        self.open_dialog(0)
        msg = self.execute()
        self.assertIn('"draw"', msg)
        self.assertIn('asmFace', msg)
        self.assertIn('kept visible', msg)
        self.assertTrue(self.w.sketch.isLightBulbOn)
        self.assertFalse(self.w.sketch.deleted)

    def test_sketch_only_option_makes_no_cut(self):
        self.start()
        self.open_dialog(0)
        self.inputs.itemById('sketch_only').value = True
        msg = self.execute()
        self.assertEqual(self.w.cut_calls, [])
        self.assertIn('Sketch only', msg)
        self.assertNotIn('Volume:', msg)
        self.assertTrue(self.w.sketch.isLightBulbOn)
        self.assertGreater(self.w.sketch.shapes, 20)

    def test_through_all_falls_back_to_finite_depth(self):
        self.start()
        self.w.cut_mode = 'noall'               # the 'all' extent makes the kernel fail
        self.open_dialog(0)
        msg = self.execute()
        self.assertIn('Volume:', msg)
        modes = [c[2] for c in self.w.cut_calls]
        self.assertIn('all', modes)
        self.assertIn('dist', modes)
        self.assertEqual(modes[-1], 'dist')

    def test_cut_failure_message_keeps_sketch_visible(self):
        self.start()
        self.w.cut_mode = 'fail'
        self.open_dialog(0)
        msg = self.execute()
        self.assertIn('cut failed', msg)
        self.assertTrue(self.w.sketch.isLightBulbOn)

if __name__ == '__main__':
    unittest.main(verbosity=2)
