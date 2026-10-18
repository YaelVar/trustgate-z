"""F3 - Analisis de equidad por edad (TrustGate Z).

Pide Yael, en este orden:
  1. Calibracion DENTRO de cada grupo de edad (50+ y <50), por deciles de score.
  2. Variables que podrian sustituir a la edad:
     a) correlacion de cada variable con la edad,
     b) importancia por grupo (pred_contrib de LightGBM) y razon 50+/<50,
     c) reentrenar sin las 3 variables con mayor razon y reportar el efecto.
  4. Carga de alertas por grupo.
(El punto 3, importancia global, queda para despues.)

NO implementa umbrales distintos por grupo ni verificaciones segun la edad: eso lo decide el
equipo y lo revisa asesoria legal. Solo MIDE.

Uso (desde la raiz del repo, con la rama feature/f3-riesgo-solicitud):
  python f3_riesgo\\f3_analisis.py --data C:\\datasets\\bank-account-fraud\\Base.csv --out docs
  python f3_riesgo\\f3_analisis.py --demo --out demo_out     # SINTETICO: solo prueba el codigo

Escribe un unico archivo: <out>/f3_analisis_equidad.md (sin datos ni CSV).
Usa f3_riesgo.py (misma carpeta): mismo particionado por meses, mismo modelo, misma semilla.
"""
import argparse
import os

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import f3_riesgo as f3

Z = 1.96
N_BINS = 10
R_UMBRAL = 0.3          # |r| minimo para marcar una variable como posible sustituta
TOP_K = 10              # tamano del top por grupo
N_QUITAR = 3            # variables a quitar en el reentrenamiento
AUC_ESPERADO = 0.8158   # corrida anterior con BAF Base completo (para comprobar que se reproduce)


# ---------- utilidades ----------
def pct(x, d=2):
    return "n/d" if pd.isna(x) else f"{100 * x:.{d}f} %"


def wilson(k, n, z=Z):
    if n == 0:
        return np.nan, np.nan
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def md(df, dec=4):
    def f(v):
        if isinstance(v, (float, np.floating)):
            return "n/d" if np.isnan(v) else f"{v:.{dec}f}"
        return str(v)
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(f(v) for v in r) + " |")
    return "\n".join(out)


def grupo_edad(df):
    return np.where(df[f3.AGE].values >= f3.SENSITIVE_AGE, f"{f3.SENSITIVE_AGE}+", f"<{f3.SENSITIVE_AGE}")


# ---------- 0. datos del conjunto de prueba ----------
def tabla_prevalencia(y, grupo):
    rows = []
    for g in [f"{f3.SENSITIVE_AGE}+", f"<{f3.SENSITIVE_AGE}"]:
        m = grupo == g
        rows.append({"grupo": g, "solicitudes": int(m.sum()), "fraudes": int(y[m].sum()),
                     "honestas": int((y[m] == 0).sum()), "tasa de fraude": pct(y[m].mean())})
    return pd.DataFrame(rows)


# ---------- 1. calibracion dentro de cada grupo ----------
def calibracion_grupo(y, s, grupo):
    tablas, resumen = {}, []
    for g in [f"{f3.SENSITIVE_AGE}+", f"<{f3.SENSITIVE_AGE}"]:
        m = grupo == g
        d = pd.DataFrame({"s": s[m], "y": y[m]})
        d["decil"] = pd.qcut(d["s"].rank(method="first"), N_BINS, labels=False) + 1
        t = d.groupby("decil").agg(n=("y", "size"), fraudes=("y", "sum"),
                                   pred=("s", "mean"), obs=("y", "mean")).reset_index()
        ic = [wilson(int(r.fraudes), int(r.n)) for r in t.itertuples()]
        t["obs_ic95"] = [f"{100 * a:.2f}-{100 * b:.2f} %" for a, b in ic]
        t["pred/obs"] = np.where(t["obs"] > 0, t["pred"] / t["obs"], np.nan)
        t["pred"], t["obs"] = t["pred"].map(pct), t["obs"].map(pct)
        tablas[g] = t[["decil", "n", "fraudes", "pred", "obs", "obs_ic95", "pred/obs"]]
        resumen.append({"grupo": g, "prob. predicha media": pct(s[m].mean()),
                        "tasa de fraude observada": pct(y[m].mean()),
                        "pred/obs": s[m].mean() / y[m].mean() if y[m].mean() > 0 else np.nan})
    return tablas, pd.DataFrame(resumen)


def calibracion_comun(y, s, grupo):
    """Mismo rango de score para ambos grupos (deciles del score GLOBAL): a igual score, igual riesgo?"""
    edges = np.unique(np.quantile(s, np.linspace(0, 1, N_BINS + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    b = pd.cut(s, edges, labels=False) + 1
    rows = []
    for k in sorted(pd.unique(b)):
        for g in [f"{f3.SENSITIVE_AGE}+", f"<{f3.SENSITIVE_AGE}"]:
            m = (b == k) & (grupo == g)
            n = int(m.sum())
            rows.append({"decil global": int(k), "grupo": g, "n": n, "fraudes": int(y[m].sum()),
                         "pred": pct(s[m].mean()) if n else "n/d",
                         "obs": pct(y[m].mean()) if n else "n/d"})
    return pd.DataFrame(rows)


# ---------- 2a. correlacion con la edad ----------
def eta(cat, age):
    d = pd.DataFrame({"c": cat.astype(str), "a": age}).dropna()
    m = d["a"].mean()
    sst = ((d["a"] - m) ** 2).sum()
    if sst == 0:
        return np.nan
    gm = d.groupby("c")["a"].agg(["size", "mean"])
    return float(np.sqrt((gm["size"] * (gm["mean"] - m) ** 2).sum() / sst))


def correlaciones(model, df_te):
    X = model.prep.transform(df_te)
    age = df_te[f3.AGE].astype(float).reset_index(drop=True)
    rows = []
    for c in X.columns:
        col = X[c].reset_index(drop=True)
        if str(col.dtype) == "category":
            rows.append({"variable": c, "tipo": "categorica (eta)", "r": eta(col, age)})
        else:
            rows.append({"variable": c, "tipo": "numerica (Pearson)",
                         "r": float(pd.concat([col.astype(float), age], axis=1).corr().iloc[0, 1])})
    t = pd.DataFrame(rows)
    t["|r|"] = t["r"].abs()
    return t.sort_values("|r|", ascending=False).reset_index(drop=True)


# ---------- 2b. importancia por grupo ----------
def importancia_grupo(model, df_te, grupo):
    X = model.prep.transform(df_te)
    contrib = model.booster.predict(X, pred_contrib=True)[:, :-1]   # sin la columna de sesgo
    a = np.abs(contrib)
    g1, g0 = f"{f3.SENSITIVE_AGE}+", f"<{f3.SENSITIVE_AGE}"
    t = pd.DataFrame({"variable": X.columns,
                      f"contrib. media abs. {g1}": a[grupo == g1].mean(axis=0),
                      f"contrib. media abs. {g0}": a[grupo == g0].mean(axis=0)})
    t["razon"] = t.iloc[:, 1] / t.iloc[:, 2].replace(0, np.nan)
    return t


def top_union(t):
    c1, c0 = t.columns[1], t.columns[2]
    top1 = t.sort_values(c1, ascending=False).head(TOP_K)["variable"]
    top0 = t.sort_values(c0, ascending=False).head(TOP_K)["variable"]
    u = t[t["variable"].isin(set(top1) | set(top0))].copy()
    u["en top-10 de"] = [", ".join(g for g, s in ((c1.split()[-1], top1), (c0.split()[-1], top0))
                                    if v in set(s)) for v in u["variable"]]
    return u.sort_values("razon", ascending=False).reset_index(drop=True)


# ---------- 2c. reentrenar sin sustitutas ----------
def resumen_modelo(nombre, model, df_va, df_te):
    thr = f3.threshold_at_fpr(df_va[f3.LABEL].values, model.score(df_va))
    y, s = df_te[f3.LABEL].values, model.score(df_te)
    pred = s >= thr
    grupo = grupo_edad(df_te)
    gm = f3.group_metrics(y, s, thr, grupo).set_index("grupo")
    g1, g0 = f"{f3.SENSITIVE_AGE}+", f"<{f3.SENSITIVE_AGE}"
    fprs = gm["fpr"].dropna()
    return {"modelo": nombre, "AUC": roc_auc_score(y, s),
            "TPR global": float((pred & (y == 1)).sum() / (y == 1).sum()),
            "FPR global": float((pred & (y == 0)).sum() / (y == 0).sum()),
            f"FPR {g1}": gm.loc[g1, "fpr"], f"FPR {g0}": gm.loc[g0, "fpr"],
            "razon FPR (menor/mayor)": float(fprs.min() / fprs.max()),
            f"alertas {g1}": gm.loc[g1, "tasa_alertas"], f"alertas {g0}": gm.loc[g0, "tasa_alertas"]}


def split_meses(df):
    ult = max(f3.TRAIN_MONTHS)
    return (df[df[f3.MONTH].isin(f3.TRAIN_MONTHS) & (df[f3.MONTH] != ult)],
            df[df[f3.MONTH] == ult], df[df[f3.MONTH].isin(f3.TEST_MONTHS)])


# ---------- 4. carga de alertas ----------
def carga_alertas(model, df_va, df_te):
    thr = f3.threshold_at_fpr(df_va[f3.LABEL].values, model.score(df_va))
    y, s = df_te[f3.LABEL].values, model.score(df_te)
    pred = s >= thr
    grupo = grupo_edad(df_te)
    rows = []
    for g in [f"{f3.SENSITIVE_AGE}+", f"<{f3.SENSITIVE_AGE}"]:
        m = grupo == g
        rows.append({"grupo": g,
                     "alertas por cada 100 solicitudes (todas)": 100 * pred[m].mean(),
                     "falsas alertas por cada 100 solicitudes honestas": 100 * (pred[m] & (y[m] == 0)).sum() / (y[m] == 0).sum()})
    t = pd.DataFrame(rows)
    r = t.iloc[0, 1:].values / t.iloc[1, 1:].values
    return t, r, thr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default="docs")
    a = ap.parse_args()
    if a.demo:
        print("*** DATOS SINTETICOS: no reportar estas cifras ***")
        df = f3.make_demo()
    elif a.data:
        df = f3.load_data(a.data)
    else:
        ap.error("usa --demo o --data")
    if f3.LABEL not in df.columns and "is_fraud" in df.columns:
        f3.LABEL = "is_fraud"
    df_tr, df_va, df_te = split_meses(df)
    print(f"entrenamiento={len(df_tr)} validacion={len(df_va)} prueba={len(df_te)}")

    model = f3.train(df_tr, df_va)
    base = resumen_modelo("base (sin la edad)", model, df_va, df_te)
    print(f"AUC base: {base['AUC']:.4f} (corrida anterior con BAF Base: {AUC_ESPERADO})")
    y, s, grupo = df_te[f3.LABEL].values, model.score(df_te), grupo_edad(df_te)

    # comprobacion de que la edad no entra
    feats = model.prep.features
    sospechosas = [c for c in feats if "age" in c.lower() or "birth" in c.lower()]
    edad_dentro = f3.AGE in feats

    md_out = ["# F3 - Analisis de equidad por edad", "",
              ("**DATOS SINTETICOS (--demo): estas cifras no valen.**\n" if a.demo else ""),
              f"Conjunto: BAF Base, {len(df)} filas. Entrenan los meses {f3.TRAIN_MONTHS[:-1]}, "
              f"valida el mes {f3.TRAIN_MONTHS[-1]}, prueba los meses {f3.TEST_MONTHS}. "
              f"Todas las cifras son del conjunto de prueba. El grupo sensible es edad >= {f3.SENSITIVE_AGE}.", "",
              "Metrica de equidad: **igualdad de tasa de falsos positivos (razon FPR menor/mayor)** = "
              "FPR del grupo con menos falsas alertas / FPR del grupo con mas. 1,0 = igual. "
              "FPR = honestas marcadas como sospechosas / honestas. "
              "No es paridad predictiva (precision).", "",
              "## 0. Datos de prueba por grupo", md(tabla_prevalencia(y, grupo)), ""]

    # 1
    tablas, resumen = calibracion_grupo(y, s, grupo)
    md_out += ["## 1. Calibracion dentro de cada grupo (deciles del score dentro del grupo)",
               "pred = probabilidad media predicha; obs = tasa de fraude observada; pred/obs = 1 es calibrado.", "",
               "### Resumen", md(resumen, 3), ""]
    for g, t in tablas.items():
        md_out += [f"### Grupo {g}", md(t, 3), ""]
    md_out += ["### Mismos rangos de score para ambos grupos (deciles del score global)",
               "Si el modelo esta calibrado igual en ambos grupos, a igual score la tasa observada deberia ser parecida "
               "(la diferencia de prevalencia ya esta incluida en el score).", "", md(calibracion_comun(y, s, grupo)), ""]

    # 2a
    corr = correlaciones(model, df_te)
    altas = corr[corr["|r|"] >= R_UMBRAL]
    md_out += ["## 2. Variables que podrian sustituir a la edad", "",
               f"- `{f3.AGE}` entre las variables del modelo: **{'SI (revisar!)' if edad_dentro else 'no'}**.",
               f"- Variables con 'age' o 'birth' en el nombre: {sospechosas if sospechosas else 'ninguna'}. "
               "(Revisar a mano si alguna deriva de la edad.)", "",
               f"### 2a. Correlacion de cada variable con la edad (prueba)",
               (f"Variables con |r| >= {R_UMBRAL}: {', '.join(altas['variable'])}." if len(altas)
                else f"Ninguna variable llega a |r| = {R_UMBRAL}. El maximo es {corr.iloc[0]['|r|']:.3f} "
                     f"({corr.iloc[0]['variable']})."), "",
               md(corr[["variable", "tipo", "r"]].head(15), 3), "(se muestran las 15 con mayor |r|)", ""]

    # 2b
    imp = importancia_grupo(model, df_te, grupo)
    u = top_union(imp)
    md_out += ["### 2b. Importancia por grupo (media del valor absoluto de la contribucion, escala log-odds, prueba)",
               f"Union de los top {TOP_K} de cada grupo, ordenada por la razon "
               f"{imp.columns[1].split()[-1]}/{imp.columns[2].split()[-1]}.", "", md(u, 4), ""]
    # 2c: candidatas = variables de la union (importancia relevante) con mayor razon
    quitar = list(u.sort_values("razon", ascending=False)["variable"].head(N_QUITAR))
    md_out += [f"### 2c. Reentrenar sin las {N_QUITAR} variables con mayor razon",
               f"Candidatas: solo las de la tabla 2b (para no elegir variables casi sin importancia con razones "
               f"inestables). Quitadas, de la mas a la menos desbalanceada: {quitar}.", ""]
    filas = [base]
    for k in range(1, len(quitar) + 1):
        m_k = f3.train(df_tr.drop(columns=quitar[:k]), df_va)
        filas.append(resumen_modelo(f"sin {', '.join(quitar[:k])}", m_k, df_va, df_te))
        print(f"reentrenado sin {quitar[:k]}: AUC {filas[-1]['AUC']:.4f}")
    t = pd.DataFrame(filas)
    for c in t.columns:
        if c.startswith(("TPR", "FPR", "alertas")):
            t[c] = t[c].map(pct)
    md_out += [md(t, 4), "", "Cada fila quita una variable mas que la anterior (acumulado), "
               "con el mismo umbral fijado en validacion (FPR 5 %).", ""]

    # 4
    ca, r, thr = carga_alertas(model, df_va, df_te)
    md_out += ["## 4. Carga de alertas por grupo (modelo base)", f"Umbral: {thr:.4f}.", "", md(ca, 2), "",
               f"Razon {ca['grupo'][0]} / {ca['grupo'][1]}: {r[0]:.2f} veces en alertas por 100 solicitudes, "
               f"{r[1]:.2f} veces en falsas alertas por 100 honestas.", "",
               "Nota: 'alertas por 100 solicitudes' incluye fraudes bien detectados; "
               "'falsas alertas por 100 honestas' es el FPR.", ""]

    os.makedirs(a.out, exist_ok=True)
    ruta = os.path.join(a.out, "f3_analisis_equidad.md")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(md_out))
    print("\n".join(md_out))
    print(f"\nEscrito: {ruta}")


if __name__ == "__main__":
    main()
