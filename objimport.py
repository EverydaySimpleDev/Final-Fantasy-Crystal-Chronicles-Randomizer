"""
objimport.py - Blender round-trip for FFCC models (topology-preserving).

Export a .chm to OBJ (one OBJ per mesh), edit the vertex positions / UVs /
normals in Blender, then re-import the OBJ back into the .chm. Because the model
stores vertices as int16 with a power-of-two scale (1/2^q from the QUAN tag) and
UVs as int16/4096, the int16 -> float -> int16 trip is exact, so an unedited
round-trip is byte-identical and an edit changes only the moved data.

LIMITATION: topology must be UNCHANGED - same vertex / UV / normal COUNT and
ORDER as the export (the model's faces/display-lists still reference the original
indices). So: move/scale/morph existing vertices = OK; add/remove/reorder vertices
or new meshes = NOT yet (needs a display-list writer). In Blender, import/export
OBJ with matching axis settings (Forward Z, Up Y) and DON'T let it merge/reorder
vertices ("Keep Vertex Order").

Usage:
    py objimport.py export <model.chm> [out_dir]
    py objimport.py import <model.chm> <obj_dir_or_file> [out.chm]
    py objimport.py roundtrip <model.chm>          # self-test: export+reimport == identical
"""

import os
import struct
import sys

import chmio
import dlst

I16_MIN, I16_MAX = -32768, 32767


def _quan_scale(root):
    q = struct.unpack(">I", root.find(b"QUAN").content()[:4])[0]
    return 1.0 / (2.0 ** q)


def _mesh_name(mesh_node, fallback):
    mnam = mesh_node.find(b"MNAM")
    if mnam:
        return mnam.content().split(b"\x00")[0].decode("ascii", "replace") or fallback
    return fallback


def _meshes(root):
    return root.find_all(b"MESH")


def _clamp(v, what, warns):
    if v < I16_MIN or v > I16_MAX:
        warns.append(f"{what} {v} out of int16 range; clamped")
        return max(I16_MIN, min(I16_MAX, v))
    return v


# --------------------------------------------------------------------------- #
# export  (CHM -> OBJ, one file per mesh)
# --------------------------------------------------------------------------- #
def export(chm_path, out_dir=None):
    out_dir = out_dir or os.path.splitext(chm_path)[0] + "_obj"
    os.makedirs(out_dir, exist_ok=True)
    root = chmio.root(chmio.load(chm_path))
    scale = _quan_scale(root)
    written = []
    for i, m in enumerate(_meshes(root)):
        name = _mesh_name(m, f"mesh{i}")
        vert, norm, uv = m.find(b"VERT"), m.find(b"NORM"), m.find(b"UV  ")
        lines = [f"# FFCC mesh '{name}' from {os.path.basename(chm_path)} "
                 f"(scale 1/{round(1/scale)}); keep vertex order on re-export\n",
                 f"o {name}\n"]
        if vert:
            for x, y, z in chmio.read_triples(vert):
                lines.append(f"v {x*scale:.9g} {y*scale:.9g} {z*scale:.9g}\n")
        if uv:
            for u, v in chmio.read_uvs(uv):
                lines.append(f"vt {u/4096.0:.9g} {v/4096.0:.9g}\n")
        if norm:
            for x, y, z in chmio.read_triples(norm):
                lines.append(f"vn {x*scale:.9g} {y*scale:.9g} {z*scale:.9g}\n")
        # faces (OBJ: f pos/uv/norm, 1-based) so Blender shows a real editable mesh
        dlhd = m.find(b"DLHD")
        if dlhd:
            for d in dlhd.find_all(b"DLST"):
                _, items = dlst.parse(d.content())
                for a, b, c in dlst.to_triangles(items):
                    lines.append(f"f {a[0]+1}/{a[3]+1}/{a[1]+1} "
                                 f"{b[0]+1}/{b[3]+1}/{b[1]+1} "
                                 f"{c[0]+1}/{c[3]+1}/{c[1]+1}\n")
        path = os.path.join(out_dir, f"{name}.obj")
        with open(path, "w") as f:
            f.writelines(lines)
        written.append((path, len(chmio.read_triples(vert)) if vert else 0))
    return out_dir, written


# --------------------------------------------------------------------------- #
# import  (edited OBJ -> CHM, topology preserving)
# --------------------------------------------------------------------------- #
def _parse_obj(path):
    vs, vns, vts = [], [], []
    with open(path) as f:
        for line in f:
            p = line.split()
            if not p:
                continue
            if p[0] == "v":
                vs.append(tuple(float(x) for x in p[1:4]))
            elif p[0] == "vn":
                vns.append(tuple(float(x) for x in p[1:4]))
            elif p[0] == "vt":
                vts.append(tuple(float(x) for x in p[1:3]))
    return vs, vns, vts


def import_obj(chm_path, obj_path, out_path=None):
    out_path = out_path or chm_path
    doc = chmio.load(chm_path)
    root = chmio.root(doc)
    scale = _quan_scale(root)
    meshes = _meshes(root)
    warns, changed = [], 0
    for i, m in enumerate(meshes):
        name = _mesh_name(m, f"mesh{i}")
        if os.path.isdir(obj_path):
            src = os.path.join(obj_path, f"{name}.obj")
        else:
            if len(meshes) > 1:
                raise SystemExit("multi-mesh model: pass the directory of per-mesh OBJs")
            src = obj_path
        if not os.path.isfile(src):
            warns.append(f"no OBJ for mesh {name!r} - left unchanged")
            continue
        vs, vns, vts = _parse_obj(src)
        vert, norm, uv = m.find(b"VERT"), m.find(b"NORM"), m.find(b"UV  ")
        # counts MUST match (topology preserved)
        for tag_, got, name_ in ((vert, len(vs), "vertices"), (uv, len(vts), "UVs"),
                                 (norm, len(vns), "normals")):
            if tag_ is not None and got and got != _count(tag_, name_):
                raise SystemExit(f"mesh {name}: OBJ has {got} {name_} but model has "
                                 f"{_count(tag_, name_)} - topology must be unchanged "
                                 f"(enable 'Keep Vertex Order' in Blender)")
        if vert and vs:
            chmio.write_triples(vert, [(_clamp(round(x/scale), "vx", warns),
                                        _clamp(round(y/scale), "vy", warns),
                                        _clamp(round(z/scale), "vz", warns)) for x, y, z in vs])
            changed += 1
        if norm and vns:
            chmio.write_triples(norm, [(_clamp(round(x/scale), "n", warns),
                                        _clamp(round(y/scale), "n", warns),
                                        _clamp(round(z/scale), "n", warns)) for x, y, z in vns])
        if uv and vts:
            chmio.write_uvs(uv, [(_clamp(round(u*4096), "u", warns),
                                  _clamp(round(v*4096), "v", warns)) for u, v in vts])
    chmio.save(doc, out_path)
    return changed, warns


def _count(node, kind):
    return len(chmio.read_uvs(node)) if kind == "UVs" else len(chmio.read_triples(node))


# --------------------------------------------------------------------------- #
# new-topology import (rebuilds a mesh's geometry AND faces from an OBJ)
# --------------------------------------------------------------------------- #
def _parse_obj_full(path):
    v, vn, vt, faces = [], [], [], []
    with open(path) as f:
        for line in f:
            p = line.split()
            if not p:
                continue
            if p[0] == "v":
                v.append(tuple(float(x) for x in p[1:4]))
            elif p[0] == "vn":
                vn.append(tuple(float(x) for x in p[1:4]))
            elif p[0] == "vt":
                vt.append(tuple(float(x) for x in p[1:3]))
            elif p[0] == "f":
                corners = []
                for c in p[1:]:
                    a = (c.split("/") + ["", ""])[:3]
                    corners.append((int(a[0]), int(a[1]) if a[1] else 0,
                                    int(a[2]) if a[2] else 0))
                for i in range(1, len(corners) - 1):   # fan-triangulate quads/ngons
                    faces.append((corners[0], corners[i], corners[i + 1]))
    return v, vn, vt, faces


def import_mesh(chm_path, obj_path, out_path=None, mesh_index=0, strips=False, flip=False, vscale=1.0, flat=False):
    """Rebuild ONE mesh's geometry AND topology from an OBJ (vertices, UVs,
    normals, and faces). Unlike import_obj this allows a different vertex/face
    count - it writes new VERT/NORM/UV arrays and a fresh triangle-list DLST.
    The CHM (and ISO) will change size: use `gciso.py rebuild` to inject it."""
    out_path = out_path or chm_path
    doc = chmio.load(chm_path)
    root = chmio.root(doc)
    scale = _quan_scale(root)
    m = _meshes(root)[mesh_index]
    v, vn, vt, faces = _parse_obj_full(obj_path)
    if not (v and vt and vn and faces):
        raise SystemExit("OBJ needs vertices, UVs, normals AND faces (f p/t/n) "
                         "- export with normals+UVs from Blender")
    warns = []
    chmio.write_triples(m.find(b"VERT"), [(_clamp(round(x*vscale/scale), "vx", warns),
                                           _clamp(round(y*vscale/scale), "vy", warns),
                                           _clamp(round(z*vscale/scale), "vz", warns)) for x, y, z in v])
    chmio.write_triples(m.find(b"NORM"), [(_clamp(round(x/scale), "n", warns),
                                           _clamp(round(y/scale), "n", warns),
                                           _clamp(round(z/scale), "n", warns)) for x, y, z in vn])
    chmio.write_uvs(m.find(b"UV  "), [(_clamp(round(u*4096), "u", warns),
                                       _clamp(round(w*4096), "v", warns)) for u, w in vt])
    # fresh DLST: keep the mesh's material index; OBJ corner (pos,uv,norm) 1-based
    # -> CHM vertex tuple (pos, norm, color=0, uv) 0-based
    dlhd = m.find(b"DLHD")
    old = dlhd.find(b"DLST")
    matidx = struct.unpack(">H", old.content()[:2])[0]
    def corner(c):
        return (c[0]-1, 0 if flat else ((c[2]-1) if c[2] else 0), 0,
                0 if flat else ((c[1]-1) if c[1] else 0))
    tris = [tuple(corner(c) for c in (tri if not flip else (tri[0], tri[2], tri[1])))
            for tri in faces]
    newdlst = chmio.Node(b"DLST", old.mystery)
    content = dlst.faces_to_strips(matidx, tris) if strips else dlst.faces_to_dlst(matidx, tris, 0x90)
    chmio.set_content(newdlst, content)
    dlhd.items = [newdlst]
    chmio.save(doc, out_path)
    return {"verts": len(v), "uvs": len(vt), "normals": len(vn), "tris": len(faces),
            "warns": warns}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _roundtrip(chm_path):
    import tempfile
    d = os.path.join(tempfile.gettempdir(), "objrt")
    export(chm_path, d)
    tmp = os.path.join(tempfile.gettempdir(), "objrt_out.chm")
    import_obj(chm_path, d, tmp)
    a, b = open(chm_path, "rb").read(), open(tmp, "rb").read()
    print(f"{os.path.basename(chm_path)}: export+reimport "
          f"{'BYTE-IDENTICAL' if a == b else 'DIFFERS'} ({len(a)} bytes)")
    if a != b:
        i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), -1)
        print(f"  first diff at {i}")


def main():
    if len(sys.argv) < 3:
        print(__doc__.strip()); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "export":
        out, written = export(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
        print(f"Exported {len(written)} mesh(es) to {out}:")
        for p, n in written:
            print(f"  {os.path.basename(p)}  ({n} verts)")
    elif cmd == "import":
        out = sys.argv[4] if len(sys.argv) > 4 else None
        n, warns = import_obj(sys.argv[2], sys.argv[3], out)
        print(f"Re-imported {n} mesh(es) into {out or sys.argv[2]}.")
        for w in warns:
            print("  !", w)
    elif cmd == "roundtrip":
        _roundtrip(sys.argv[2])
    elif cmd == "newmesh":
        out = sys.argv[4] if len(sys.argv) > 4 else None
        info = import_mesh(sys.argv[2], sys.argv[3], out)
        print(f"Rebuilt mesh: {info['verts']} verts, {info['uvs']} uvs, "
              f"{info['normals']} normals, {info['tris']} tris -> {out or sys.argv[2]}")
        for w in info["warns"][:10]:
            print("  !", w)
        print("Size likely changed - inject with: py gciso.py rebuild <iso> <disc_path> "
              "<new.chm> <out.iso>")
    else:
        print(__doc__.strip()); sys.exit(1)


if __name__ == "__main__":
    main()
