#!/usr/bin/env python3
"""
ETL local da base Olist  (equivalente ao job do AWS Glue do projeto)

    raw (CSV do Kaggle)  ->  silver (limpo, tipado)  ->  gold (pronto p/ consulta)

Uso:
    python etl/etl_olist.py --raw data/raw --out data

Camadas
  raw    : os 9 CSVs originais, sem alteração (no projeto, ficariam no S3)
  silver : cada tabela limpa (tipos, texto padronizado, duplicados, tradução de categorias)
  gold   : tabelas analíticas do dashboard "Visão Financeira e Comportamento de Pagamentos"
             - gold_pagamentos : 1 linha por pagamento
             - gold_pedidos    : 1 linha por pedido (receita, parcelas, flag de cartão)

Também gera docs/relatorio_qualidade.md com contagens, regras aplicadas e conciliação.
"""
import argparse
from pathlib import Path

import pandas as pd

try:
    import pyarrow  # noqa: F401
    HAS_PARQUET = True
except ImportError:
    HAS_PARQUET = False

ARQUIVOS = {
    "orders": "olist_orders_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "items": "olist_order_items_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "translation": "product_category_name_translation.csv",
}

report = []   # regras de limpeza aplicadas (vão para o relatório)
stats = []    # (tabela, linhas_raw, linhas_silver)


def log(msg=""):
    print(msg)


def salvar(df, pasta, nome, forcar_csv=False):
    """Silver: Parquet se houver pyarrow, senão CSV. Gold: sempre CSV (+ Parquet se houver)."""
    pasta.mkdir(parents=True, exist_ok=True)
    if HAS_PARQUET:
        df.to_parquet(pasta / f"{nome}.parquet", index=False)
    if forcar_csv or not HAS_PARQUET:
        df.to_csv(pasta / f"{nome}.csv", index=False)


# --------------------------------------------------------------------------- #
# 1) EXTRACT (raw)
# --------------------------------------------------------------------------- #
def extract(raw_dir):
    zips = {
        "customers": ["customer_zip_code_prefix"],
        "sellers": ["seller_zip_code_prefix"],
        "geolocation": ["geolocation_zip_code_prefix"],
    }
    dfs = {}
    for chave, arq in ARQUIVOS.items():
        caminho = raw_dir / arq
        if not caminho.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
        dtype = {c: str for c in zips.get(chave, [])}   # CEP como texto (preserva zeros à esquerda)
        dfs[chave] = pd.read_csv(caminho, dtype=dtype)
        log(f"[raw] {arq:45s} {len(dfs[chave]):>9,} linhas")
    return dfs


# --------------------------------------------------------------------------- #
# 2) TRANSFORM -> SILVER
# --------------------------------------------------------------------------- #
def limpa_texto(s):
    return s.astype("string").str.strip().str.lower()


def silver_orders(o):
    n0 = len(o)
    o = o.drop_duplicates("order_id").copy()
    cols_data = ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
                 "order_delivered_customer_date", "order_estimated_delivery_date"]
    for c in cols_data:
        o[c] = pd.to_datetime(o[c], errors="coerce")
    sem_data = int(o["order_purchase_timestamp"].isna().sum())
    o = o.dropna(subset=["order_purchase_timestamp"])
    o["order_status"] = limpa_texto(o["order_status"])
    ts = o["order_purchase_timestamp"]
    o["data_pedido"] = ts.dt.strftime("%Y-%m-%d")
    o["ano"] = ts.dt.year.astype(int)
    o["mes"] = ts.dt.month.astype(int)
    o["ano_mes"] = ts.dt.strftime("%Y-%m")
    report.append(f"- orders: {n0 - len(o)} linhas removidas (duplicadas ou sem data de compra: {sem_data}).")
    return o


def silver_customers(c):
    c = c.drop_duplicates("customer_id").copy()
    c["customer_city"] = limpa_texto(c["customer_city"])
    c["customer_state"] = c["customer_state"].astype("string").str.strip().str.upper()
    c["customer_zip_code_prefix"] = c["customer_zip_code_prefix"].str.zfill(5)
    return c


def silver_payments(p):
    n0 = len(p)
    p = p.drop_duplicates(["order_id", "payment_sequential"]).copy()
    n_dup = n0 - len(p)
    p["payment_type"] = limpa_texto(p["payment_type"])
    # Regra 1: parcelas = 0 é inválido -> assume pagamento à vista (1x)
    parcelas_zero = int((p["payment_installments"] < 1).sum())
    p.loc[p["payment_installments"] < 1, "payment_installments"] = 1
    # Regra 2: método 'not_defined' ou valor <= 0 não representam receita -> removidos
    invalidos = (p["payment_type"] == "not_defined") | (p["payment_value"] <= 0)
    n_inv = int(invalidos.sum())
    valor_inv = float(p.loc[invalidos, "payment_value"].sum())
    p = p[~invalidos]
    report.append(f"- payments: {parcelas_zero} pagamentos com 0 parcelas ajustados para 1x (pagamento à vista).")
    report.append(f"- payments: {n_inv} pagamentos removidos (método 'not_defined' ou valor <= 0; "
                  f"soma removida = R$ {valor_inv:,.2f}). Duplicados removidos: {n_dup}.")
    return p


def silver_items(i):
    i = i.drop_duplicates(["order_id", "order_item_id"]).copy()
    i["shipping_limit_date"] = pd.to_datetime(i["shipping_limit_date"], errors="coerce")
    i["valor_item_com_frete"] = (i["price"] + i["freight_value"]).round(2)
    return i


def silver_products(p, trad):
    p = p.drop_duplicates("product_id").copy()
    # corrige o erro de grafia do dataset original ('lenght')
    p = p.rename(columns={"product_name_lenght": "product_name_length",
                          "product_description_lenght": "product_description_length"})
    p = p.merge(trad, on="product_category_name", how="left")
    sem_cat = int(p["product_category_name"].isna().sum())
    p["product_category_name"] = p["product_category_name"].fillna("sem_categoria")
    # categorias sem tradução ficam com o nome em português
    p["product_category_name_english"] = (p["product_category_name_english"]
                                          .fillna(p["product_category_name"]))
    report.append(f"- products: {sem_cat} produtos sem categoria -> 'sem_categoria'; colunas com 'lenght' renomeadas para 'length'.")
    return p


def silver_sellers(s):
    s = s.drop_duplicates("seller_id").copy()
    s["seller_city"] = limpa_texto(s["seller_city"])
    s["seller_state"] = s["seller_state"].astype("string").str.strip().str.upper()
    s["seller_zip_code_prefix"] = s["seller_zip_code_prefix"].str.zfill(5)
    return s


def silver_reviews(r):
    n0 = len(r)
    r = r.copy()
    for c in ["review_creation_date", "review_answer_timestamp"]:
        r[c] = pd.to_datetime(r[c], errors="coerce")
    r = r[r["review_score"].between(1, 5)]
    r = r.drop_duplicates(["review_id", "order_id"], keep="last")
    report.append(f"- reviews: {n0 - len(r)} linhas removidas (duplicadas ou nota fora de 1-5).")
    return r


def silver_geolocation(g):
    # o raw tem ~1 milhão de linhas, várias por CEP -> 1 linha por prefixo de CEP
    g = g.copy()
    g["geolocation_zip_code_prefix"] = g["geolocation_zip_code_prefix"].str.zfill(5)
    g["geolocation_city"] = limpa_texto(g["geolocation_city"])
    g["geolocation_state"] = g["geolocation_state"].astype("string").str.strip().str.upper()

    def moda(s):
        return s.mode().iat[0]

    out = (g.groupby("geolocation_zip_code_prefix", as_index=False)
             .agg(lat=("geolocation_lat", "mean"), lng=("geolocation_lng", "mean"),
                  cidade=("geolocation_city", moda), uf=("geolocation_state", moda)))
    report.append("- geolocation: consolidada em 1 linha por prefixo de CEP (média de lat/lng; cidade e UF mais frequentes).")
    return out


# --------------------------------------------------------------------------- #
# 3) GOLD
# --------------------------------------------------------------------------- #
def build_gold(silver):
    o, c, p = silver["orders"], silver["customers"], silver["payments"]

    base = (p.merge(o[["order_id", "customer_id", "order_status", "data_pedido", "ano", "mes", "ano_mes"]],
                    on="order_id", how="inner")
              .merge(c[["customer_id", "customer_state", "customer_city"]], on="customer_id", how="left"))

    gp = base.rename(columns={
        "payment_sequential": "sequencial_pagamento", "payment_type": "metodo_pagamento",
        "payment_installments": "parcelas", "payment_value": "valor_pagamento",
        "order_status": "status_pedido", "customer_state": "uf_cliente", "customer_city": "cidade_cliente",
    })[["order_id", "sequencial_pagamento", "metodo_pagamento", "parcelas", "valor_pagamento",
        "data_pedido", "ano", "mes", "ano_mes", "status_pedido", "uf_cliente", "cidade_cliente"]]
    gp = gp.sort_values(["data_pedido", "order_id", "sequencial_pagamento"]).reset_index(drop=True)

    # --- gold_pedidos: 1 linha por pedido ---------------------------------
    gp["_cartao"] = (gp["metodo_pagamento"] == "credit_card").astype(int)
    agg = gp.groupby("order_id", as_index=False).agg(
        valor_total=("valor_pagamento", "sum"),
        qtd_pagamentos=("sequencial_pagamento", "count"),
        max_parcelas=("parcelas", "max"),
        flag_cartao_credito=("_cartao", "max"),
    )
    agg["valor_total"] = agg["valor_total"].round(2)
    principal = (gp.sort_values(["order_id", "valor_pagamento"], ascending=[True, False])
                   .drop_duplicates("order_id")[["order_id", "metodo_pagamento"]]
                   .rename(columns={"metodo_pagamento": "metodo_principal"}))
    dims = gp.drop_duplicates("order_id")[["order_id", "data_pedido", "ano", "mes", "ano_mes",
                                           "status_pedido", "uf_cliente", "cidade_cliente"]]
    gpe = (agg.merge(principal, on="order_id").merge(dims, on="order_id")
              [["order_id", "data_pedido", "ano", "mes", "ano_mes", "status_pedido", "uf_cliente",
                "cidade_cliente", "valor_total", "qtd_pagamentos", "max_parcelas",
                "metodo_principal", "flag_cartao_credito"]]
              .sort_values(["data_pedido", "order_id"]).reset_index(drop=True))
    gp = gp.drop(columns="_cartao")
    return gp, gpe


# --------------------------------------------------------------------------- #
# 4) VALIDAÇÕES E RELATÓRIO
# --------------------------------------------------------------------------- #
def validar_e_relatar(silver, gp, gpe, out_docs):
    erros = []
    soma_silver = round(silver["payments"]["payment_value"].sum(), 2)
    soma_gp = round(gp["valor_pagamento"].sum(), 2)
    soma_gpe = round(gpe["valor_total"].sum(), 2)
    if abs(soma_silver - soma_gp) > 0.05:
        erros.append(f"Soma silver ({soma_silver}) != gold_pagamentos ({soma_gp})")
    if abs(soma_gp - soma_gpe) > 0.05:
        erros.append(f"Soma gold_pagamentos ({soma_gp}) != gold_pedidos ({soma_gpe})")
    if gpe["order_id"].duplicated().any():
        erros.append("gold_pedidos tem order_id duplicado")
    if gpe["uf_cliente"].isna().any():
        erros.append("gold_pedidos tem pedidos sem UF")
    if (gp["parcelas"] < 1).any():
        erros.append("gold_pagamentos tem parcelas < 1")

    fora_do_gold = int((~silver["orders"]["order_id"].isin(gpe["order_id"])).sum())
    ent = gpe[gpe["status_pedido"] == "delivered"]

    # conciliação informativa: itens (preço + frete) x pagamentos, só pedidos entregues
    itens = silver["items"].groupby("order_id")["valor_item_com_frete"].sum()
    comp = ent.set_index("order_id")[["valor_total"]].join(itens, how="inner")
    dif = comp["valor_total"] - comp["valor_item_com_frete"]
    pct_bate = 100 * (dif.abs() <= 0.05).mean()

    L = ["# Relatório de qualidade e conciliação (gerado automaticamente)", "",
         "## Volumes por tabela", "", "| Tabela | Linhas raw | Linhas silver |", "|---|---:|---:|"]
    for nome, n_raw, n_silver in stats:
        L.append(f"| {nome} | {n_raw:,} | {n_silver:,} |")
    L += ["", "## Regras de limpeza aplicadas", ""] + report + [
        "", "## Tabelas gold", "",
        f"- gold_pagamentos: {len(gp):,} linhas (1 por pagamento).",
        f"- gold_pedidos: {len(gpe):,} linhas (1 por pedido com pagamento válido).",
        f"- Pedidos do raw sem nenhum pagamento válido (ficam fora do gold): {fora_do_gold}.",
        "", "## Conciliação", "",
        f"- Soma de pagamentos (silver): R$ {soma_silver:,.2f}",
        f"- Soma gold_pagamentos: R$ {soma_gp:,.2f}",
        f"- Soma gold_pedidos: R$ {soma_gpe:,.2f}",
        f"- Receita dos pedidos entregues (status = delivered): R$ {ent['valor_total'].sum():,.2f} "
        f"em {len(ent):,} pedidos.",
        f"- Entre os pedidos entregues, {pct_bate:.1f}% têm (preço + frete) dos itens igual ao total pago "
        "(nos demais a diferença pode vir de juros de parcelamento, vouchers ou arredondamentos; não investigado).",
        "", "## Validações automáticas", ""]
    if erros:
        L += [f"- FALHOU: {e}" for e in erros]
    else:
        L.append("- Todas as validações passaram (somas batem, sem order_id duplicado, sem UF nula, parcelas >= 1).")
    out_docs.mkdir(parents=True, exist_ok=True)
    (out_docs / "relatorio_qualidade.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    if erros:
        raise SystemExit("Validações falharam:\n" + "\n".join(erros))
    log("\n".join(L[-9:]))


def main():
    ap = argparse.ArgumentParser(description="ETL local Olist (raw -> silver -> gold)")
    ap.add_argument("--raw", default="data/raw", help="pasta com os CSVs do Kaggle")
    ap.add_argument("--out", default="data", help="pasta base de saída (cria silver/ e gold/)")
    ap.add_argument("--docs", default="docs", help="pasta do relatório de qualidade")
    a = ap.parse_args()
    raw_dir, out = Path(a.raw), Path(a.out)
    log(f"Formato silver: {'Parquet' if HAS_PARQUET else 'CSV (instale pyarrow para gerar Parquet)'}")

    raw = extract(raw_dir)

    silver = {
        "orders": silver_orders(raw["orders"]),
        "customers": silver_customers(raw["customers"]),
        "payments": silver_payments(raw["payments"]),
        "items": silver_items(raw["items"]),
        "products": silver_products(raw["products"], raw["translation"]),
        "sellers": silver_sellers(raw["sellers"]),
        "reviews": silver_reviews(raw["reviews"]),
        "geolocation": silver_geolocation(raw["geolocation"]),
    }
    for nome, df in silver.items():
        stats.append((nome, len(raw[nome]), len(df)))
        salvar(df, out / "silver", f"silver_{nome}")
        log(f"[silver] silver_{nome:12s} {len(df):>9,} linhas")

    gp, gpe = build_gold(silver)
    salvar(gp, out / "gold", "gold_pagamentos", forcar_csv=True)
    salvar(gpe, out / "gold", "gold_pedidos", forcar_csv=True)
    log(f"[gold] gold_pagamentos {len(gp):,} | gold_pedidos {len(gpe):,}")

    validar_e_relatar(silver, gp, gpe, Path(a.docs))
    log("\nETL concluído. Relatório em docs/relatorio_qualidade.md")


if __name__ == "__main__":
    main()
