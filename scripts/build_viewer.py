#!/usr/bin/env python3
"""Bundle the Three.js viewer and inline the GLB into one portable HTML file."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "viewer" / "dist"
DIST.mkdir(parents=True, exist_ok=True)
esbuild = ROOT / "node_modules" / ".bin" / "esbuild"

cmd = [
    str(esbuild),
    str(ROOT / "viewer" / "src" / "main.js"),
    "--bundle",
    "--format=iife",
    "--minify",
    "--target=chrome100,safari15",
    "--loader:.glb=dataurl",
    "--loader:.jpg=dataurl",
    "--loader:.png=dataurl",
    "--log-level=warning",
    f"--outfile={DIST / 'bundle.js'}",
]
print("$", " ".join(cmd))
subprocess.run(cmd, check=True, cwd=ROOT)

css_cmd = [
    str(esbuild),
    str(ROOT / "viewer" / "src" / "style.css"),
    "--minify",
    "--target=chrome100,safari15",
    f"--outfile={DIST / 'style.min.css'}",
]
subprocess.run(css_cmd, check=True, cwd=ROOT)

js = (DIST / "bundle.js").read_text(encoding="utf-8")
css = (DIST / "style.min.css").read_text(encoding="utf-8")
js = js.replace("</script", "<\\/script")
template = (ROOT / "viewer" / "src" / "index.template.html").read_text(encoding="utf-8")
html = template.replace("__CSS__", css).replace("__JS__", js)
out1 = ROOT / "7-eleven-store-3d.html"
out2 = ROOT / "7-11便利店-3D交互.html"
out1.write_text(html, encoding="utf-8")
out2.write_text(html, encoding="utf-8")
print(f"WROTE {out1} ({len(html)/1024/1024:.2f} MiB)")
print(f"WROTE {out2}")
