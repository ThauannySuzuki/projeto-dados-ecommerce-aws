# Projeto Dados AWS — Olist: Visão Financeira e Comportamento de Pagamentos

Pipeline de dados sobre o [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(~100 mil pedidos, 2016–2018). O produto final (Entrega 3) é um dashboard no Amazon QuickSight.
Este repositório cobre a **Entrega 2: ETL e consultas SQL**.

## Arquitetura

```
Kaggle (CSV) → Amazon S3 (raw) → AWS Glue (ETL) → Amazon Athena (gold) → Amazon QuickSight (dashboard)
```

### Status da Entrega 2

O upload dos CSVs para o bucket S3 (`olist-datalake-raw-projeto-dados`, us-east-2) **foi bloqueado por falta de permissão**
na conta da faculdade: o bucket foi criado, mas todo upload retorna `Acesso negado`
("Você não tem permissões para fazer upload de arquivos e pastas"). Por isso, a Entrega 2 foi
implementada **localmente**, reproduzindo cada etapa do pipeline:

| Etapa na AWS | O que foi feito nesta entrega | Arquivo |
|---|---|---|
| S3 (raw) | CSVs originais na pasta `data/raw/` | — |
| Glue (ETL) | Script Python/pandas: raw → silver → gold | `etl/etl_olist.py` |
| Athena (DDL) | DDL das tabelas gold (**não executado no Athena**) | `sql/00_ddl_athena_gold.sql` |
| Athena (consultas) | 7 consultas SQL, executadas localmente em SQLite | `sql/consultas_dashboard.sql`, `etl/run_queries.py` |
| QuickSight | Previsto para a Entrega 3 | — |

As consultas usam SQL padrão e foram escritas para rodar no Athena sem alteração; nesta entrega,
foram validadas apenas no SQLite local.

## Como executar

```bash
pip install -r requirements.txt          # pyarrow é opcional (gera Parquet)
# coloque os 9 CSVs do Kaggle em data/raw/
python etl/etl_olist.py                  # gera data/silver, data/gold e docs/relatorio_qualidade.md
python etl/run_queries.py                # roda sql/consultas_dashboard.sql e salva outputs/resultados_sql/
```

## Camadas de dados

- **raw**: os 9 CSVs originais, sem alteração.
- **silver**: cada tabela limpa — datas convertidas, textos padronizados (minúsculas/maiúsculas, espaços), CEP como texto com 5 dígitos,
  duplicados removidos, categorias de produto traduzidas, geolocalização consolidada em 1 linha por CEP.
- **gold** (as tabelas do dashboard):
  - `gold_pedidos` — 1 linha por pedido: data, status, UF, valor total pago, qtd. de pagamentos, máx. de parcelas, método principal, flag de cartão de crédito.
  - `gold_pagamentos` — 1 linha por pagamento: método, parcelas, valor, e os mesmos atributos do pedido.

### Decisões de limpeza (pagamentos)

- 2 pagamentos com 0 parcelas → ajustados para 1x (pagamento à vista).
- 9 pagamentos removidos: método `not_defined` ou valor ≤ 0 (soma removida: R$ 0,00, então não afetam a receita).
- 4 pedidos ficam fora do gold por não terem nenhum pagamento válido.
- Definições do dashboard: **receita** = soma de `payment_value`; **ticket médio** = receita ÷ pedidos;
  **% compra no cartão** = pedidos com ao menos um pagamento em `credit_card` ÷ total de pedidos.
  O filtro padrão é `status = delivered`, como no protótipo do Figma.

Detalhes e conciliação: [`docs/relatorio_qualidade.md`](docs/relatorio_qualidade.md).

## Resultados (pedidos entregues)

| Indicador | Valor |
|---|---:|
| Receita total | R$ 15.422.461,77 |
| Total de pedidos | 96.477 |
| Ticket médio | R$ 159,86 |
| % compra no cartão | 77,0% |

Receita por método: cartão de crédito 78,5% · boleto 18,0% · voucher 2,2% · cartão de débito 1,4%.
Top 5 estados por receita: SP (R$ 5,77 mi), RJ (R$ 2,06 mi), MG (R$ 1,82 mi), RS (R$ 0,86 mi), PR (R$ 0,78 mi).
Todos os resultados estão em `outputs/resultados_sql/`.

Conferência: receita total, receita de SP, receita de cartão e % de cartão foram recalculadas direto dos CSVs
originais, sem passar pelo ETL, e coincidiram com as consultas.

## Consultas × visuais do protótipo

| Consulta | Visual do dashboard |
|---|---|
| `q1_kpis_gerais` | 4 cards: Receita Total, Total de Pedidos, Ticket Médio, % Compra no Cartão |
| `q2_evolucao_receita_mensal` | Gráfico de linha: evolução da receita |
| `q3_receita_por_metodo` | Gráfico de rosca: receita por método |
| `q4_distribuicao_parcelamento` | Gráfico de barras: distribuição de parcelamento |
| `q5_top5_estados_por_receita` | Tabela: top 5 estados |
| `q6_pedidos_por_status`, `q7_receita_por_ano_e_metodo` | Apoio aos filtros Status e Ano |

> Os valores exibidos no protótipo do Figma (exceto a receita de R$ 15,4 mi) eram ilustrativos.
> Os valores reais calculados estão na tabela acima.

## Limitações e próximos passos

- Glue, Athena e S3 **não foram executados** (bloqueio de permissão). O DDL do Athena e a migração do script para um job Glue
  (PySpark) ficam pendentes até a liberação da permissão `s3:PutObject`.
- Entrega 3: carregar as tabelas gold no QuickSight (via Athena, ou upload direto dos CSVs de `data/gold/`) e montar o dashboard do Figma.
- A série mensal começa em 2017-01 porque 2016 tem poucos meses com pedidos.
