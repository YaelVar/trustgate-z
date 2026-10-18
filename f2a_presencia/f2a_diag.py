"""Diagnostico de F2a: compara formas de puntuar 'parece rostro' sobre los rasgos ya guardados (f2a_rasgos.npz).
Uso: python f2a_diag.py f2a_out/f2a_rasgos.npz"""
import sys, numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.svm import OneClassSVM
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics import roc_auc_score

d = np.load(sys.argv[1], allow_pickle=True)
X_tr, X_ub, X_tp, X_fc, X_fr = (d[k] for k in ("X_tr", "X_ub", "X_tp", "X_fc", "X_fr"))
n_cel = int(d["n_tr_cel"])
print(f"train {X_tr.shape} (celeba {n_cel}) | tex umbral {X_ub.shape} | tex prueba {X_tp.shape} | cara celeba {X_fc.shape} | cara rvf {X_fr.shape}")
print(f"HOG medio: train {X_tr.mean():.4f} | texturas {np.vstack([X_ub, X_tp]).mean():.4f} | celeba(prueba) {X_fc.mean():.4f} | rvf(prueba) {X_fr.mean():.4f}")

def evalua(nombre, f):
    """f(X)->score (mayor = mas rostro). Umbral: 5 % de las texturas de umbral aceptadas."""
    s_ub, s_tp, s_fc, s_fr, s_tr = f(X_ub), f(X_tp), f(X_fc), f(X_fr), f(X_tr)
    thr = np.quantile(s_ub, 0.95, method="higher")
    caras = np.r_[s_fc, s_fr]; tex = np.r_[s_ub, s_tp]
    auc = roc_auc_score(np.r_[np.ones(len(caras)), np.zeros(len(tex))], np.r_[caras, tex])
    print(f"{nombre:<34} AUC {auc:.3f} | FP tex prueba {100*(s_tp>thr).mean():5.1f} % | FN celeba {100*(s_fc<=thr).mean():5.1f} % | "
          f"FN rvf {100*(s_fr<=thr).mean():5.1f} % | train aceptado {100*(s_tr>thr).mean():5.1f} %")

sc = StandardScaler().fit(X_tr)
for k in (20, 50, 100):
    pca = PCA(n_components=k, random_state=42).fit(sc.transform(X_tr))
    Z = lambda X: pca.transform(sc.transform(X))
    for g in (0.3, 1, 3):
        for nu in (0.05,):
            m = OneClassSVM(kernel="rbf", gamma="scale", nu=nu)
            Ztr = Z(X_tr); gs = 1 / (k * Ztr.var()); m.set_params(gamma=gs * g).fit(Ztr)
            evalua(f"OCSVM pca{k} gamma x{g}", lambda X, m=m, Z=Z: m.decision_function(Z(X)))
    ev = pca.explained_variance_
    evalua(f"Mahalanobis pca{k}", lambda X, Z=Z, ev=ev: -(Z(X) ** 2 / ev).sum(1))
    evalua(f"Error reconstruccion pca{k}", lambda X, pca=pca: -((sc.transform(X) - pca.inverse_transform(pca.transform(sc.transform(X)))) ** 2).sum(1))
    nn = NearestNeighbors(n_neighbors=5).fit(Z(X_tr))
    evalua(f"kNN(5) pca{k}", lambda X, nn=nn, Z=Z: -nn.kneighbors(Z(X), n_neighbors=5)[0].mean(1))
# HOG sin estandarizar
for k in (50,):
    pca = PCA(n_components=k, random_state=42).fit(X_tr)
    nn = NearestNeighbors(n_neighbors=5).fit(pca.transform(X_tr))
    evalua(f"kNN(5) HOG crudo pca{k}", lambda X, nn=nn, pca=pca: -nn.kneighbors(pca.transform(X), n_neighbors=5)[0].mean(1))
    m = OneClassSVM(kernel="rbf", gamma="scale", nu=0.05).fit(pca.transform(X_tr))
    evalua(f"OCSVM HOG crudo pca{k}", lambda X, m=m, pca=pca: m.decision_function(pca.transform(X)))
