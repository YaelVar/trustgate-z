"""F3 - Complemento de equidad (TrustGate Z).

Responde a los ajustes de Yael sobre el commit f0336ef (todo en PRUEBA, meses 6-7):
  1. FPR de 50+ y <50 DENTRO de cada categoria de housing_status. Pregunta: la brecha
     (9,7 % frente a 4,7 %) se explica por la composicion de housing_status o persiste dentro
     de cada categoria. Se agrega una estandarizacion directa para cuantificarlo.
  2. Prueba rapida de la hipotesis sobre date_of_birth_distinct_emails_4w: solicitantes por
     decada de edad y media de la variable por decada, en entrenamiento y en prueba.
  3. Tabla de referencia para el README: media +- desviacion de 5 semillas (y la semilla 42 como
     ejemplo), alertas por 100 solicitudes y falsas alarmas por 100 honestas por separado, y
     deriva temporal (KS) de credit_risk_score y date_of_birth_distinct_emails_4w.

NO cambia el modelo, NO quita variables, NO usa umbrales por grupo ni nada especifico por edad.

Uso (raiz del repo, rama feature/f3-riesgo-solicitud, junto a f3_riesgo.py y f3_analisis.py):
  python f3_riesgo\\f3_extra.py --data C:\\datasets\\bank-account-fraud\\Base.csv --out docs
  python f3_riesgo\\f3_extra.py --demo --out demo_out        # SINTETICO: solo prueba el codigo

Escribe un unico archivo: <out>/f3_extra.md (sin datos ni CSV).
"""
import argparse
import os

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import roc_auc_score

import f3_analisis as fa
import f3_riesgo as f3

G1, G0 = fa.G1, fa.G0
HOUSING = "housing_status"
DOB = "date_of_birth_distinct_emails_4w"
CREDIT = "credit_risk_score"
SEMILLA_BASE = 42
MIN_HONESTAS = 100     # minimo de solicitudes honestas por grupo para considerar fiable una celda


# ---------- por semilla ----------
def evaluar(df_tr, df_va, df_te, seed):
    model = f3.train(df_tr, df_va, seed=seed)
    thr = f3.threshold_at_fpr(df_va[f3.LABEL].values, model.score(df_va))
    y, s = df_te[f3.LABEL].values, model.score(df_te)
    pred, g = s >= thr, fa.grupo_edad(df_te)
    hon = y == 0
    fpr1 = float(pred[(g == G1) & hon].mean())
    fpr0 = float(pred[(g == G0) & hon].mean())

    # estandarizacion directa por categoria de housing_status
    hs = df_te[HOUSING].astype(str).values
    cats = sorted(pd.unique(hs))
    n1 = {c: int(((g == G1) & hon & (hs == c)).sum()) for c in cats}
    n0 = {c: int(((g == G0) & hon & (hs == c)).sum()) for c in cats}
    f1c = {c: float(pred[(g == G1) & hon & (hs == c)].mean()) for c in cats if n1[c] > 0}
    f0c = {c: float(pred[(g == G0) & hon & (hs == c)].mean()) for c in cats if n0[c] > 0}
    comun = [c for c in cats if c in f1c and c in f0c]
    w0 = np.array([n0[c] for c in comun], float)
    w1 = np.array([n1[c] for c in comun], float)
    # FPR de 50+ si tuvieran la composicion de housing_status de <50
    fpr1_std = float(np.dot(w0 / w0.sum(), [f1c[c] for c in comun]))
    # FPR de <50 si tuvieran la composicion de 50+
    fpr0_std = float(np.dot(w1 / w1.sum(), [f0c[c] for c in comun]))
    brecha = fpr1 - fpr0
    res = {"semilla": seed, "AUC": roc_auc_score(y, s),
           "TPR": float((pred & (y == 1)).sum() / (y == 1).sum()),
           "FPR": float(pred[hon].mean()), "FPR1": fpr1, "FPR0": fpr0,
           "razon_menor_mayor": min(fpr1, fpr0) / max(fpr1, fpr0), "razon_FPR": fpr1 / fpr0,
           "alertas1": float(pred[g == G1].mean()), "alertas0": float(pred[g == G0].mean()),
           "FPR1_con_mezcla_de_0": fpr1_std, "FPR0_con_mezcla_de_1": fpr0_std,
           "brecha_explicada_A": (fpr1 - fpr1_std) / brecha if brecha else np.nan,
           "brecha_explicada_B": (fpr0_std - fpr0) / brecha if brecha else np.nan}
    return res, (pred, y, g, hs)


# ---------- 1. FPR por categoria ----------
def tabla_housing(pred, y, g, hs):
    rows = []
    for c in sorted(pd.unique(hs)) + ["TODAS"]:
        mc = np.ones(len(y), bool) if c == "TODAS" else hs == c
        fila = {"categoria": c}
        fprs = {}
        for gr in (G1, G0):
            mg = mc & (g == gr)
            h = mg & (y == 0)
            k, n = int(pred[h].sum()), int(h.sum())
            lo, hi = fa.wilson(k, n)
            fila[f"n {gr}"] = int(mg.sum())
            fila[f"honestas {gr}"] = n
            fprs[gr] = k / n if n else np.nan
            fila[f"FPR {gr} (IC 95 %)"] = "n/d" if n == 0 else f"{100 * k / n:.2f} % ({100 * lo:.1f}-{100 * hi:.1f})"
        fila["razon FPR 50+/<50"] = fprs[G1] / fprs[G0] if fprs[G0] and not np.isnan(fprs[G1]) else np.nan
        fila["fiable"] = "si" if min(fila[f"honestas {G1}"], fila[f"honestas {G0}"]) >= MIN_HONESTAS else "NO (pocas honestas)"
        rows.append(fila)
    return pd.DataFrame(rows)


# ---------- 2. hipotesis date_of_birth_distinct_emails_4w ----------
def hipotesis_dob(df):
    periodos = (("entrenamiento", df[df[f3.MONTH].isin(f3.TRAIN_MONTHS)]),
                ("prueba", df[df[f3.MONTH].isin(f3.TEST_MONTHS)]))
    t = pd.DataFrame({"decada de edad": sorted(df[f3.AGE].unique())})
    for nombre, d in periodos:
        gg = d.groupby(f3.AGE)[DOB].agg(["size", "mean"])
        t[f"solicitantes {nombre}"] = t["decada de edad"].map(gg["size"]).fillna(0).astype(int)
        t[f"media {nombre}"] = t["decada de edad"].map(gg["mean"])
    cors = []
    for nombre, _ in periodos:
        n, m = t[f"solicitantes {nombre}"], t[f"media {nombre}"]
        for etiqueta, ok in (("todas las decadas", n > 0), ("solo decadas con >= 100 solicitantes", n >= 100)):
            if ok.sum() >= 3:
                cors.append({"periodo": nombre, "decadas usadas": f"{etiqueta} ({int(ok.sum())})",
                             "Pearson (n frente a media)": stats.pearsonr(n[ok], m[ok])[0],
                             "Spearman (n frente a media)": stats.spearmanr(n[ok], m[ok])[0],
                             "Pearson (log n frente a media)": stats.pearsonr(np.log(n[ok]), m[ok])[0]})
    return t, pd.DataFrame(cors)


# ---------- 3. tabla de referencia ----------
def tabla_referencia(res, ejemplo):
    def f(col, esc, dec, unidad):
        v = res[col].values * esc
        sd = v.std(ddof=1) if len(v) > 1 else 0.0
        return f"{v.mean():.{dec}f} ± {sd:.{dec}f}{unidad}", f"{ejemplo[col] * esc:.{dec}f}{unidad}"
    filas = [("AUC", "AUC", 1, 4, ""),
             ("TPR global", "TPR", 100, 2, " %"),
             ("Falsas alarmas por 100 honestas, global (FPR)", "FPR", 100, 2, ""),
             (f"Falsas alarmas por 100 honestas, {G1}", "FPR1", 100, 2, ""),
             (f"Falsas alarmas por 100 honestas, {G0}", "FPR0", 100, 2, ""),
             ("Razon de falsas alarmas 50+/<50 (veces)", "razon_FPR", 1, 2, ""),
             ("Igualdad de tasa de falsos positivos (FPR menor / FPR mayor)", "razon_menor_mayor", 1, 3, ""),
             (f"Alertas por 100 solicitudes, {G1}", "alertas1", 100, 2, ""),
             (f"Alertas por 100 solicitudes, {G0}", "alertas0", 100, 2, "")]
    rows = []
    for nombre, col, esc, dec, un in filas:
        a, b = f(col, esc, dec, un)
        rows.append({"medida": nombre, f"media ± desviacion ({len(res)} semillas)": a, f"semilla {SEMILLA_BASE} (ejemplo)": b})
    r = res["alertas1"] / res["alertas0"]
    ex = ejemplo["alertas1"] / ejemplo["alertas0"]
    rows.append({"medida": "Razon de alertas por 100 solicitudes 50+/<50 (veces)",
                 f"media ± desviacion ({len(res)} semillas)": f"{r.mean():.2f} ± {r.std(ddof=1) if len(r) > 1 else 0:.2f}",
                 f"semilla {SEMILLA_BASE} (ejemplo)": f"{ex:.2f}"})
    return pd.DataFrame(rows)


def deriva(df):
    tr = df[df[f3.MONTH].isin(f3.TRAIN_MONTHS)]
    te = df[df[f3.MONTH].isin(f3.TEST_MONTHS)]
    rows = []
    for v in (CREDIT, DOB):
        if v in df:
            ks = stats.ks_2samp(tr[v].astype(float), te[v].astype(float))
            rows.append({"variable": v, "media entrenamiento": tr[v].mean(), "media prueba": te[v].mean(),
                         "KS (entrenamiento frente a prueba)": ks.statistic})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--semillas", type=int, default=5)
    ap.add_argument("--out", default="docs")
    a = ap.parse_args()
    if a.demo:
        print("*** DATOS SINTETICOS: no reportar estas cifras ***")
        df = fa.demo_extra(f3.make_demo())
    elif a.data:
        df = f3.load_data(a.data)
    else:
        ap.error("usa --demo o --data")
    if f3.LABEL not in df.columns and "is_fraud" in df.columns:
        f3.LABEL = "is_fraud"
    df_tr, df_va, df_te = fa.split_meses(df)
    semillas = list(range(SEMILLA_BASE, SEMILLA_BASE + a.semillas))

    resultados, ejemplo, arrays = [], None, None
    for sd in semillas:
        r, arr = evaluar(df_tr, df_va, df_te, sd)
        resultados.append(r)
        if sd == SEMILLA_BASE:
            ejemplo, arrays = r, arr
        print(f"semilla {sd}: AUC {r['AUC']:.4f} | FPR 50+ {100 * r['FPR1']:.2f} % | FPR <50 {100 * r['FPR0']:.2f} %")
    res = pd.DataFrame(resultados)
    print(f"AUC semilla {SEMILLA_BASE}: {ejemplo['AUC']:.4f} (corrida anterior: 0.8158)")

    o = ["# F3 - Complemento de equidad", "",
         ("**DATOS SINTETICOS (--demo): estas cifras no valen.**\n" if a.demo else ""),
         f"BAF Base, {len(df)} filas. Entrenan los meses {f3.TRAIN_MONTHS[:-1]}, valida el mes {f3.TRAIN_MONTHS[-1]}, "
         f"prueba los meses {f3.TEST_MONTHS}. Todo en prueba. Umbral por modelo: FPR 5 % en validacion.", ""]

    # 1
    o += ["## 1. FPR por categoria de housing_status y por grupo de edad",
          f"Modelo de la semilla {SEMILLA_BASE} (el entregado). FPR = honestas marcadas como sospechosas / honestas. "
          f"Una celda es fiable con al menos {MIN_HONESTAS} honestas en cada grupo.", "",
          md_(tabla_housing(*arrays), 3), ""]
    pr = ["FPR 50+ observado", "FPR <50 observado", "FPR 50+ con la mezcla de housing_status de <50 (A)",
          "FPR <50 con la mezcla de housing_status de 50+ (B)", "Parte de la brecha explicada por composicion (A)",
          "Parte de la brecha explicada por composicion (B)"]
    cols = ["FPR1", "FPR0", "FPR1_con_mezcla_de_0", "FPR0_con_mezcla_de_1", "brecha_explicada_A", "brecha_explicada_B"]
    filas = []
    for n_, c in zip(pr, cols):
        v = res[c].values
        esc = 100 if c.startswith("FPR") else 100
        un = " %"
        filas.append({"medida": n_, f"media ± desviacion ({len(res)} semillas)":
                      f"{esc * v.mean():.2f} ± {esc * (v.std(ddof=1) if len(v) > 1 else 0):.2f}{un}",
                      f"semilla {SEMILLA_BASE}": f"{esc * ejemplo[c]:.2f}{un}"})
    o += ["### Cuanto de la brecha es composicion",
          "Estandarizacion directa: (A) toma el FPR de 50+ dentro de cada categoria y lo pesa con la proporcion de "
          "honestas de <50 en cada categoria; (B) hace lo contrario. Si (A) se acerca al FPR de <50 (o (B) al de 50+), "
          "la brecha se explica por composicion. Si (A) sigue cerca del FPR de 50+, persiste dentro de las categorias. "
          "Solo quedan fuera las categorias sin honestas en alguno de los grupos; BF y BG entran con pesos menores a 0,2 % y no cambian el resultado.", "",
          md_(pd.DataFrame(filas), 2), ""]

    # 2
    if DOB in df:
        t, c = hipotesis_dob(df)
        for col in t.columns:
            if col == "decada de edad" or col.startswith("solicitantes"):
                t[col] = t[col].astype(int).astype(str)
            else:
                t[col] = t[col].map(lambda v: "n/d" if pd.isna(v) else f"{v:.3f}")
        o += ["## 2. Hipotesis: la media de date_of_birth_distinct_emails_4w sigue la densidad de solicitantes por decada",
              "Entrenamiento = meses 0-5; prueba = meses 6-7. Decada de edad = valor de customer_age.", "",
              md_(t, 3), "", "Correlacion entre el numero de solicitantes por decada y la media de la variable "
              "(pocos puntos: lectura orientativa):", "", md_(c, 3), ""]

    # 3
    o += ["## 3. Cifras de referencia para el README", "",
          md_(tabla_referencia(res, ejemplo), 2), "",
          "'Falsas alarmas por 100 honestas' (FPR) y 'alertas por 100 solicitudes' son medidas distintas: la segunda "
          "incluye los fraudes bien detectados.", "", "### Deriva temporal (entrenamiento frente a prueba)", ""]
    d = deriva(df)
    if len(d):
        o += [md_(d, 3), ""]

    os.makedirs(a.out, exist_ok=True)
    ruta = os.path.join(a.out, "f3_extra.md")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(o))
    print("\n".join(o))
    print(f"\nEscrito: {ruta}")


md_ = fa.md

if __name__ == "__main__":
    main()
