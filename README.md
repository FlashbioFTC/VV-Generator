# VV Generator for Autodesk Fusion 360

Adaptive lightweight patterns for planar faces: **Voronoi** (sharp or rounded corners), **hexagons** (honeycomb),
**triangles** (triangular mesh) and **circles**. The pattern is denser around holes and chosen reinforcement faces,
drawn in a sketch and cut with an Extrude (Cut). **Lloyd relaxation** evens out the cells, you can place your own **seed points**, and there is an optional **live preview**. After each run it shows a **measured analysis** of the part and the
result (areas, wall, coverage, volume and mass removed). The dialog follows Fusion's language (English / Português-BR / Español).

> The analysis is geometric (proximity to holes / reinforcement), **not** FEA. Validate with a simulation study.

Created and maintained by **Flashbio #31888**.

## Install

| Option | Steps |
|---|---|
| **.msi** (Windows) | Download `VVGenerator-1.7.0.msi` from [Releases](../../releases), double-click. Per-user install, no admin rights. |
| **.zip** (Windows / macOS) | Download `VVGenerator-v1.7.0.zip`, unzip, run `install-windows.bat` or `install-macos.command`. |
| Manual | Copy the `VVGenerator` folder to the Fusion AddIns folder (see below). |

AddIns folder: Windows `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns` · macOS `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns`

Then in Fusion: **Utilities ▸ Add-Ins** (Shift+S) ▸ **VV Generator** ▸ **Run**. The button is in **Solid ▸ Create**.
After updating, **Stop** and **Run** the add-in again (restart Fusion once if the toolbar icon looks stale).

## Architecture

| File | Role |
|---|---|
| `VVGenerator/vv_engine.py` | Pure-Python geometry engine (no Autodesk modules): outline domain, reinforcement field, Voronoi / tiling cells, guaranteed trimming against the outline, verification and statistics. |
| `VVGenerator/VVGenerator.py` | Fusion glue: dialog, validation, translations, sketch drawing, extrude-cut with fallbacks, report. |
| `tests/test_engine.py` | Independent brute-force oracle + irregular outlines + fuzzing. |
| `tests/test_glue_mock.py` | Smoke test of the glue code against a fake Fusion API. |
| `installer/` | WiX v4 project and `build-msi.ps1`. |

**Why the pattern cannot leave the part:** every cell is cut by the supporting half-plane of a *capsule* (outline segment
buffered by the solid rim) and of each keep-out disc. Capsules and discs are convex, so the convex cell stays outside all of
them and, being connected to a seed inside the face, inside the face — also for concave or irregular outlines.

## Tests

```
python tests/test_engine.py
python tests/test_glue_mock.py
```

The tests prove the geometry and the glue logic. They cannot prove the real Fusion API behaves identically — validate on a copy of your part.

## Making a release

1. Bump `version` in `VVGenerator/VVGenerator.manifest` (and `VERSION` in `VVGenerator.py`) and commit.
2. On GitHub: **Releases ▸ Draft a new release**, create the tag (e.g. `v1.7.0`), paste `RELEASE_NOTES.md`, **Publish**.
3. The workflow runs the tests, builds `VVGenerator-<version>.msi` and `VVGenerator-v<version>.zip` and attaches them.

Local MSI build (Windows, .NET SDK 8+): `./installer/build-msi.ps1`

## License

No license has been chosen yet — add a `LICENSE` file before making the repository public.
