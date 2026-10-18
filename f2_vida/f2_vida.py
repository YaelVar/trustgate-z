"""F2 - Vida (liveness) sobre CelebA-Spoof. TrustGate Z.

Entrada : imagen de un rostro (recorte alrededor de la caja _BB.txt).
Salida  : score en [0, 1]; mayor = mas probable que sea un ATAQUE (foto, pantalla, mascara...).
Modelo  : rasgos clasicos (color en YCrCb/HSV, textura LBP, espectro de frecuencias, nitidez, reflejos, borde)
          + LightGBM. Sin redes preentrenadas (no hay descarga de pesos en la VM).

Datos   : subconjunto de 3.000 imagenes de CelebA-Spoof (metadatos_subconjunto.csv). La particion train/test ya viene
          separada POR PERSONA; la validacion se separa del entrenamiento tambien por persona.
Umbral  : se fija SOLO en validacion (igualdad APCER = BPCER). Se rechaza si score >= umbral.
Metricas: ISO/IEC 30107-3. APCER = ataques aceptados / ataques; BPCER = reales rechazados / reales.
          Media +- desviacion de 5 semillas (42-46); la semilla 42 produce los archivos de salida.

Uso:
  python f2_vida.py --celeba ../datos/subconjunto/CelebA_Spoof --meta ../datos/subconjunto/metadatos_subconjunto.csv \
         --discordantes ../datos/discordantes_train.txt --jobs 2 --out f2_out [--guardar-rasgos]
  (con --rasgos f2_out/f2_rasgos.npz se saltan la extraccion y se reutilizan los rasgos guardados)

Escribe <out>/f2_resultados.md, <out>/f2_predicciones.csv (contrato de f3_equidad.py, sin rutas) y
<out>/f2_model.joblib (PESOS: no subir a Git).
"""
import argparse
import io
import os
import time
import warnings

import numpy as np
import pandas as pd
from joblib import Parallel, delayed, dump
from PIL import Image
from scipy import ndimage as ndi
from skimage.color import rgb2hsv
from skimage.feature import local_binary_pattern
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
import lightgbm as lgb

warnings.filterwarnings("ignore", message=".*eval_set.*")
MODEL_VERSION = "f2-lgbm-0.1"
SIZE = 128
SEEDS = [42, 43, 44, 45, 46]
Z = 1.96
MIN_N = 60          # minimo de muestras por grupo para marcarlo como confiable (igual que f3_equidad.py)
# Codigos de CelebA-Spoof segun su documentacion (verificar contra la ficha del dataset)
TIPO = {0: "live", 1: "Photo", 2: "Poster", 3: "A4", 4: "Face Mask", 5: "Upper Body Mask", 6: "Region Mask",
        7: "PC", 8: "Pad", 9: "Phone", 10: "3D Mask"}
ILUM = {1: "Normal", 2: "Strong", 3: "Back", 4: "Dark"}
ENTORNO = {1: "Indoor", 2: "Outdoor"}


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


# ---------- recorte ----------
def caja_bb(path, W, H, base=224, margen=1.6):
    """Caja cuadrada alrededor del rostro desde <imagen>_BB.txt (x y w h score; coordenadas sobre base x base)."""
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


def cargar(path, margen, size=SIZE, calidad=0):
    im = Image.open(path)
    W, H = im.size
    caja = caja_bb(path, W, H, 224, margen)
    im = im.convert("RGB")
    if caja is None:
        s = min(W, H)
        x0, y0 = (W - s) // 2, (H - s) // 2
        caja = (x0, y0, x0 + s, y0 + s)
    im = im.crop(caja).resize((size, size), Image.LANCZOS)
    if calidad:                                  # recompresion JPEG igual para todas las imagenes (iguala el procesamiento)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=calidad)
        buf.seek(0)
        im = Image.open(buf).convert("RGB")
    return np.asarray(im), W, H


# ---------- rasgos ----------
def _hist(a, bins, rango):
    h, _ = np.histogram(a, bins=bins, range=rango)
    return h / max(h.sum(), 1)


def caracteristicas(rgb):
    """Devuelve (vector, nombres). Rasgos de color, textura, frecuencia, nitidez, exposicion y borde."""
    v, n = [], []
    S = rgb.shape[0]

    def add(prefijo, arr):
        arr = np.atleast_1d(np.asarray(arr, np.float32)).ravel()
        v.extend(arr.tolist())
        n.extend([f"{prefijo}_{i}" if len(arr) > 1 else prefijo for i in range(len(arr))])

    f = rgb.astype(np.float32)
    R, G, B = f[..., 0], f[..., 1], f[..., 2]
    Y = 0.299 * R + 0.587 * G + 0.114 * B
    Cr = (R - Y) * 0.713 + 128
    Cb = (B - Y) * 0.564 + 128
    hsv = rgb2hsv(rgb)
    canales = {"Y": (Y, (0, 255)), "Cr": (Cr, (0, 255)), "Cb": (Cb, (0, 255)),
               "H": (hsv[..., 0], (0, 1)), "S": (hsv[..., 1], (0, 1)), "V": (hsv[..., 2], (0, 1))}
    # color
    for k, (c, rg) in canales.items():
        add(f"color_{k}_media", c.mean())
        add(f"color_{k}_desv", c.std())
        add(f"color_{k}_hist", _hist(c, 8, rg))
    # textura LBP
    for k in ("Y", "Cr", "Cb"):
        c = np.clip(canales[k][0], 0, 255).astype(np.uint8)
        lbp = local_binary_pattern(c, 8, 1, "uniform")
        add(f"lbp8_{k}", _hist(lbp, 10, (0, 10)))
        if k == "Y":
            m = S // 2
            for qi, (a, b) in enumerate([(0, 0), (0, m), (m, 0), (m, m)]):
                add(f"lbp8_Y_q{qi}", _hist(lbp[a:a + m, b:b + m], 10, (0, 10)))
            lbp16 = local_binary_pattern(c, 16, 2, "uniform")
            add("lbp16_Y", _hist(lbp16, 18, (0, 18)))
    # frecuencia (moire, desenfoque de reimpresion)
    g = Y - Y.mean()
    win = np.outer(np.hanning(S), np.hanning(S))
    P = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(g * win))) ** 2)
    yy, xx = np.indices(P.shape)
    r = np.hypot(yy - S / 2, xx - S / 2) / (S / 2)
    bins = np.linspace(0, 1, 13)
    add("fft_radial", [P[(r >= bins[i]) & (r < bins[i + 1])].mean() for i in range(12)])
    alto = P[r > 0.25]
    add("fft_pico_alto", alto.max() / (np.median(alto) + 1e-6))
    add("fft_ratio_alto_bajo", P[r > 0.5].mean() / (P[r < 0.15].mean() + 1e-6))
    # nitidez / ruido
    lap = ndi.laplace(Y)
    add("nitidez_lap_var", lap.var())
    m = S // 2
    add("nitidez_lap_var_q", [lap[a:a + m, b:b + m].var() for a, b in [(0, 0), (0, m), (m, 0), (m, m)]])
    gx, gy = ndi.sobel(Y, axis=1), ndi.sobel(Y, axis=0)
    mag = np.hypot(gx, gy)
    add("grad_media", mag.mean())
    add("grad_desv", mag.std())
    add("borde_densidad", (mag > 60).mean())
    add("ruido_resid_desv", (Y - ndi.gaussian_filter(Y, 1.0)).std())
    # exposicion y reflejos
    V, S = hsv[..., 2], hsv[..., 1]
    add("exp_sobreexpuesto", (V > 0.95).mean())
    add("exp_oscuro", (V < 0.10).mean())
    add("exp_especular", ((S < 0.12) & (V > 0.8)).mean())
    add("exp_p5_p95", [np.percentile(Y, 5), np.percentile(Y, 95)])
    # borde del recorte frente al centro (contexto: marco de pantalla o papel)
    anillo = (r > 0.8)
    centro = (r < 0.4)
    add("anillo_vs_centro_grad", mag[anillo].mean() / (mag[centro].mean() + 1e-6))
    add("anillo_vs_centro_color", [Y[anillo].mean() - Y[centro].mean(), Cr[anillo].mean() - Cr[centro].mean(),
                                   Cb[anillo].mean() - Cb[centro].mean()])
    return np.array(v, np.float32), n


def rasgos_imagen(path, margen, size=SIZE, calidad=0):
    try:
        rgb, W, H = cargar(path, margen, size, calidad)
        x, _ = caracteristicas(rgb)
        return x, np.array([W, H, os.path.getsize(path)], np.float64)
    except Exception:
        return None


def nombres_rasgos():
    return caracteristicas(np.zeros((SIZE, SIZE, 3), np.uint8))[1]


# ---------- umbral y metricas ----------
def tasas_en(cands, s, y):
    live, att = np.sort(s[y == 0]), np.sort(s[y == 1])
    bpcer = 1 - np.searchsorted(live, cands, side="left") / len(live)     # reales con score >= umbral (rechazados)
    apcer = np.searchsorted(att, cands, side="left") / len(att)           # ataques con score < umbral (aceptados)
    return bpcer, apcer


def umbral_eer(s, y):
    cands = np.unique(np.quantile(s, np.linspace(0, 1, 1001)))
    b, a = tasas_en(cands, s, y)
    return float(cands[int(np.argmin(np.abs(b - a)))])


def umbral_bpcer(s, y, objetivo=0.05):
    cands = np.unique(np.quantile(s, np.linspace(0, 1, 1001)))
    b, _ = tasas_en(cands, s, y)
    ok = np.where(b <= objetivo)[0]
    return float(cands[ok[0]]) if len(ok) else float(cands[-1])


def apcer_bpcer(s, y, thr):
    k_a = int(((y == 1) & (s < thr)).sum())
    k_b = int(((y == 0) & (s >= thr)).sum())
    return k_a, int((y == 1).sum()), k_b, int((y == 0).sum())


def entrenar(X, y, grupos, idx_train, seed, nombres=None):
    """Separa validacion por persona dentro de train, entrena LightGBM con parada temprana. Devuelve modelo, idx_tr, idx_val."""
    gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed)
    a, b = next(gss.split(idx_train, groups=grupos[idx_train]))
    itr, iva = idx_train[a], idx_train[b]
    assert not (set(grupos[itr]) & set(grupos[iva])), "una persona quedo en entrenamiento y validacion"
    m = lgb.LGBMClassifier(n_estimators=600, learning_rate=0.05, num_leaves=15, subsample=0.8, subsample_freq=1,
                           colsample_bytree=0.5, min_child_samples=20, random_state=seed, verbose=-1)
    m.fit(X[itr], y[itr], eval_set=[(X[iva], y[iva])], eval_metric="auc",
          callbacks=[lgb.early_stopping(50, verbose=False)])
    return m, itr, iva


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--celeba", default="../datos/subconjunto/CelebA_Spoof")
    ap.add_argument("--meta", default="../datos/subconjunto/metadatos_subconjunto.csv")
    ap.add_argument("--discordantes", default="../datos/discordantes_train.txt")
    ap.add_argument("--margen-bb", type=float, default=1.6)
    ap.add_argument("--tam", type=int, default=SIZE, help="lado del recorte (px) sobre el que se calculan los rasgos")
    ap.add_argument("--calidad-jpeg", type=int, default=0, help="recomprime el recorte a JPEG con esta calidad (0 = no); iguala el procesamiento")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--rasgos", help="npz con rasgos ya calculados (salta la extraccion)")
    ap.add_argument("--guardar-rasgos", action="store_true")
    ap.add_argument("--out", default="f2_out")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()

    meta = pd.read_csv(a.meta)
    excl = set()
    if a.discordantes and os.path.exists(a.discordantes):
        with open(a.discordantes, encoding="utf-8-sig") as f:
            excl = {ln.strip().replace("\\", "/") for ln in f if ln.strip()}
    n_excl = int(meta["ruta"].str.replace("\\", "/").isin(excl).sum())
    meta = meta[~meta["ruta"].str.replace("\\", "/").isin(excl)].reset_index(drop=True)
    meta["path"] = [os.path.join(a.celeba, r) for r in meta["ruta"]]
    print(f"Metadatos: {len(meta)} imagenes | discordantes excluidas: {n_excl} de {len(excl)}")

    # ---- rasgos ----
    if a.rasgos and os.path.exists(a.rasgos):
        z = np.load(a.rasgos, allow_pickle=True)
        X, MD, rutas_ok = z["X"], z["MD"], list(z["rutas"])
        print(f"Rasgos cargados de {a.rasgos}: {X.shape}")
    else:
        print(f"Extrayendo rasgos de {len(meta)} imagenes ({a.jobs} procesos)...")
        r = Parallel(n_jobs=a.jobs)(delayed(rasgos_imagen)(p, a.margen_bb, a.tam, a.calidad_jpeg) for p in meta["path"])
        ok = [i for i, v in enumerate(r) if v is not None]
        X = np.vstack([r[i][0] for i in ok])
        MD = np.vstack([r[i][1] for i in ok])
        rutas_ok = [meta["ruta"][i] for i in ok]
        print(f"  listo en {time.time() - t0:.0f} s; imagenes ilegibles: {len(meta) - len(ok)}")
        if a.guardar_rasgos:
            np.savez_compressed(os.path.join(a.out, "f2_rasgos.npz"), X=X, MD=MD, rutas=np.array(rutas_ok))
    meta = meta.set_index("ruta").loc[rutas_ok].reset_index()
    nombres = nombres_rasgos()
    assert X.shape[1] == len(nombres), "numero de rasgos distinto al de nombres"

    y = (meta["carpeta"].str.lower() == "spoof").astype(int).values
    persona = meta["sujeto"].astype(str).values
    es_train = (meta["particion"] == "train").values
    idx_train, idx_test = np.where(es_train)[0], np.where(~es_train)[0]
    assert not (set(persona[idx_train]) & set(persona[idx_test])), "una persona esta en entrenamiento y prueba"
    tipo = meta["tipo_ataque"].astype(int).values

    # ---- 5 semillas ----
    filas, por_tipo, por_ilum, por_ent = [], [], [], []
    ref = None
    for seed in SEEDS:
        m, itr, iva = entrenar(X, y, persona, idx_train, seed)
        s_va, s_te = m.predict_proba(X[iva])[:, 1], m.predict_proba(X[idx_test])[:, 1]
        thr = umbral_eer(s_va, y[iva])
        thr5 = umbral_bpcer(s_va, y[iva], 0.05)
        ka, na, kb, nb = apcer_bpcer(s_te, y[idx_test], thr)
        ka5, _, kb5, _ = apcer_bpcer(s_te, y[idx_test], thr5)
        auc = roc_auc_score(y[idx_test], s_te)
        filas.append({"semilla": seed, "arboles": m.best_iteration_ or m.n_estimators, "AUC": auc, "umbral": thr,
                      "APCER": ka / na, "BPCER": kb / nb, "ACER": (ka / na + kb / nb) / 2,
                      "APCER_bpcer5": ka5 / na, "BPCER_bpcer5": kb5 / nb})
        t = tipo[idx_test]
        for k in sorted(set(t[y[idx_test] == 1])):
            msk = (t == k) & (y[idx_test] == 1)
            por_tipo.append({"semilla": seed, "tipo": k, "n": int(msk.sum()), "k": int((s_te[msk] < thr).sum())})
        for col, dic, dest in (("iluminacion", ILUM, por_ilum), ("entorno", ENTORNO, por_ent)):
            vv = meta[col].astype(int).values[idx_test]
            for k in sorted(set(vv[y[idx_test] == 1])):
                msk = (vv == k) & (y[idx_test] == 1)
                dest.append({"semilla": seed, "grupo": k, "n": int(msk.sum()), "k": int((s_te[msk] < thr).sum())})
        if seed == SEEDS[0]:
            ref = dict(m=m, itr=itr, iva=iva, s_va=s_va, s_te=s_te, thr=thr, thr5=thr5, ka=ka, na=na, kb=kb, nb=nb,
                       ka5=ka5, kb5=kb5)
        print(f"  semilla {seed}: AUC {auc:.3f} | APCER {100 * ka / na:.1f} % | BPCER {100 * kb / nb:.1f} %")
    res = pd.DataFrame(filas)

    # ---- control: solo tamano/formato del archivo ----
    cm = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, num_leaves=7, random_state=42, verbose=-1)
    cm.fit(MD[ref["itr"]], y[ref["itr"]])
    auc_ctrl = roc_auc_score(y[idx_test], cm.predict_proba(MD[idx_test])[:, 1])
    auc_ctrl_val = roc_auc_score(y[ref["iva"]], cm.predict_proba(MD[ref["iva"]])[:, 1])
    sc_te = cm.predict_proba(MD[idx_test])[:, 1]

    # tamano original por clase (todo el subconjunto) y evaluacion donde el tamano NO distingue las clases
    nm = ["ancho (px)", "alto (px)", "peso (KB)"]
    filas_t = []
    for j, nom in enumerate(nm):
        v = MD[:, j] / (1024 if j == 2 else 1)
        for c, nc in ((0, "real"), (1, "ataque")):
            q = np.percentile(v[y == c], [10, 50, 90])
            filas_t.append({"medida": nom, "clase": nc, "p10": f"{q[0]:.0f}", "mediana": f"{q[1]:.0f}", "p90": f"{q[2]:.0f}"})
    tabla_tam = pd.DataFrame(filas_t)
    yt, area, peso = y[idx_test], MD[idx_test, 0] * MD[idx_test, 1], MD[idx_test, 2]

    def rango(v):
        return (max(np.quantile(v[yt == 0], .05), np.quantile(v[yt == 1], .05)),
                min(np.quantile(v[yt == 0], .95), np.quantile(v[yt == 1], .95)))
    (la, ha), (lb, hb) = rango(area), rango(peso)
    comun = (area >= la) & (area <= ha) & (peso >= lb) & (peso <= hb) if (la < ha and lb < hb) else np.zeros(len(yt), bool)
    n_r, n_a = int(((yt == 0) & comun).sum()), int(((yt == 1) & comun).sum())
    if min(n_r, n_a) >= 30:
        auc_m = roc_auc_score(yt[comun], ref["s_te"][comun]); auc_c = roc_auc_score(yt[comun], sc_te[comun])
        k_a, n_aa, k_b, n_bb = apcer_bpcer(ref["s_te"][comun], yt[comun], ref["thr"])
        texto_comun = (f"- En el **rango de tamanos que comparten reales y ataques** (area y peso entre sus percentiles 5 y 95 comunes; "
                       f"{n_r} reales y {n_a} ataques de prueba): AUC del modelo {auc_m:.3f}; AUC del control de tamano {auc_c:.3f}; "
                       f"APCER {tasa(k_a, n_aa)}; BPCER {tasa(k_b, n_bb)}.")
    else:
        texto_comun = (f"- En el rango de tamanos comunes (area y peso entre sus percentiles 5 y 95 comunes) quedan solo {n_r} reales y {n_a} ataques "
                       "de prueba: no alcanza para evaluar (se pide al menos 30 por clase).")

    # ---- salidas del modelo de referencia (semilla 42) ----
    m, thr = ref["m"], ref["thr"]
    dump({"model": m, "threshold_eer": thr, "threshold_bpcer5": ref["thr5"], "features": nombres,
          "version": MODEL_VERSION, "margen_bb": a.margen_bb}, os.path.join(a.out, "f2_model.joblib"))
    imp = pd.DataFrame({"rasgo": nombres, "ganancia": m.booster_.feature_importance("gain")})
    imp["ganancia"] = (100 * imp["ganancia"] / imp["ganancia"].sum()).round(1)
    imp = imp.sort_values("ganancia", ascending=False).head(10).rename(columns={"ganancia": "% de ganancia"})

    def fila_csv(idx, s, split):
        d = meta.iloc[idx]
        return pd.DataFrame({"split": split, "is_attack": y[idx], "score": s,
                             "spoof_type": [TIPO.get(int(t), str(t)) for t in d["tipo_ataque"]],
                             "illumination": [ILUM.get(int(t), "") for t in d["iluminacion"]],
                             "environment": [ENTORNO.get(int(t), "") for t in d["entorno"]]})
    pd.concat([fila_csv(ref["iva"], ref["s_va"], "val"), fila_csv(idx_test, ref["s_te"], "test")]).to_csv(
        os.path.join(a.out, "f2_predicciones.csv"), index=False)

    # ---- reporte ----
    def ms(c, pct=True):
        f = 100 if pct else 1
        return f"{f * res[c].mean():.2f} ± {f * res[c].std():.2f}" + (" %" if pct else "")

    def tabla_grupo(lista, nombre_dic, ref_seed_filas):
        d = pd.DataFrame(lista)
        out = []
        for g in sorted(d["grupo"].unique() if "grupo" in d else d["tipo"].unique()):
            col = "grupo" if "grupo" in d else "tipo"
            s = d[d[col] == g]
            p42 = s[s["semilla"] == SEEDS[0]].iloc[0]
            ap = (s["k"] / s["n"]) * 100
            lo, hi = wilson(int(p42["k"]), int(p42["n"]))
            out.append({"grupo": nombre_dic.get(int(g), g), "ataques (prueba)": int(p42["n"]),
                        "APCER semilla 42": f"{100 * p42['k'] / p42['n']:.1f} % (IC {100 * lo:.1f}-{100 * hi:.1f})",
                        "APCER 5 semillas": f"{ap.mean():.1f} ± {ap.std():.1f} %",
                        "confiable (n ≥ 60)": "si" if p42["n"] >= MIN_N else "no, pocas muestras"})
        return pd.DataFrame(out)

    ka, na, kb, nb = ref["ka"], ref["na"], ref["kb"], ref["nb"]
    n_per_tr = len(set(persona[idx_train])); n_per_te = len(set(persona[idx_test]))
    o = [f"# F2 - Vida (liveness) sobre CelebA-Spoof", "",
         f"Modelo `{MODEL_VERSION}`: rasgos clasicos (color, LBP, frecuencias, nitidez, reflejos, borde) + LightGBM. "
         "Score = probabilidad de ataque; se rechaza si score >= umbral. Umbral fijado solo en validacion (APCER = BPCER).", "",
         "## Datos", "",
         f"- Subconjunto de {len(meta)} imagenes: entrenamiento {len(idx_train)} ({n_per_tr} personas), prueba {len(idx_test)} ({n_per_te} personas). "
         "Ninguna persona esta en ambos. Validacion: 25 % de las personas de entrenamiento (se repite por semilla).",
         f"- Reales/ataques en prueba: {nb} / {na}. Discordantes excluidas: {n_excl} de {len(excl)} en la lista.",
         f"- Recorte: alrededor de la caja _BB.txt (base 224, margen {a.margen_bb}), reescalado a {a.tam}x{a.tam}"
         + (f" y recomprimido a JPEG calidad {a.calidad_jpeg} (igual para todas las imagenes)" if a.calidad_jpeg else "")
         + f". {X.shape[1]} rasgos.", "",
         "## Resultados en prueba (media ± desviacion de 5 semillas, 42 a 46)", "",
         "| Medida | 5 semillas | Semilla 42 (modelo entregado) |", "|---|---|---|",
         f"| AUC | {ms('AUC', False)} | {res.loc[0, 'AUC']:.3f} |",
         f"| APCER (ataques aceptados) | {ms('APCER')} | {tasa(ka, na)} |",
         f"| BPCER (reales rechazados) | {ms('BPCER')} | {tasa(kb, nb)} |",
         f"| ACER = (APCER + BPCER) / 2 | {ms('ACER')} | {100 * (ka / na + kb / nb) / 2:.2f} % |", "",
         "Con el umbral que fija BPCER = 5 % en validacion:", "",
         "| Medida | 5 semillas | Semilla 42 |", "|---|---|---|",
         f"| APCER | {ms('APCER_bpcer5')} | {tasa(ref['ka5'], na)} |",
         f"| BPCER | {ms('BPCER_bpcer5')} | {tasa(ref['kb5'], nb)} |", "",
         "## APCER por tipo de ataque (umbral EER)", "",
         md(tabla_grupo(por_tipo, TIPO, None)), "",
         "## APCER por iluminacion", "", md(tabla_grupo(por_ilum, ILUM, None)), "",
         "## APCER por entorno", "", md(tabla_grupo(por_ent, ENTORNO, None)), "",
         "Los reales (`live`) no traen iluminacion ni entorno en este subconjunto (codigo 0), asi que BPCER no se puede desglosar por esas dimensiones.", "",
         "## Control de atajos", "",
         f"- Un modelo con **solo** ancho, alto y peso en bytes del archivo original (sin mirar la cara) da AUC {auc_ctrl:.3f} en prueba "
         f"({auc_ctrl_val:.3f} en validacion).",
         ("- **Atajo fuerte:** el tamano del archivo separa reales de ataques casi por si solo. Los resultados de arriba no demuestran, por si mismos, "
          "deteccion de vida: parte de la senal puede venir de como se capturo cada clase." if auc_ctrl >= 0.8 else
          "- El tamano del archivo separa poco las clases; el atajo de tamano no parece dominar."),
         texto_comun, "",
         "Tamano del archivo original por clase (todo el subconjunto):", "", md(tabla_tam), "",
         "## Rasgos que mas pesan (semilla 42)", "", md(imp), "",
         "## Limites", "",
         "- Subconjunto de 3.000 imagenes de CelebA-Spoof: por tipo de ataque hay del orden de 50 ataques en prueba, asi que los intervalos son anchos; los grupos con menos de 60 se marcan como poco confiables en las tablas.",
         "- Conjunto unico. Reales y ataques pueden diferir en como se capturaron (dispositivo, resolucion, compresion); el control mide solo una parte de eso (tamano y peso del archivo).",
         "- Rasgos hechos a mano, sin redes preentrenadas. No se evaluo en otro conjunto de datos ni con ataques nuevos.",
         "- El umbral y la parada temprana usan la misma validacion; el sesgo es pequeno pero existe.",
         "- Los nombres de los codigos (tipo de ataque, iluminacion, entorno) siguen la documentacion de CelebA-Spoof y deben verificarse contra su ficha.",
         "- Sin atributo de edad (`young`) en el subconjunto: no se audita por edad.",
         "- Licencia: CelebA-Spoof es de uso no comercial. Los pesos no se publican.", ""]
    ruta = os.path.join(a.out, "f2_resultados.md")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(o))
    print("\n".join(o))
    print(f"Escrito: {ruta} | {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
