"""F2a alternativa: clasificador de dos clases (rostros vs texturas), evaluado en FAMILIAS de textura no vistas.
Entrena: rostros (X_tr) + texturas del grupo de umbral (X_ub). Las texturas de prueba (X_tp, otras familias) se parten por familia
en 'umbral' y 'prueba' (5 particiones). Uso: python f2a_diag2.py f2a_out/f2a_rasgos.npz"""
import sys, re, os, numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import roc_auc_score
import lightgbm as lgb

d = np.load(sys.argv[1], allow_pickle=True)
X_tr, X_ub, X_tp, X_fc, X_fr = (d[k] for k in ("X_tr", "X_ub", "X_tp", "X_fc", "X_fr"))
fam = np.array([re.match(r"[A-Za-z]+", os.path.basename(p)).group(0) for p in d["p_tp"]])
X = np.vstack([X_tr, X_ub]); y = np.r_[np.ones(len(X_tr)), np.zeros(len(X_ub))]
print(f"entrena: {len(X_tr)} rostros + {len(X_ub)} texturas | prueba: {len(X_tp)} texturas ({len(set(fam))} familias), caras {len(X_fc)}+{len(X_fr)}")

def modelos():
    sc = StandardScaler().fit(X); pca = PCA(100, random_state=42).fit(sc.transform(X))
    lr = LogisticRegression(C=0.1, max_iter=2000, class_weight="balanced").fit(pca.transform(sc.transform(X)), y)
    gb = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31, subsample=0.8, subsample_freq=1,
                            colsample_bytree=0.5, class_weight="balanced", random_state=42, verbose=-1).fit(X, y)
    return {"Regresion logistica (PCA100)": lambda Z: lr.decision_function(pca.transform(sc.transform(Z))),
            "LightGBM (HOG crudo)": lambda Z: gb.predict_proba(Z)[:, 1]}

for nombre, f in modelos().items():
    s_tp, s_fc, s_fr = f(X_tp), f(X_fc), f(X_fr)
    filas = []
    for seed in range(5):
        iu, ip = next(GroupShuffleSplit(1, test_size=0.5, random_state=seed).split(X_tp, groups=fam))
        thr = np.quantile(s_tp[iu], 0.95, method="higher")
        filas.append(((s_tp[ip] > thr).mean(), (s_fc <= thr).mean(), (s_fr <= thr).mean(),
                      roc_auc_score(np.r_[np.ones(len(s_fc) + len(s_fr)), np.zeros(len(ip))], np.r_[s_fc, s_fr, s_tp[ip]])))
    a = np.array(filas) * 100; a[:, 3] /= 100
    print(f"{nombre:<30} FP texturas {a[:,0].mean():4.1f} +- {a[:,0].std():3.1f} % | FN CelebA {a[:,1].mean():5.1f} +- {a[:,1].std():3.1f} % | "
          f"FN RvF {a[:,2].mean():5.1f} +- {a[:,2].std():3.1f} % | AUC {a[:,3].mean():.3f}")
