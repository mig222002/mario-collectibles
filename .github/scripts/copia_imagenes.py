"""Copia de seguridad de las imágenes de Mario Collectibles.

Lee la hoja publicada (CSV), descarga cada imagen de la columna «imagen» que aún no esté copiada,
guarda dos versiones en WebP (nunca más grandes que el original):
  img/s/<huella>.webp  → 640 px, para tarjetas y miniaturas
  img/l/<huella>.webp  → hasta 1600 px, para la ficha y el zoom
Escribe imagenes.json, que la web usa para mostrar la copia en lugar del enlace original. Las imágenes que ya no están en la hoja se borran.
"""
import csv, io, json, os, sys, datetime
from concurrent.futures import ThreadPoolExecutor
import requests
from PIL import Image

CSV_URL = ("https://docs.google.com/spreadsheets/d/e/2PACX-1vSj2KYGDyaw6T7TKaZ6NG2hSFeqmsfk3Ok2yy434gSU5ofQ1t7wAN9RHtQmJBSe_gwyC-AHx1OyzguR"
           "/pub?gid=435068621&single=true&output=csv")
OUT_DIR = "img"
MANIFEST = "imagenes.json"
TAMANOS = {"s": (640, 82), "l": (1600, 86)}   # carpeta: (lado máximo, calidad)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://mig222002.github.io/",
}


def huella(url: str) -> str:
    """FNV-1a de 32 bits sobre unidades UTF-16, en base 36 (igual que mirHash en la web)."""
    h = 2166136261
    data = url.encode("utf-16-le")
    for i in range(0, len(data), 2):
        h ^= data[i] | (data[i + 1] << 8)
        h = (h * 16777619) & 0xFFFFFFFF
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while True:
        h, r = divmod(h, 36)
        out = digits[r] + out
        if h == 0:
            return out


def leer_hoja():
    r = requests.get(CSV_URL, timeout=60)
    r.raise_for_status()
    r.encoding = "utf-8"
    filas = list(csv.reader(io.StringIO(r.text)))
    cab = [c.strip().lower() for c in filas[0]]
    i_img, i_nom = cab.index("imagen"), (cab.index("nombre") if "nombre" in cab else None)
    piezas = {}
    for f in filas[1:]:
        if len(f) <= i_img:
            continue
        url = f[i_img].strip()
        if url.startswith("http"):
            piezas.setdefault(url, f[i_nom].strip() if i_nom is not None and len(f) > i_nom else "")
    return piezas


def copiar(url: str):
    """Devuelve (url, ruta o None, error)."""
    h = huella(url)
    rutas = {k: f"{OUT_DIR}/{k}/{h}.webp" for k in TAMANOS}
    if all(os.path.exists(r) for r in rutas.values()):
        return url, h, None
    ultimo = ""
    for intento in range(2):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code != 200 or len(r.content) < 500:
                ultimo = f"HTTP {r.status_code}"
                continue
            im = Image.open(io.BytesIO(r.content))
            im.load()
            im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
            for k, (lado, calidad) in TAMANOS.items():
                copia = im.copy()
                copia.thumbnail((lado, lado), Image.LANCZOS)   # solo reduce, nunca amplía
                copia.save(rutas[k], "WEBP", quality=calidad, method=6)
            return url, h, None
        except Exception as e:  # noqa: BLE001 - registramos cualquier fallo de red o de imagen
            ultimo = type(e).__name__
    return url, None, ultimo or "error"


def main():
    for k in TAMANOS:
        os.makedirs(f"{OUT_DIR}/{k}", exist_ok=True)
    piezas = leer_hoja()
    print(f"{len(piezas)} imágenes en la hoja")
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(copiar, piezas))
    items, fallos = {}, []
    for url, h, err in res:
        if h:
            items[h] = 1
        else:
            fallos.append({"nombre": piezas[url], "url": url, "error": err})
    usados = {f"{h}.webp" for h in items}
    total = 0
    for k in TAMANOS:
        carpeta = f"{OUT_DIR}/{k}"
        for f in os.listdir(carpeta):
            if f not in usados:
                os.remove(os.path.join(carpeta, f))
            else:
                total += os.path.getsize(os.path.join(carpeta, f))
    hoy = datetime.date.today().isoformat()
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump({"v": 3, "dir": OUT_DIR, "made": hoy, "items": items, "fails": fallos}, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"Copiadas: {len(items)} · fallidas: {len(fallos)} · {total / 1048576:.1f} MB")
    for f in fallos:
        print("  ✗", f["nombre"], f["url"], f["error"])


if __name__ == "__main__":
    sys.exit(main())
