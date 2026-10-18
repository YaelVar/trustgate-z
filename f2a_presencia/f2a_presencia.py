"""F2a - Presencia de rostro (TrustGate Z).

Modelo de DOS CLASES (por defecto, --modelo lr): regresion logistica sobre PCA (100 componentes) de HOG
en gris, rostros frente a texturas. Las texturas (ambientCG, CC0) SI entrenan el modelo como clase negativa
(grupo de entrenamiento de texturas); otros dos grupos de texturas, sin familias en comun con el anterior
ni entre si, fijan el umbral y miden falsos positivos.

Flujo:
  1. Rasgos: imagen -> recorte central cuadrado -> 128x128 -> gris -> HOG (sin color, para reducir el atajo
     "las texturas se distinguen por color").
  2. Entrenamiento: rostros reales de CelebA-Spoof (Data/train/*/live, sin las discordantes) y de Real vs Fake
     Faces (partes 'real' de train), mas el grupo de entrenamiento de texturas (933, 47 familias). Nunca se
     usan imagenes de prueba.
  3. Umbral: el score que deja como maximo 5 % de falsos positivos en el grupo de umbral de texturas
     (542, 24 familias).
  4. Prueba: FP en el grupo de prueba de texturas (427, 24 familias); FN en rostros reservados (CelebA-Spoof
     Data/test/*/live y Real vs Fake test/real). Con intervalos de Wilson al 95 %.
  Las texturas se dividen por FAMILIA (Asphalt, Bricks, ...), no solo por archivo, en los tres grupos sin
  familias en comun: hay variantes casi identicas (Asphalt024A/B/C) que contaminarian la prueba si quedaran
  en grupos distintos.

Filtro de rostros en las texturas (independiente de este modelo): --filtrar usa el cascade LBP frontal que trae
scikit-image. Es un detector ajeno a F2a, para no quitar justo las texturas que F2a confundiria con rostros.

Uso (en la VM, desde ~/trustgate-data/src con la rama de F2a):
  python f2a_presencia.py --texturas ../datos/ambientcg-color --filtrar --out f2a_out
  python f2a_presencia.py --texturas ../datos/ambientcg-color --descartados f2a_out/descartados_cascade.txt --out f2a_out
Rutas por defecto: ../datos/subconjunto/CelebA_Spoof, ../datos/real-vs-fake/"Real vs Fake Faces",
../datos/discordantes_train.txt. Cambiarlas con --celeba, --rvf, --discordantes.

Escribe <out>/f2a_resultados.md (sin imagenes ni rutas de rostros) y <out>/f2a_model.joblib (PESOS: no subir a Git).
"""
import argparse
import io
import os
import re
import time

import numpy as np
import pandas as pd
from joblib import Parallel, delayed, dump
from PIL import Image
from skimage import data as skdata
from skimage.color import rgb2gray
from skimage.feature import Cascade, hog
from sklearn.decomposition import PCA
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM
from sklearn.linear_model import LogisticRegression
import lightgbm as lgb

SIZE = 128
EXT = (".jpg", ".jpeg", ".png")
TARGET_FP = 0.05
SEED = 42
Z = 1.96
_DET = None


# ---------- utilidades ----------
def wilson(k, n, z=Z):
    if n == 0:
        return np.nan, np.nan
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def tasa(k, n):
    if n == 0:
        return "n/d"
    lo, hi = wilson(k, n)
    return f"{100 * k / n:.2f} % ({k}/{n}; IC 95 % {100 * lo:.2f}-{100 * hi:.2f})"


def md(df):
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    out += ["| " + " | ".join(str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(out)


def listar(raiz):
    out = []
    for dp, dn, fn in os.walk(raiz):
        dn[:] = [d for d in dn if not d.startswith(".")]      # ignora .ipynb_checkpoints
        out += [os.path.join(dp, f) for f in fn if f.lower().endswith(EXT)]
    return sorted(out)


def caja_bb(path, W, H, bbcfg):
    """Caja cuadrada alrededor del rostro, a partir de <imagen>_BB.txt (formato CelebA-Spoof: x y w h score).
    bbcfg = (usar, base, margen). Si base > 0 las coordenadas estan sobre una imagen de base x base y se
    reescalan a W x H; si base = 0 son pixeles reales. Devuelve None si no hay caja valida."""
    usar, base, margen = bbcfg
    if not usar:
        return None
    f = os.path.splitext(path)[0] + "_BB.txt"
    if not os.path.exists(f):
        return None
    try:
        with open(f) as fh:
            x, y, w, h = [float(v) for v in fh.read().split()[:4]]
    except Exception:
        return None
    if base:
        x, w, y, h = x * W / base, w * W / base, y * H / base, h * H / base
    if w <= 1 or h <= 1:
        return None
    cx, cy = x + w / 2, y + h / 2
    lado = min(max(w, h) * margen, W, H)
    x0 = min(max(cx - lado / 2, 0), W - lado)
    y0 = min(max(cy - lado / 2, 0), H - lado)
    return (int(x0), int(y0), int(x0 + lado), int(y0 + lado))


def cargar(path, size=SIZE, calidad=0, bbcfg=(False, 224, 1.6)):
    """Recorte cuadrado y reescalado: alrededor del rostro si hay caja _BB.txt; si no, recorte central.
    Opcional: recodificar a JPEG con una calidad dada."""
    im = Image.open(path)
    W, H = im.size
    caja = caja_bb(path, W, H, bbcfg)
    if caja is None:
        im.draft("RGB", (size * 2, size * 2))      # acelera la decodificacion de JPEG grandes
    im = im.convert("RGB")
    if caja is None:
        w, h = im.size
        s = min(w, h)
        x0, y0 = (w - s) // 2, (h - s) // 2
        caja = (x0, y0, x0 + s, y0 + s)
    im = im.crop(caja).resize((size, size), Image.BILINEAR)
    if calidad:
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=calidad)
        buf.seek(0)
        im = Image.open(buf).convert("RGB")
    return np.asarray(im)


def rasgos(path, calidad=0, bbcfg=(False, 224, 1.6)):
    try:
        g = rgb2gray(cargar(path, calidad=calidad, bbcfg=bbcfg))
        return hog(g, orientations=9, pixels_per_cell=(16, 16), cells_per_block=(2, 2),
                   block_norm="L2-Hys", feature_vector=True).astype(np.float32)
    except Exception:
        return None


def extraer(paths, jobs, calidad=0, bbcfg=(False, 224, 1.6)):
    r = Parallel(n_jobs=jobs)(delayed(rasgos)(p, calidad, bbcfg) for p in paths)
    ok = [i for i, v in enumerate(r) if v is not None]
    return (np.vstack([r[i] for i in ok]) if ok else np.zeros((0, 1764), np.float32)), [paths[i] for i in ok], len(paths) - len(ok)


def tiene_rostro(path):
    """Detector independiente de F2a: cascade LBP frontal de scikit-image, sobre la imagen a 256x256."""
    global _DET
    if _DET is None:
        _DET = Cascade(skdata.lbp_frontal_face_cascade_filename())
    g = (rgb2gray(cargar(path, size=256)) * 255).astype(np.uint8)
    d = _DET.detect_multi_scale(img=g, scale_factor=1.2, step_ratio=1, min_size=(24, 24),
                                max_size=(256, 256), min_neighbor_number=4)
    return len(d) > 0


def familia(path):
    m = re.match(r"[A-Za-z]+", os.path.basename(path))
    return m.group(0) if m else "otros"


def muestrear(lista, n, rng):
    if n and len(lista) > n:
        return [lista[i] for i in sorted(rng.choice(len(lista), n, replace=False))]
    return lista


# ---------- descubrimiento de rostros ----------
def rostros_celeba(raiz, discordantes):
    """Data/<train|test>/<sujeto>/<live|spoof>/<archivo>. Devuelve dict (split, clase) -> rutas."""
    excl = set()
    if discordantes and os.path.exists(discordantes):
        with open(discordantes, encoding="utf-8-sig") as f:      # la primera linea trae BOM
            excl = {ln.strip().replace("\\", "/") for ln in f if ln.strip()}
    out, n_excl = {}, 0
    for p in listar(os.path.join(raiz, "Data")):
        rel = os.path.relpath(p, raiz).replace("\\", "/")
        partes = rel.split("/")
        if len(partes) < 5:
            continue
        if rel in excl:
            n_excl += 1
            continue
        out.setdefault((partes[1], partes[3].lower()), []).append(p)
    return out, n_excl, len(excl)


def rostros_rvf(raiz):
    """<...>/8020/<train|valid|test>/<real|fake>/<archivo>. Solo se devuelve el lado real."""
    out = {}
    for p in listar(raiz):
        partes = os.path.relpath(p, raiz).replace("\\", "/").split("/")
        if len(partes) < 4:
            continue
        split, clase = partes[-3].lower(), partes[-2].lower()
        if "real" in clase:
            out.setdefault(split, []).append(p)
    return out


class LGBMScore:
    """Envoltorio para que LightGBM tenga decision_function (mayor = mas rostro)."""
    def __init__(self, **kw):
        self.m = lgb.LGBMClassifier(**kw)
    def fit(self, X, y):
        self.m.fit(X, y); return self
    def decision_function(self, X):
        return self.m.predict_proba(X)[:, 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--celeba", default="../datos/subconjunto/CelebA_Spoof")
    ap.add_argument("--rvf", default="../datos/real-vs-fake/Real vs Fake Faces")
    ap.add_argument("--discordantes", default="../datos/discordantes_train.txt")
    ap.add_argument("--texturas", required=True)
    ap.add_argument("--descartados", help="archivo con nombres de textura a excluir (una por linea)")
    ap.add_argument("--filtrar", action="store_true", help="descarta texturas con rostro segun el cascade independiente")
    ap.add_argument("--max-train", type=int, default=4000, help="rostros de entrenamiento por fuente")
    ap.add_argument("--max-test", type=int, default=2000, help="rostros de prueba por fuente")
    ap.add_argument("--incluir-spoof", action="store_true", help="tambien mide cuantos spoof de CelebA-Spoof se aceptan como rostro")
    ap.add_argument("--modelo", choices=["lr", "lgbm", "ocsvm"], default="lr",
                    help="lr = regresion logistica rostros vs texturas (por defecto); lgbm; ocsvm = clase unica (resultado negativo, ver docs)")
    ap.add_argument("--nu", type=float, default=0.05)
    ap.add_argument("--componentes", type=int, default=100)
    ap.add_argument("--calidad-jpeg", type=int, default=0, help="recodifica a JPEG con esta calidad (0 = no)")
    ap.add_argument("--sin-bb", action="store_true", help="no usar las cajas _BB.txt: recorte central")
    ap.add_argument("--bb-base", type=int, default=224, help="base de las coordenadas de _BB.txt (224 = sobre imagen 224x224; 0 = pixeles reales)")
    ap.add_argument("--margen-bb", type=float, default=1.6, help="lado del recorte = margen x lado mayor de la caja")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--guardar-rasgos", action="store_true", help="guarda los rasgos en <out>/f2a_rasgos.npz (para f2a_diag.py)")
    ap.add_argument("--out", default="f2a_out")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(SEED)
    t0 = time.time()

    # ---- texturas ----
    tex = listar(a.texturas)
    n_total = len(tex)
    descartar = set()
    if a.descartados and os.path.exists(a.descartados):
        with open(a.descartados, encoding="utf-8-sig") as f:
            descartar |= {os.path.basename(ln.strip()) for ln in f if ln.strip()}
    if a.filtrar:
        print(f"Filtrando {len(tex)} texturas con el cascade independiente...")
        flags = Parallel(n_jobs=a.jobs)(delayed(tiene_rostro)(p) for p in tex)
        con_rostro = [os.path.basename(p) for p, fl in zip(tex, flags) if fl]
        with open(os.path.join(a.out, "descartados_cascade.txt"), "w") as f:
            f.write("\n".join(con_rostro))
        print(f"  con rostro segun el cascade: {len(con_rostro)} (lista en descartados_cascade.txt)")
        descartar |= set(con_rostro)
    tex = [p for p in tex if os.path.basename(p) not in descartar]
    fam = np.array([familia(p) for p in tex])
    print(f"Texturas: {n_total} en total, {n_total - len(tex)} descartadas, {len(tex)} usadas, {len(set(fam))} familias")
    # tres grupos sin familias en comun: entrenamiento (negativos), umbral y prueba
    i_neg, i_rest = next(GroupShuffleSplit(n_splits=1, test_size=0.5, random_state=SEED).split(tex, groups=fam))
    iu_, ip_ = next(GroupShuffleSplit(n_splits=1, test_size=0.5, random_state=SEED).split(i_rest, groups=fam[i_rest]))
    ui, pi = i_rest[iu_], i_rest[ip_]
    tex_neg, tex_umbral, tex_prueba = [tex[i] for i in i_neg], [tex[i] for i in ui], [tex[i] for i in pi]
    assert not (set(fam[i_neg]) & set(fam[ui])) and not (set(fam[i_neg]) & set(fam[pi])) and not (set(fam[ui]) & set(fam[pi])), \
        "una familia quedo en mas de un grupo"

    # ---- rostros ----
    cel, n_excl, n_lista = rostros_celeba(a.celeba, a.discordantes)
    rvf = rostros_rvf(a.rvf)
    print("CelebA-Spoof:", {k: len(v) for k, v in cel.items()}, f"| discordantes excluidas: {n_excl} de {n_lista}")
    print("Real vs Fake (lado real):", {k: len(v) for k, v in rvf.items()})
    tr_cel = muestrear(cel.get(("train", "live"), []), a.max_train, rng)
    tr_rvf = muestrear(rvf.get("train", []), a.max_train, rng)
    te_cel = muestrear(cel.get(("test", "live"), []), a.max_test, rng)
    te_rvf = muestrear(rvf.get("test", []), a.max_test, rng)
    te_spoof = muestrear(cel.get(("test", "spoof"), []), a.max_test, rng) if a.incluir_spoof else []
    if not tr_cel and not tr_rvf:
        raise SystemExit("No encontre rostros de entrenamiento. Revisa --celeba y --rvf.")

    # ---- rasgos ----
    print("Extrayendo rasgos...")
    bbcfg = (not a.sin_bb, a.bb_base, a.margen_bb)
    n_bb = sum(os.path.exists(os.path.splitext(p)[0] + "_BB.txt") for p in tr_cel + te_cel + te_spoof) if bbcfg[0] else 0
    print(f"  recortes con caja de rostro (CelebA-Spoof): {n_bb} de {len(tr_cel) + len(te_cel) + len(te_spoof)}")
    X_tr, p_tr, f1 = extraer(tr_cel + tr_rvf, a.jobs, a.calidad_jpeg, bbcfg)
    X_ub, _, f2 = extraer(tex_umbral, a.jobs, a.calidad_jpeg)
    X_ng, _, f2b = extraer(tex_neg, a.jobs, a.calidad_jpeg) if a.modelo != "ocsvm" else (np.zeros((0, X_tr.shape[1])), [], 0)
    X_tp, p_tp, f3 = extraer(tex_prueba, a.jobs, a.calidad_jpeg)
    X_fc, _, f4 = extraer(te_cel, a.jobs, a.calidad_jpeg, bbcfg)
    X_fr, _, f5 = extraer(te_rvf, a.jobs, a.calidad_jpeg, bbcfg)
    X_sp, _, f6 = extraer(te_spoof, a.jobs, a.calidad_jpeg, bbcfg) if te_spoof else (np.zeros((0, X_tr.shape[1])), [], 0)
    if a.guardar_rasgos:
        np.savez_compressed(os.path.join(a.out, "f2a_rasgos.npz"), X_tr=X_tr, X_ub=X_ub, X_tp=X_tp, X_fc=X_fc, X_fr=X_fr, X_sp=X_sp,
                            n_tr_cel=len(tr_cel), p_tp=np.array(p_tp))
    print(f"  listo en {time.time() - t0:.0f} s; imagenes ilegibles: {f1 + f2 + f2b + f3 + f4 + f5 + f6}")

    # ---- modelo y umbral ----
    if a.modelo == "ocsvm":
        modelo = make_pipeline(StandardScaler(), PCA(n_components=min(a.componentes, len(X_tr) - 1), random_state=SEED),
                               OneClassSVM(kernel="rbf", gamma="scale", nu=a.nu))
        modelo.fit(X_tr)
    else:
        X_all, y_all = np.vstack([X_tr, X_ng]), np.r_[np.ones(len(X_tr)), np.zeros(len(X_ng))]
        if a.modelo == "lr":
            modelo = make_pipeline(StandardScaler(), PCA(n_components=min(a.componentes, len(X_all) - 1), random_state=SEED),
                                   LogisticRegression(C=0.1, max_iter=2000, class_weight="balanced"))
        else:
            modelo = LGBMScore(n_estimators=300, learning_rate=0.05, num_leaves=31, subsample=0.8, subsample_freq=1,
                               colsample_bytree=0.5, class_weight="balanced", random_state=SEED, verbose=-1)
        modelo.fit(X_all, y_all)
    s_ub = modelo.decision_function(X_ub)
    thr = float(np.quantile(s_ub, 1 - TARGET_FP, method="higher"))     # acepta si score > thr
    fp_ub = int((s_ub > thr).sum())
    dump(modelo, os.path.join(a.out, "f2a_model.joblib"))

    s_tp = modelo.decision_function(X_tp)
    fp = int((s_tp > thr).sum())
    res = {}
    for nombre, X in (("CelebA-Spoof live (prueba)", X_fc), ("Real vs Fake, real (prueba)", X_fr)):
        if len(X):
            s = modelo.decision_function(X)
            res[nombre] = (int((s <= thr).sum()), len(s))
    if len(res):
        res["Todos los rostros de prueba"] = (sum(v[0] for v in res.values()), sum(v[1] for v in res.values()))
    fams = pd.DataFrame({"familia": [familia(p) for p in p_tp], "fp": (s_tp > thr).astype(int)})
    top = (fams.groupby("familia")["fp"].agg(["sum", "size"]).sort_values(["sum", "size"], ascending=False).head(10)
           .reset_index().rename(columns={"sum": "FP", "size": "texturas"}))

    desc = {"ocsvm": "Clase unica (OneClassSVM): modelo ajustado solo con rostros. Las texturas fijan el umbral y miden falsos positivos; no entrenan.",
            "lr": "Dos clases (regresion logistica, PCA 100): rostros frente a texturas. Tres grupos de texturas sin familias en comun: "
                  "entrenamiento (negativos), umbral y prueba.",
            "lgbm": "Dos clases (LightGBM): rostros frente a texturas. Tres grupos de texturas sin familias en comun: entrenamiento, umbral y prueba."}[a.modelo]
    o = ["# F2a - Presencia de rostro", "", desc, "",
         "## Datos", "",
         f"- Entrenamiento: {len(p_tr)} rostros (CelebA-Spoof live: {len(tr_cel)}, Real vs Fake real: {len(tr_rvf)}). "
         f"Discordantes excluidas: {n_excl} de {n_lista} en la lista.",
         f"- Texturas: {n_total} en total, {n_total - len(tex)} descartadas por rostro o por lista, {len(tex)} usadas, "
         f"{len(set(fam))} familias. Grupo de entrenamiento: {len(tex_neg)} ({len(set(fam[i_neg]))} familias); "
         f"grupo de umbral: {len(tex_umbral)} ({len(set(fam[ui]))} familias); "
         f"grupo de prueba: {len(tex_prueba)} ({len(set(fam[pi]))} familias). Ninguna familia esta en mas de un grupo.",
         f"- Rostros de prueba: CelebA-Spoof live {len(X_fc)}, Real vs Fake real {len(X_fr)}.",
         f"- Recorte: " + ("alrededor de la caja de rostro de CelebA-Spoof (_BB.txt, base " + str(a.bb_base) + f", margen {a.margen_bb}); "
                           f"{n_bb} de {len(tr_cel) + len(te_cel) + len(te_spoof)} imagenes de CelebA-Spoof con caja. "
                           if bbcfg[0] else "recorte central cuadrado. ")
         + "Real vs Fake y texturas: recorte central cuadrado.", "",
         "## Umbral", "",
         f"Score del modelo (mayor = mas parecido a un rostro). Umbral = {thr:.4f}, fijado para que como maximo "
         f"{100 * TARGET_FP:.0f} % de las texturas del grupo de umbral se acepten como rostro: "
         f"{fp_ub} de {len(s_ub)} ({100 * fp_ub / max(len(s_ub), 1):.2f} %).", "",
         "## Resultados en prueba", "",
         f"- **Falsos positivos en texturas** (textura aceptada como rostro): {tasa(fp, len(s_tp))}"]
    for k, (fn, n) in res.items():
        o.append(f"- **Falsos negativos, {k}** (rostro no aceptado): {tasa(fn, n)}")
    if len(X_sp):
        acept = int((modelo.decision_function(X_sp) > thr).sum())
        o.append(f"- Spoof de CelebA-Spoof aceptados como rostro (presencia, no vida): {tasa(acept, len(X_sp))}")
    o += ["", "### Familias de textura con mas falsos positivos (prueba)", "", md(top), "",
          "## Limites", "",
          "- Las texturas no son objetos, escenas ni personas: F2a no garantiza el rechazo de fotos de objetos reales.",
          *(["- Con dos clases el modelo aprende rostros frente a texturas; no demuestra presencia de rostro frente a cualquier otra imagen. "
             "Los falsos positivos se miden solo en familias de textura no vistas.",
             "- Resultado negativo previo: el modelo de clase unica (OneClassSVM, tambien distancia de Mahalanobis, error de reconstruccion y "
             "kNN sobre HOG) no separo rostros de texturas (AUC maximo 0,82; mas del 60 % de rostros rechazados al fijar 5 % de falsos positivos)."]
            if a.modelo != "ocsvm" else []),
          "- El modelo podria separar texturas de rostros por encuadre, fondo o nitidez y no por la presencia de un rostro; "
          "por eso los rasgos son HOG en gris, sin color.",
          "- Las texturas se filtran con un detector independiente (cascade LBP), no con este modelo.",
          "- Licencias: rostros de uso no comercial (CelebA-Spoof, FFHQ); texturas CC0 1.0. Los pesos no se publican.", ""]
    ruta = os.path.join(a.out, "f2a_resultados.md")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(o))
    print("\n".join(o))
    print(f"Escrito: {ruta} | {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
