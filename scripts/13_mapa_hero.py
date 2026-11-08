#!/usr/bin/env python3
"""13_mapa_hero.py — Genera el mapa real del hero (SVG estático) de los 21 territorios de
Medellín a partir del límite oficial por comuna del servidor GeoMedellín (misma fuente ECV
que ya usa el proyecto). Pensado para CORRER EN GITHUB ACTIONS, no en la Raspberry Pi:
descarga el GeoJSON, proyecta lat/lon al lienzo SVG y escribe docs/mapa_comunas.svg.

- Sin dependencias pesadas (solo stdlib: urllib, json). No usa shapely/geopandas.
- El servidor ya simplifica la geometría con maxAllowableOffset → archivo liviano.
- Salida determinista (sin timestamps) para que el auto-commit no genere ruido si no cambia.
- Honesto: contorno catastral REAL por comuna, atribución Alcaldía de Medellín / MEData.

Uso: python3 scripts/13_mapa_hero.py [--salida docs/mapa_comunas.svg]
"""
import json
import sys
import urllib.request

URL = ("https://www.medellin.gov.co/servidormapas/rest/services/estadisticas/"
       "VC_Indicadores_ECV/MapServer/4/query"
       "?where=1%3D1&outFields=codigo,nombre&f=geojson"
       "&returnGeometry=true&outSR=4326&maxAllowableOffset=0.0003")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

# Territorios de mayor carga en el índice de salud (acento visual). Derivado del hallazgo del
# proyecto (La Candelaria es la comuna de mayor mortalidad); el resto son neutros.
CODIGOS_ALTA = {"10"}          # La Candelaria
CODIGOS_MEDIA = {"08", "03", "01"}  # Villa Hermosa, Manrique, Popular (zonas de atención)

W, H = 240.0, 320.0            # lienzo SVG (coincide con el viewBox del hero actual)
PAD = 14.0                     # margen interior


def descargar(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))


def anillos(geom):
    """Devuelve lista de anillos [[ (lon,lat), ... ], ...] para Polygon/MultiPolygon."""
    t = geom.get("type")
    c = geom.get("coordinates", [])
    if t == "Polygon":
        return [anillo for anillo in c]
    if t == "MultiPolygon":
        return [anillo for poly in c for anillo in poly]
    return []


def bbox(features):
    xs, ys = [], []
    for f in features:
        for ring in anillos(f["geometry"]):
            for lon, lat in ring:
                xs.append(lon); ys.append(lat)
    return min(xs), min(ys), max(xs), max(ys)


def construir_svg(data):
    feats = data.get("features", [])
    if not feats:
        raise SystemExit("GeoJSON sin features")
    minx, miny, maxx, maxy = bbox(feats)
    ancho_geo, alto_geo = (maxx - minx) or 1e-9, (maxy - miny) or 1e-9
    # Lienzo ceñido al mapa real (proporción geográfica), con un pequeño margen.
    # Escala arbitraria para tener coordenadas cómodas; el viewBox se ajusta al contenido.
    ESC = 1000.0
    ancho = ancho_geo * ESC
    alto = alto_geo * ESC
    vb_w = round(ancho + 2 * PAD, 1)
    vb_h = round(alto + 2 * PAD, 1)

    def proj(lon, lat):
        x = PAD + (lon - minx) * ESC
        y = PAD + (maxy - lat) * ESC  # invertir Y (norte arriba)
        return round(x, 1), round(y, 1)

    paths = []
    for f in sorted(feats, key=lambda z: z["properties"].get("codigo", "")):
        cod = (f["properties"].get("codigo") or "").strip()
        nombre = (f["properties"].get("nombre") or "").strip()
        clase = "terr"
        if cod in CODIGOS_ALTA:
            clase += " alta"
        elif cod in CODIGOS_MEDIA:
            clase += " media"
        d = []
        for ring in anillos(f["geometry"]):
            if len(ring) < 3:
                continue
            pts = [proj(lon, lat) for lon, lat in ring]
            d.append("M" + " L".join(f"{x},{y}" for x, y in pts) + " Z")
        if d:
            titulo = f"{nombre}".strip() or cod
            paths.append(f'<path class="{clase}" d="{" ".join(d)}"><title>{titulo}</title></path>')

    svg = []
    svg.append(f'<svg viewBox="0 0 {vb_w} {vb_h}" role="img" '
               f'aria-label="Mapa de los 21 territorios de Medellín (contorno real por comuna)">')
    svg.append('<g class="terr-grupo">')
    svg.extend("  " + p for p in paths)
    svg.append('</g>')
    svg.append('</svg>')
    return "\n".join(svg) + "\n"


def main():
    salida = "docs/mapa_comunas.svg"
    if "--salida" in sys.argv:
        salida = sys.argv[sys.argv.index("--salida") + 1]
    print(f"[13] Descargando límite de comunas desde GeoMedellín…", flush=True)
    data = descargar(URL)
    n = len(data.get("features", []))
    print(f"[13] {n} territorios recibidos. Generando SVG…", flush=True)
    if n < 16:
        raise SystemExit(f"Se esperaban >=16 territorios, llegaron {n}")
    svg = construir_svg(data)
    with open(salida, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"[13] OK → {salida} ({len(svg)} bytes)", flush=True)


if __name__ == "__main__":
    main()
