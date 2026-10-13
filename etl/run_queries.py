#!/usr/bin/env python3
"""
Executa localmente as consultas de sql/consultas_dashboard.sql sobre as tabelas gold.

Faz o papel do Amazon Athena no projeto: carrega gold_pedidos e gold_pagamentos num banco
SQLite em memória (já vem com o Python, não precisa instalar nada), roda cada consulta,
imprime o resultado e salva um CSV por consulta em outputs/resultados_sql/.

Uso:
    python etl/run_queries.py
"""
import argparse
import re
import sqlite3
from pathlib import Path

import pandas as pd


def ler_consultas(caminho):
    """Separa o arquivo .sql em {nome: comando} usando os marcadores '-- name: xxx'."""
    texto = Path(caminho).read_text(encoding="utf-8")
    partes = re.split(r"^-- name:\s*(\S+)\s*$", texto, flags=re.M)
    consultas = {}
    for nome, corpo in zip(partes[1::2], partes[2::2]):
        linhas = [l for l in corpo.splitlines() if not l.strip().startswith("--")]
        consultas[nome] = "\n".join(linhas).strip().rstrip(";")
    return consultas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default="data/gold")
    ap.add_argument("--sql", default="sql/consultas_dashboard.sql")
    ap.add_argument("--out", default="outputs/resultados_sql")
    a = ap.parse_args()

    con = sqlite3.connect(":memory:")
    for tabela in ["gold_pedidos", "gold_pagamentos"]:
        df = pd.read_csv(Path(a.gold) / f"{tabela}.csv")
        df.to_sql(tabela, con, index=False)
        print(f"[carga] {tabela}: {len(df):,} linhas")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 160)
    for nome, sql in ler_consultas(a.sql).items():
        res = pd.read_sql_query(sql, con)
        res.to_csv(out / f"{nome}.csv", index=False)
        print(f"\n=== {nome} ({len(res)} linhas) ===")
        print(res.to_string(index=False))


if __name__ == "__main__":
    main()
