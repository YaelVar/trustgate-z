"""Revisa el archivo base de Bank Account Fraud (BAF) antes de subirlo a la VM.

Uso:
  python revisar_baf.py C:\\datasets\\bank-account-fraud\\Base.csv
  python revisar_baf.py Base.csv --muestra 200000 --salida baf_muestra.csv

Imprime: tamano, columnas, columna de fraude y su tasa, filas por mes, valores de edad,
tasa de fraude por grupo de edad y columnas con -1 (posible "sin dato").
Con --muestra y --salida guarda una muestra estratificada por mes y etiqueta.
No subir estos archivos a GitHub (licencia CC BY-NC-SA 4.0).
"""
import argparse

import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ruta")
    ap.add_argument("--muestra", type=int, help="filas aproximadas de la muestra")
    ap.add_argument("--salida", help="CSV de salida para la muestra")
    a = ap.parse_args()

    df = pd.read_parquet(a.ruta) if a.ruta.endswith(".parquet") else pd.read_csv(a.ruta)
    print("filas, columnas:", df.shape)
    print("columnas:", list(df.columns))
    label = next((c for c in ("fraud_bool", "is_fraud") if c in df), None)
    print("columna de fraude:", label)
    if label:
        print(f"tasa de fraude: {df[label].mean():.3%}")
    if "month" in df:
        print("filas por mes:", df["month"].value_counts().sort_index().to_dict())
    if "customer_age" in df:
        print("valores de edad:", df["customer_age"].value_counts().sort_index().to_dict())
        mayor = df["customer_age"] >= 50
        print(f"grupo 50+: {mayor.mean():.1%} de las filas")
        if label:
            print(f"tasa de fraude 50+: {df.loc[mayor, label].mean():.3%} | "
                  f"menores de 50: {df.loc[~mayor, label].mean():.3%}")
    num = df.select_dtypes("number")
    menos1 = (num == -1).sum()
    print("columnas con valores -1 (posible 'sin dato'):", menos1[menos1 > 0].to_dict())
    nulos = df.isna().sum()
    print("columnas con nulos:", nulos[nulos > 0].to_dict())

    if a.muestra and a.salida:
        if not (label and "month" in df):
            raise SystemExit("No puedo estratificar: faltan la columna de fraude o 'month'.")
        frac = min(1.0, a.muestra / len(df))
        m = df.groupby(["month", label]).sample(frac=frac, random_state=42)
        m.to_csv(a.salida, index=False)
        print(f"muestra guardada: {len(m)} filas, fraude {m[label].mean():.3%} -> {a.salida}")


if __name__ == "__main__":
    main()
