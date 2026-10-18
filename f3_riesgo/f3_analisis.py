"""F3 - Analisis de equidad por edad (TrustGate Z), version 2.

Contenido (todo sobre el conjunto de PRUEBA, meses 6-7, salvo donde se indique):
  1. Calibracion DENTRO de cada grupo de edad por deciles: n, probabilidad predicha media,
     tasa observada, fraudes, e indicacion de en que deciles el modelo subestima o sobreestima
     (prediccion fuera del IC 95 % de Wilson de la tasa observada).
  2. Variables que podrian sustituir a la edad:
     - correlacion con la edad (Pearson y Spearman para numericas; eta y V de Cramer para
       categoricas sin orden), relacion de date_of_birth_distinct_emails_4w y housing_status con la edad,
     - importancia por grupo (pred_contrib) y razon 50+/<50,
     - resultado CON y SIN cada variable candidata, con varias semillas (media y desviacion).
  3. credit_risk_score: varias semillas con y sin la variable, y su distribucion por mes
     (entrenamiento 0-5 frente a prueba 6-7).
  4. Carga de alertas por grupo: dos medidas distintas, nombradas por separado.

NO implementa umbrales distintos por grupo ni verificaciones segun la edad, y NO elimina
ninguna variable del modelo: solo MIDE. Eso lo decide el equipo con asesoria legal.

Uso (desde la raiz del repo, rama feature/f3-riesgo-solicitud):
  python f3_riesgo\\f3_analisis.py --data C:\\datasets\\bank-account-fraud\\Base.csv --out docs
  python f3_riesgo\\f3_analisis.py --demo --semillas 2 --out demo_out   # SINTETICO: solo prueba el codigo

Escribe un unico archivo: <out>/f3_analisis_equidad.md (sin datos ni CSV).
Tarda mas que la version anterior: entrena unos 30 modelos (6 configuraciones x 5 semillas).
"""
import argparse
import os
import time

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import roc_auc_score

import f3_riesgo as f3

Z = 1.96
N_BINS = 10
R_UMBRAL = 0.3            # |r| minimo para marcar una variable como posible sustituta
R_CANDIDATAS = 0.25       # umbral mas bajo para incluir candidatas en "con y sin"
TOP_K = 10
SEMILLA_BASE = 42         # con esta semilla se reproduce AUC 0.8158
VAR_DOB = "date_of_birth_distinct_emails_4w"
VAR_HOUSING = "housing_status"
VAR_CREDIT = "credit_risk_score"
VAR_CARDS = "has_other_cards"
G1, G0 = f"{f3.SENSITIVE_AGE}+", f"<{f3.SENSITIVE_AGE}"


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
    return np.where(df[f3.AGE].values >= f3.SENSITIVE_AGE, G1, G0)


def split_meses(df):
    ult = max(f3.TRAIN_MONTHS)
    return (df[df[f3.MONTH].isin(f3.TRAIN_MONTHS) & (df[f3.MONTH] != ult)],
            df[df[f3.MONTH] == ult], df[df[f3.MONTH].isin(f3.TEST_MONTHS)])


def demo_extra(df):
    """Solo para --demo: agrega columnas con los nombres de BAF para ejercitar todo el codigo."""
    r = np.random.default_rng(5)
    age = df[f3.AGE].values
    df[VAR_DOB] = r.poisson(np.where(age >= 50, 1.5, 0.5))
    df[VAR_HOUSING] = np.where(r.random(len(df)) < np.where(age >= 50, .6, .2), "BA",
                               r.choice(["BB", "BC", "BD"], len(df)))
    df[VAR_CARDS] = r.integers(0, 2, len(df))
    return df


# ---------- 0. datos de prueba ----------
def tabla_prevalencia(y, grupo):
    rows = []
    for g in (G1, G0):
        m = grupo == g
        rows.append({"grupo": g, "solicitudes": int(m.sum()), "fraudes": int(y[m].sum()),
                     "honestas": int((y[m] == 0).sum()), "tasa de fraude": pct(y[m].mean())})
    return pd.DataFrame(rows)


# ---------- 1. calibracion ----------
def calibracion_grupo(y, s, grupo):
    tablas, deciles = {}, {}
    for g in (G1, G0):
        m = grupo == g
        d = pd.DataFrame({"s": s[m], "y": y[m]})
        d["decil"] = pd.qcut(d["s"].rank(method="first"), N_BINS, labels=False) + 1
        t = d.groupby("decil").agg(n=("y", "size"), fraudes=("y", "sum"),
                                   pred=("s", "mean"), obs=("y", "mean")).reset_index()
        ic = [wilson(int(r.fraudes), int(r.n)) for r in t.itertuples()]
        lo = np.array([a for a, _ in ic])
        hi = np.array([b for _, b in ic])
        t["estado"] = np.where(t["pred"] < lo, "SUBESTIMA", np.where(t["pred"] > hi, "SOBREESTIMA", "compatible"))
        deciles[g] = {"subestima": [int(k) for k in t.loc[t.estado == "SUBESTIMA", "decil"]],
                      "sobreestima": [int(k) for k in t.loc[t.estado == "SOBREESTIMA", "decil"]]}
        t["obs_ic95"] = [f"{100 * a:.2f}-{100 * b:.2f} %" for a, b in ic]
        t["pred/obs"] = np.where(t["obs"] > 0, t["pred"] / t["obs"], np.nan)
        t["pred"], t["obs"] = t["pred"].map(pct), t["obs"].map(pct)
        tablas[g] = t[["decil", "n", "fraudes", "pred", "obs", "obs_ic95", "pred/obs", "estado"]]
    return tablas, deciles


def calibracion_comun(y, s, grupo):
    """Mismos rangos de score para ambos grupos (deciles del score GLOBAL; con empates salen menos tramos)."""
    edges = np.unique(np.quantile(s, np.linspace(0, 1, N_BINS + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    b = pd.cut(s, edges, labels=False) + 1
    rows = []
    for k in sorted(pd.unique(b)):
        for g in (G1, G0):
            m = (b == k) & (grupo == g)
            n = int(m.sum())
            rows.append({"tramo de score global": int(k), "grupo": g, "n": n, "fraudes": int(y[m].sum()),
                         "pred": pct(s[m].mean()) if n else "n/d", "obs": pct(y[m].mean()) if n else "n/d"})
    return pd.DataFrame(rows)


# ---------- 2a. relacion con la edad ----------
def eta(cat, age):
    """Razon de correlacion: cuanto de la varianza de la edad (numerica) explica la categoria. 0 a 1."""
    d = pd.DataFrame({"c": cat.astype(str), "a": age}).dropna()
    m = d["a"].mean()
    sst = ((d["a"] - m) ** 2).sum()
    if sst == 0:
        return np.nan
    gm = d.groupby("c")["a"].agg(["size", "mean"])
    return float(np.sqrt((gm["size"] * (gm["mean"] - m) ** 2).sum() / sst))


def cramer_v(cat, age):
    """V de Cramer con correccion de sesgo (Bergsma), edad tratada como categorias. 0 a 1."""
    d = pd.DataFrame({"c": cat.astype(str), "a": age.astype(str)}).dropna()
    ct = pd.crosstab(d["c"], d["a"])
    if ct.shape[0] < 2 or ct.shape[1] < 2:
        return np.nan
    chi2 = stats.chi2_contingency(ct, correction=False)[0]
    n = ct.values.sum()
    r, k = ct.shape
    phi2c = max(0.0, chi2 / n - (k - 1) * (r - 1) / (n - 1))
    rc, kc = r - (r - 1) ** 2 / (n - 1), k - (k - 1) ** 2 / (n - 1)
    den = min(kc - 1, rc - 1)
    return float(np.sqrt(phi2c / den)) if den > 0 else np.nan


def correlaciones(model, df_te):
    X = model.prep.transform(df_te)
    age = df_te[f3.AGE].astype(float).reset_index(drop=True)
    rows = []
    for c in X.columns:
        col = X[c].reset_index(drop=True)
        if str(col.dtype) == "category":
            rows.append({"variable": c, "tipo": "categorica sin orden", "medida": "eta", "valor": eta(col, age),
                         "complementaria": "V de Cramer", "valor_compl": cramer_v(col, age)})
        else:
            pair = pd.concat([col.astype(float), age], axis=1)
            rows.append({"variable": c, "tipo": "numerica", "medida": "Pearson", "valor": float(pair.corr().iloc[0, 1]),
                         "complementaria": "Spearman", "valor_compl": float(pair.corr(method="spearman").iloc[0, 1])})
    t = pd.DataFrame(rows)
    t["abs"] = t["valor"].abs()
    return t.sort_values("abs", ascending=False).reset_index(drop=True)


def relacion_dob(df_te):
    d = df_te.groupby(f3.AGE)[VAR_DOB].agg(n="size", media="mean", p90=lambda x: x.quantile(.9),
                                           pct_mayor_0=lambda x: (x > 0).mean()).reset_index()
    d["pct_mayor_0"] = d["pct_mayor_0"].map(pct)
    d.columns = [f3.AGE, "n", f"media de {VAR_DOB}", "percentil 90", "% con valor > 0"]
    return d


def relacion_housing(df_te, grupo):
    ct = pd.crosstab(df_te[VAR_HOUSING].astype(str), grupo)
    out = pd.DataFrame({"categoria": ct.index})
    for g in (G1, G0):
        out[f"% de {g}"] = [pct(v) for v in (ct[g] / ct[g].sum()).values]
    fr = df_te.groupby(df_te[VAR_HOUSING].astype(str))[f3.LABEL].mean()
    out["tasa de fraude"] = [pct(fr[c]) for c in out["categoria"]]
    return out


# ---------- 2b. importancia por grupo ----------
def importancia_grupo(model, df_te, grupo):
    X = model.prep.transform(df_te)
    a = np.abs(model.booster.predict(X, pred_contrib=True)[:, :-1])   # sin la columna de sesgo
    t = pd.DataFrame({"variable": X.columns,
                      f"contrib. media abs. {G1}": a[grupo == G1].mean(axis=0),
                      f"contrib. media abs. {G0}": a[grupo == G0].mean(axis=0)})
    t["razon"] = t.iloc[:, 1] / t.iloc[:, 2].replace(0, np.nan)
    return t


def top_union(t):
    c1, c0 = t.columns[1], t.columns[2]
    top1 = set(t.sort_values(c1, ascending=False).head(TOP_K)["variable"])
    top0 = set(t.sort_values(c0, ascending=False).head(TOP_K)["variable"])
    u = t[t["variable"].isin(top1 | top0)].copy()
    u["en top-10 de"] = [", ".join(g for g, s in ((G1, top1), (G0, top0)) if v in s) for v in u["variable"]]
    return u.sort_values("razon", ascending=False).reset_index(drop=True)


# ---------- 2c y 3. con y sin variables, varias semillas ----------
def metricas(model, df_va, df_te):
    thr = f3.threshold_at_fpr(df_va[f3.LABEL].values, model.score(df_va))
    y, s = df_te[f3.LABEL].values, model.score(df_te)
    pred, g = s >= thr, grupo_edad(df_te)

    def fpr(m):
        return float((pred[m] & (y[m] == 0)).sum() / (y[m] == 0).sum())
    f1, f0 = fpr(g == G1), fpr(g == G0)
    return {"AUC": roc_auc_score(y, s), "TPR": float((pred & (y == 1)).sum() / (y == 1).sum()),
            "FPR": fpr(np.ones(len(y), bool)), "FPR1": f1, "FPR0": f0, "razon": min(f1, f0) / max(f1, f0)}


class Evaluador:
    def __init__(self, df_tr, df_va, df_te, semillas):
        self.df_tr, self.df_va, self.df_te, self.semillas, self.cache = df_tr, df_va, df_te, semillas, {}

    def correr(self, quitar=()):
        key = tuple(sorted(quitar))
        if key not in self.cache:
            t0, filas = time.time(), []
            for sd in self.semillas:
                m = f3.train(self.df_tr.drop(columns=list(key)), self.df_va, seed=sd)
                filas.append({"semilla": sd, **metricas(m, self.df_va, self.df_te)})
            d = pd.DataFrame(filas)
            self.cache[key] = d
            print(f"  sin {list(key) or 'nada'}: AUC {d.AUC.mean():.4f} +- {d.AUC.std(ddof=1) if len(d) > 1 else 0:.4f} "
                  f"({time.time() - t0:.0f} s)")
        return self.cache[key]


def _sd(x):
    return x.std(ddof=1) if len(x) > 1 else 0.0


def tabla_config(ev, configs):
    base = ev.correr(())
    rows = []
    for nombre, quitar in configs:
        d = ev.correr(quitar)
        dauc = d["AUC"].values - base["AUC"].values
        rows.append({
            "modelo": nombre,
            "AUC": f"{d.AUC.mean():.4f} ± {_sd(d.AUC):.4f}",
            "cambio de AUC vs base (misma semilla)": "-" if not quitar else f"{dauc.mean():+.4f} ± {_sd(pd.Series(dauc)):.4f}",
            "TPR global": f"{100 * d.TPR.mean():.2f} ± {100 * _sd(d.TPR):.2f} %",
            f"FPR {G1}": f"{100 * d.FPR1.mean():.2f} ± {100 * _sd(d.FPR1):.2f} %",
            f"FPR {G0}": f"{100 * d.FPR0.mean():.2f} ± {100 * _sd(d.FPR0):.2f} %",
            "razon FPR (menor/mayor)": f"{d.razon.mean():.4f} ± {_sd(d.razon):.4f}"})
    return pd.DataFrame(rows)


# ---------- 3b. distribucion por mes ----------
def tabla_mes(df, col):
    rows = []
    for mes, d in df.groupby(f3.MONTH):
        x, y = d[col].astype(float), d[f3.LABEL]
        uso = "prueba" if mes in f3.TEST_MONTHS else ("valida" if mes == max(f3.TRAIN_MONTHS) else "entrena")
        rows.append({"mes": int(mes), "uso": uso, "n": len(d), "media": x.mean(), "sd": x.std(),
                     "p05": x.quantile(.05), "p50": x.quantile(.5), "p95": x.quantile(.95),
                     "tasa de fraude": pct(y.mean()),
                     "AUC de la variable sola": roc_auc_score(y, x) if y.nunique() == 2 else np.nan})
    tr = df.loc[df[f3.MONTH].isin(f3.TRAIN_MONTHS), col].astype(float)
    te = df.loc[df[f3.MONTH].isin(f3.TEST_MONTHS), col].astype(float)
    ks = stats.ks_2samp(tr, te)
    return pd.DataFrame(rows), ks.statistic, tr.mean(), te.mean(), tr.std(), te.std()


# ---------- 4. carga de alertas ----------
def carga_alertas(model, df_va, df_te):
    thr = f3.threshold_at_fpr(df_va[f3.LABEL].values, model.score(df_va))
    y, s = df_te[f3.LABEL].values, model.score(df_te)
    pred, grupo = s >= thr, grupo_edad(df_te)
    rows = []
    for g in (G1, G0):
        m = grupo == g
        rows.append({"grupo": g, "alertas por cada 100 solicitudes": 100 * pred[m].mean(),
                     "falsas alarmas por cada 100 honestas (FPR)": 100 * (pred[m] & (y[m] == 0)).sum() / (y[m] == 0).sum()})
    t = pd.DataFrame(rows)
    return t, t.iloc[0, 1:].values / t.iloc[1, 1:].values, thr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--semillas", type=int, default=5)
    ap.add_argument("--out", default="docs")
    a = ap.parse_args()
    if a.demo:
        print("*** DATOS SINTETICOS: no reportar estas cifras ***")
        df = demo_extra(f3.make_demo())
    elif a.data:
        df = f3.load_data(a.data)
    else:
        ap.error("usa --demo o --data")
    if f3.LABEL not in df.columns and "is_fraud" in df.columns:
        f3.LABEL = "is_fraud"
    df_tr, df_va, df_te = split_meses(df)
    print(f"entrenamiento={len(df_tr)} validacion={len(df_va)} prueba={len(df_te)}")
    semillas = list(range(SEMILLA_BASE, SEMILLA_BASE + a.semillas))

    model = f3.train(df_tr, df_va, seed=SEMILLA_BASE)
    y, s, grupo = df_te[f3.LABEL].values, model.score(df_te), grupo_edad(df_te)
    print(f"AUC base (semilla {SEMILLA_BASE}): {roc_auc_score(y, s):.4f} (corrida anterior con BAF Base: 0.8158)")

    feats = model.prep.features
    sospechosas = [c for c in feats if "age" in c.lower() or "birth" in c.lower()]
    o = ["# F3 - Analisis de equidad por edad (version 2)", "",
         ("**DATOS SINTETICOS (--demo): estas cifras no valen.**\n" if a.demo else ""),
         f"Conjunto: BAF Base, {len(df)} filas. Entrenan los meses {f3.TRAIN_MONTHS[:-1]}, valida el mes "
         f"{f3.TRAIN_MONTHS[-1]}, prueba los meses {f3.TEST_MONTHS}. Salvo indicacion, las cifras son del conjunto "
         f"de prueba. Grupo sensible: edad >= {f3.SENSITIVE_AGE}. Semillas: {semillas}.", "",
         "## Terminologia", "",
         "- **Igualdad de tasa de falsos positivos (razon FPR menor/mayor)** = FPR del grupo con menos falsas alarmas / "
         "FPR del grupo con mas. 1,0 = igual. No es paridad predictiva (precision).",
         "- **Falsas alarmas por 100 honestas** (= FPR): honestas marcadas como sospechosas / honestas, por 100.",
         "- **Alertas por 100 solicitudes**: solicitudes marcadas (fraudes bien detectados y falsas alarmas) / todas las "
         "solicitudes del grupo, por 100. Es una medida distinta de la anterior.", "",
         "## 0. Datos de prueba por grupo", md(tabla_prevalencia(y, grupo)), ""]

    # ---- 1 ----
    tablas, deciles = calibracion_grupo(y, s, grupo)
    o += ["## 1. Calibracion dentro de cada grupo (deciles del score dentro del grupo)",
          "n = solicitudes del decil; fraudes = fraudes observados; pred = probabilidad media predicha; "
          "obs = tasa de fraude observada con su IC 95 % de Wilson; pred/obs = 1 es calibrado. "
          "**SUBESTIMA** = la prediccion queda por debajo del IC 95 % de lo observado; "
          "**SOBREESTIMA** = por encima; compatible = dentro del IC.", ""]
    for g in (G1, G0):
        o += [f"### Grupo {g}", md(tablas[g], 3), "",
              f"Deciles donde el modelo **subestima**: {deciles[g]['subestima'] or 'ninguno'}. "
              f"Deciles donde **sobreestima**: {deciles[g]['sobreestima'] or 'ninguno'}.", ""]
    o += ["El promedio global predicho/observado de un grupo no basta para sacar conclusiones: "
          "hay que mirar las tablas por decil. Cada fila de las tablas anteriores usa deciles dentro del propio grupo; "
          "la tabla siguiente compara ambos grupos en los mismos rangos de score.", "",
          "### Mismos rangos de score para ambos grupos (tramos del score global; con empates salen menos de 10)",
          md(calibracion_comun(y, s, grupo)), ""]

    # ---- 2 ----
    o += ["## 2. Variables que podrian sustituir a la edad", "",
          f"- `{f3.AGE}` entre las variables del modelo: **{'SI (revisar!)' if f3.AGE in feats else 'no'}**.",
          f"- Variables con 'age' o 'birth' en el nombre: {sospechosas or 'ninguna'}.",
          "- En BAF la edad viene agrupada por decenas (10, 20, ..., 90) y no se publica la fecha de nacimiento; "
          "las variables categoricas (housing_status, employment_status, payment_type, source, device_os) son "
          "codigos anonimos sin orden. Por eso en las categoricas se usa **eta** (razon de correlacion, edad como "
          "numero) y **V de Cramer** (edad como categorias), no Pearson.", ""]
    corr = correlaciones(model, df_te)
    altas = corr[corr["abs"] >= R_UMBRAL]
    o += ["### 2a. Relacion de cada variable con la edad (prueba)",
          (f"Con |valor| >= {R_UMBRAL}: {', '.join(altas['variable'])}." if len(altas)
           else f"Ninguna llega a {R_UMBRAL}; maximo {corr.iloc[0]['abs']:.3f} ({corr.iloc[0]['variable']})."), "",
          md(corr[["variable", "tipo", "medida", "valor", "complementaria", "valor_compl"]].head(15), 3),
          "(15 con mayor |valor| de la medida principal)", ""]
    if VAR_DOB in df_te:
        o += [f"#### {VAR_DOB} frente a la edad (prueba)", md(relacion_dob(df_te), 3), ""]
    if VAR_HOUSING in df_te:
        o += [f"#### {VAR_HOUSING}: reparto de categorias por grupo (prueba)", md(relacion_housing(df_te, grupo)), ""]

    imp = importancia_grupo(model, df_te, grupo)
    u = top_union(imp)
    o += ["### 2b. Importancia por grupo (media del valor absoluto de la contribucion, escala log-odds, prueba)",
          f"Union de los top {TOP_K} de cada grupo, ordenada por la razon {G1}/{G0}.", "", md(u, 4), ""]

    # ---- 2c ----
    ev = Evaluador(df_tr, df_va, df_te, semillas)
    cand = [v for v in (VAR_DOB, VAR_HOUSING) if v in feats]
    cand += [v for v in corr.loc[corr["abs"] >= R_CANDIDATAS, "variable"] if v not in cand]
    print(f"Con y sin cada variable candidata {cand} ({len(semillas)} semillas cada una):")
    configs = [("base (sin la edad)", ())] + [(f"sin {v}", (v,)) for v in cand]
    o += ["### 2c. Con y sin cada variable candidata",
          f"Candidatas: {cand} (las dos nombradas por el equipo y las que tienen |valor| >= {R_CANDIDATAS}). "
          f"Cada fila reentrena {len(semillas)} veces (semillas distintas); media ± desviacion. "
          "El umbral se fija en validacion (FPR 5 %) en cada modelo. **No se elimina ninguna variable del modelo.**", "",
          md(tabla_config(ev, configs)), ""]

    # ---- 3 ----
    if VAR_CREDIT in feats:
        quitar3 = tuple(v for v in (VAR_DOB, VAR_CARDS, VAR_CREDIT) if v in feats)
        print("credit_risk_score:")
        configs3 = [("base (sin la edad)", ()), (f"sin {VAR_CREDIT}", (VAR_CREDIT,)),
                    (f"sin {VAR_DOB}", (VAR_DOB,)), (f"sin {', '.join(quitar3)}", quitar3)]
        o += ["## 3. credit_risk_score", "",
              f"### 3a. Con y sin la variable, {len(semillas)} semillas",
              "Incluye la combinacion de la corrida anterior, donde el AUC subio a 0,838.", "",
              md(tabla_config(ev, configs3)), "",
              "### 3b. Distribucion por mes (todo el conjunto)",
              "'AUC de la variable sola' usa la variable como puntuacion: valores por debajo de 0,5 significan que "
              "valores altos se asocian con MENOS fraude. Si cambia mucho entre meses de entrenamiento y de prueba, "
              "la variable perdio o cambio su relacion con el fraude.", ""]
        for v in [VAR_CREDIT] + ([VAR_DOB] if VAR_DOB in df else []):
            t, ks, mtr, mte, str_, ste = tabla_mes(df, v)
            o += [f"#### {v}", md(t, 3), "",
                  f"Entrenamiento (meses {f3.TRAIN_MONTHS[0]}-{f3.TRAIN_MONTHS[-1]}) frente a prueba "
                  f"(meses {f3.TEST_MONTHS[0]}-{f3.TEST_MONTHS[-1]}): media {mtr:.3f} frente a {mte:.3f}, "
                  f"desviacion {str_:.3f} frente a {ste:.3f}, estadistico KS = {ks:.3f} (0 = misma distribucion).", ""]

    # ---- 4 ----
    ca, r, thr = carga_alertas(model, df_va, df_te)
    o += ["## 4. Carga de alertas por grupo (modelo base)", f"Umbral: {thr:.4f}.", "", md(ca, 2), "",
          f"Razon {G1} / {G0}: **{r[0]:.2f} veces** en alertas por 100 solicitudes; "
          f"**{r[1]:.2f} veces** en falsas alarmas por 100 honestas. Son medidas distintas y se nombran por separado.", "",
          "## Limites", "",
          "- Una sola particion temporal (meses 0-5 / 6-7) y un solo conjunto de datos.",
          "- BAF es un conjunto sintetico (generado con una GAN a partir de datos reales anonimizados). "
          "Segun el paper de BAF, en los datos originales la prevalencia de fraude es mayor en solicitantes mayores; "
          "verificar la cita exacta antes de usarla.",
          "- Calibrar bien por grupo no demuestra por si solo la causa de la diferencia de falsas alarmas.",
          "- No se implemento ningun umbral ni verificacion por edad."]

    os.makedirs(a.out, exist_ok=True)
    ruta = os.path.join(a.out, "f3_analisis_equidad.md")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write("\n".join(o))
    print("\n".join(o))
    print(f"\nEscrito: {ruta}")


if __name__ == "__main__":
    main()
