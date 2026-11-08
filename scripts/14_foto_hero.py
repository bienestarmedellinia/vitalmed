#!/usr/bin/env python3
"""14_foto_hero.py — Descarga la foto panorámica de Medellín para el fondo del banner.

Pensado para CORRER EN GITHUB ACTIONS (igual que el resto del pipeline), aunque es tan
liviano que también funciona en la Raspberry Pi: NO procesa imágenes (no requiere Pillow).
Wikimedia Commons sirve miniaturas ya redimensionadas por la API (iiurlwidth), así que solo
se descarga el JPEG del ancho pedido (~1280 px, ~220 KB) y se guarda en docs/.

Imagen: "Panorámica de Medellín desde el Cerro El Picacho" — autor Luis90f — CC BY-SA 4.0.
La atribución es OBLIGATORIA (BY-SA): se declara en docs/index.html (Transparencia).

Uso: python3 scripts/14_foto_hero.py [--ancho 1280] [--salida docs/hero_medellin.jpg]
"""
import json
import sys
import urllib.parse
import urllib.request

TITULO = "File:Panorámica de Medellín desde el Cerro El Picacho.jpg"
API = "https://commons.wikimedia.org/w/api.php"
UA = "Mozilla/5.0 (bienestar-medellin-datos; proyecto hackathon ITM)"


def thumb_url(titulo, ancho):
    params = {
        "action": "query", "titles": titulo, "prop": "imageinfo",
        "iiprop": "url|extmetadata", "iiurlwidth": str(ancho), "format": "json",
    }
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode("utf-8"))
    pg = list(d["query"]["pages"].values())[0]
    ii = pg["imageinfo"][0]
    em = ii.get("extmetadata", {})
    return ii["thumburl"], em.get("LicenseShortName", {}).get("value", ""), em.get("Artist", {}).get("value", "")


def main():
    ancho = 1280
    salida = "docs/hero_medellin.jpg"
    if "--ancho" in sys.argv:
        ancho = int(sys.argv[sys.argv.index("--ancho") + 1])
    if "--salida" in sys.argv:
        salida = sys.argv[sys.argv.index("--salida") + 1]

    print(f"[14] Resolviendo miniatura {ancho}px de la panorámica de Medellín…", flush=True)
    url, lic, autor = thumb_url(TITULO, ancho)
    print(f"[14] Licencia: {lic} · fuente: Wikimedia Commons", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = r.read()
    if len(data) < 10000 or data[:2] != b"\xff\xd8":
        raise SystemExit(f"Descarga no parece un JPEG válido ({len(data)} bytes)")
    with open(salida, "wb") as fh:
        fh.write(data)
    print(f"[14] OK → {salida} ({len(data)} bytes)", flush=True)


if __name__ == "__main__":
    main()
