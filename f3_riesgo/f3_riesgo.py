"""F3 - Riesgo de la solicitud (TrustGate Z).

Entrena LightGBM con Bank Account Fraud (BAF), calcula risk_score y top_factors,
mide equidad por edad y genera la prueba de paridad PC vs servidor (s390x).

Uso:
  python f3_riesgo.py --demo                      # prueba con datos SINTETICOS
  python f3_riesgo.py --data ruta/Base.csv        # entrenamiento real (csv o parquet)
  python f3_riesgo.py --parity --out f3_out       # puntua parity_rows.csv con el modelo guardado

IMPORTANTE: --demo solo comprueba que el codigo corre. No reportar sus metricas.
Confirmar en el datasheet de BAF: nombres de columnas, meses de entrenamiento/prueba
y cuales columnas usan -1 como valor faltante.
"""
import argparse
import glob
import json
import os
import platform

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss, roc_auc_score, roc_curve

# ---- Configuracion (ajustar con el datasheet) ----
LABEL = "fraud_bool"
MONTH = "month"
AGE = "customer_age"
SENSITIVE_AGE = 50                 # grupo sensible: 50 anios o mas
TRAIN_MONTHS = [0, 1, 2, 3, 4, 5]  # paper BAF: 6 primeros meses entrenan; el ultimo (5) valida
TEST_MONTHS = [6, 7]               # paper BAF: los 2 ultimos meses prueban
TARGET_FPR = 0.05                  # umbral global fijado a 5 % de falsos positivos
USE_AGE_AS_FEATURE = False         # por defecto el modelo NO ve la edad
MISSING_MINUS_ONE = [              # columnas donde -1 significa "sin dato" (revisado en Base.csv)
    "prev_address_months_count", "current_address_months_count",
    "bank_months_count", "session_length_in_minutes", "device_distinct_emails_8w",
]
CATEGORICAL = ["payment_type", "employment_status", "housing_status", "source", "device_os"]
MODEL_VERSION = "f3-lgbm-0.2"


# ---- Preprocesamiento ----
class Prep:
    """Guarda columnas y categorias del entrenamiento para aplicarlas igual despues."""

    def fit(self, df):
        self.cat_levels = {c: sorted(df[c].astype(str).unique()) for c in CATEGORICAL if c in df}
        drop = {LABEL, MONTH} | (set() if USE_AGE_AS_FEATURE else {AGE})
        self.features = [c for c in df.columns if c not in drop]
        return self

    def transform(self, df):
        X = df[self.features].copy()
        for c in MISSING_MINUS_ONE:
            if c in X:
                X[c] = X[c].where(X[c] != -1, np.nan)
        for c, levels in self.cat_levels.items():
            X[c] = pd.Categorical(X[c].astype(str), categories=levels)
        return X

    def to_json(self):
        return {"features": self.features, "cat_levels": self.cat_levels}

    @classmethod
    def from_json(cls, d):
        p = cls()
        p.features, p.cat_levels = d["features"], d["cat_levels"]
        return p


# ---- Modelo ----
class F3Model:
    def __init__(self, prep, booster):
        self.prep, self.booster = prep, booster

    def score(self, df):
        """Probabilidad de fraude (0 a 1) por fila."""
        return self.booster.predict(self.prep.transform(df))

    def top_factors(self, df, k=3):
        """Los k factores que mas empujan cada puntuacion (pred_contrib de LightGBM)."""
        X = self.prep.transform(df)
        contrib = self.booster.predict(X, pred_contrib=True)  # ultima columna = sesgo base
        names, out = list(X.columns), []
        for row in contrib:
            c = row[:-1]
            idx = np.argsort(-np.abs(c))[:k]
            out.append([{"feature": names[i], "contribution": round(float(c[i]), 4),
                         "effect": "sube_riesgo" if c[i] > 0 else "baja_riesgo"} for i in idx])
        return out

    def score_application(self, row: dict):
        """Salida de F3. Formato provisional: ajustar al contrato de schemas/ de Yael."""
        df = pd.DataFrame([row])
        return {"risk_score": float(self.score(df)[0]),
                "top_factors": self.top_factors(df)[0],
                "model_version": MODEL_VERSION}

    def save(self, out):
        os.makedirs(out, exist_ok=True)
        self.booster.save_model(os.path.join(out, "f3_model.txt"))  # formato de texto, portable
        with open(os.path.join(out, "f3_prep.json"), "w") as f:
            json.dump(self.prep.to_json(), f)

    @classmethod
    def load(cls, out):
        with open(os.path.join(out, "f3_prep.json")) as f:
            prep = Prep.from_json(json.load(f))
        return cls(prep, lgb.Booster(model_file=os.path.join(out, "f3_model.txt")))


def train(df_tr, df_va, seed=42):
    prep = Prep().fit(df_tr)
    X_tr, X_va = prep.transform(df_tr), prep.transform(df_va)
    y_tr, y_va = df_tr[LABEL].values, df_va[LABEL].values
    pos = max(int(y_tr.sum()), 1)
    # Raiz cuadrada del peso completo: compensa el desbalance sin distorsionar tanto la calibracion
    spw = float(np.sqrt((len(y_tr) - pos) / pos))
    clf = lgb.LGBMClassifier(n_estimators=500, learning_rate=0.05, num_leaves=31,
                             subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                             scale_pos_weight=spw, random_state=seed, n_jobs=2, verbose=-1)
    clf.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], eval_metric="auc",
            callbacks=[lgb.early_stopping(50, verbose=False)])
    return F3Model(prep, clf.booster_)


# ---- Evaluacion y equidad ----
def threshold_at_fpr(y, s, fpr=TARGET_FPR):
    f, _, th = roc_curve(y, s)
    idx = max(np.searchsorted(f, fpr, side="right") - 1, 1)  # 0 seria el umbral infinito
    return float(th[idx])


def group_metrics(y, s, thr, group):
    rows = []
    for g in sorted(pd.unique(group)):
        m = group == g
        yg, pred = y[m], s[m] >= thr
        neg, pos = int((yg == 0).sum()), int((yg == 1).sum())
        rows.append({"grupo": g, "n": int(m.sum()), "fraudes": pos,
                     "fpr": float((pred & (yg == 0)).sum() / neg) if neg else np.nan,
                     "tpr": float((pred & (yg == 1)).sum() / pos) if pos else np.nan,
                     "tasa_alertas": float(pred.mean())})
    return pd.DataFrame(rows)


def evaluate(model, df_val, df_test):
    thr = threshold_at_fpr(df_val[LABEL].values, model.score(df_val))  # umbral fijado en validacion
    y, s = df_test[LABEL].values, model.score(df_test)
    grupo = np.where(df_test[AGE].values >= SENSITIVE_AGE, f"{SENSITIVE_AGE}+", f"<{SENSITIVE_AGE}")
    print(f"AUC prueba: {roc_auc_score(y, s):.4f} | umbral (FPR {TARGET_FPR:.0%} en validacion): {thr:.4f}")
    pred = s >= thr
    print(f"Global en prueba: TPR {(pred & (y == 1)).sum() / max((y == 1).sum(), 1):.4f} "
          f"a FPR {(pred & (y == 0)).sum() / max((y == 0).sum(), 1):.4f} "
          f"(el paper de BAF reporta TPR a FPR fijo de 5 %)")
    print("Equidad por edad (mismo umbral para todos):")
    gm = group_metrics(y, s, thr, grupo)
    print(gm.round(4).to_string(index=False))
    fprs = gm["fpr"].dropna()
    if len(fprs) == 2 and fprs.max() > 0:
        print(f"Igualdad predictiva (FPR menor / FPR mayor): {fprs.min() / fprs.max():.3f} "
              f"(1.0 = igual; es la metrica de equidad del paper de BAF)")
    frac, mean_pred = calibration_curve(y, s, n_bins=10, strategy="quantile")
    print(f"Brier: {brier_score_loss(y, s):.4f} | calibracion (predicho -> observado):")
    for a, b in zip(mean_pred, frac):
        print(f"  {a:.3f} -> {b:.3f}")


# ---- Datos ----
def load_data(path):
    return pd.read_parquet(path) if path.endswith(".parquet") else pd.read_csv(path)


def make_demo(n=20000, seed=0):
    """Datos SINTETICOS genericos (no imitan BAF). Solo para probar que el codigo corre."""
    r = np.random.default_rng(seed)
    df = pd.DataFrame({
        MONTH: r.integers(0, 8, n),
        AGE: r.choice([10, 20, 30, 40, 50, 60, 70, 80], n),
        "income": r.random(n),
        "name_email_similarity": r.random(n),
        "credit_risk_score": r.normal(100, 50, n),
        "prev_address_months_count": np.where(r.random(n) < 0.3, -1, r.integers(0, 200, n)),
        "payment_type": r.choice(list("ABCD"), n),
        "employment_status": r.choice(list("EFG"), n),
        "device_os": r.choice(["windows", "linux", "other"], n),
    })
    z = -5 + 2.0 * (df.name_email_similarity < 0.2) + 0.01 * df.credit_risk_score
    df[LABEL] = (r.random(n) < 1 / (1 + np.exp(-z))).astype(int)
    return df


# ---- Paridad PC vs servidor ----
def parity(out):
    model = F3Model.load(out)
    rows = pd.read_csv(os.path.join(out, "parity_rows.csv"))
    scores = np.round(model.score(rows), 8)
    path = os.path.join(out, f"parity_scores_{platform.machine()}.csv")
    pd.DataFrame({"i": range(len(scores)), "score": scores}).to_csv(path, index=False)
    print("Escrito:", path)
    files = sorted(glob.glob(os.path.join(out, "parity_scores_*.csv")))
    if len(files) >= 2:
        base = pd.read_csv(files[0])["score"].values
        for f in files[1:]:
            d = np.abs(base - pd.read_csv(f)["score"].values).max()
            print(f"Diferencia maxima {os.path.basename(files[0])} vs {os.path.basename(f)}: {d:.2e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--parity", action="store_true")
    ap.add_argument("--sample", type=int, help="filas aprox. de una muestra estratificada por mes y etiqueta")
    ap.add_argument("--out", default="f3_out")
    a = ap.parse_args()
    global LABEL

    if a.parity:
        return parity(a.out)
    if a.demo:
        print("*** DATOS SINTETICOS: no reportar estas metricas ***")
        df = make_demo()
    elif a.data:
        df = load_data(a.data)
    else:
        ap.error("usa --demo o --data")

    if LABEL not in df.columns and "is_fraud" in df.columns:   # el paper la llama is_fraud
        LABEL = "is_fraud"
    for c in (LABEL, MONTH, AGE):
        if c not in df.columns:
            raise SystemExit(f"Falta la columna '{c}'. Columnas del archivo: {list(df.columns)}")
    print(f"Etiqueta: {LABEL} | tasa de fraude: {df[LABEL].mean():.3%} | filas: {len(df)}")
    if a.sample and len(df) > a.sample:
        df = df.groupby([MONTH, LABEL]).sample(frac=a.sample / len(df), random_state=42)
        print(f"Muestra estratificada: {len(df)} filas | tasa de fraude: {df[LABEL].mean():.3%}")

    last_train = max(TRAIN_MONTHS)
    df_tr = df[df[MONTH].isin(TRAIN_MONTHS) & (df[MONTH] != last_train)]
    df_va = df[df[MONTH] == last_train]
    df_te = df[df[MONTH].isin(TEST_MONTHS)]
    print(f"entrenamiento={len(df_tr)} validacion={len(df_va)} prueba={len(df_te)}")

    model = train(df_tr, df_va)
    evaluate(model, df_va, df_te)

    model.save(a.out)
    df_te.head(100).to_csv(os.path.join(a.out, "parity_rows.csv"), index=False)
    ejemplo = model.score_application(df_te.iloc[0].to_dict())
    print("Ejemplo de salida:", json.dumps(ejemplo, ensure_ascii=False))
    parity(a.out)


if __name__ == "__main__":
    main()
