-- =====================================================================
-- DDL das tabelas gold para o Amazon Athena (camada Gold do projeto)
-- ATENÇÃO: este arquivo NÃO foi executado no Athena (o upload ao S3 está bloqueado
-- na conta da faculdade). A estrutura segue as colunas geradas pelo ETL local.
-- Antes de rodar: gerar os arquivos gold em Parquet (pip install pyarrow) e copiá-los
-- para o prefixo abaixo no S3.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS olist_gold;

CREATE EXTERNAL TABLE IF NOT EXISTS olist_gold.gold_pedidos (
    order_id             string,
    data_pedido          string,   -- formato YYYY-MM-DD
    ano                  int,
    mes                  int,
    ano_mes              string,   -- formato YYYY-MM
    status_pedido        string,
    uf_cliente           string,
    cidade_cliente       string,
    valor_total          double,
    qtd_pagamentos       int,
    max_parcelas         int,
    metodo_principal     string,
    flag_cartao_credito  int
)
STORED AS PARQUET
LOCATION 's3://olist-datalake-raw-projeto-dados/gold/gold_pedidos/';

CREATE EXTERNAL TABLE IF NOT EXISTS olist_gold.gold_pagamentos (
    order_id              string,
    sequencial_pagamento  int,
    metodo_pagamento      string,
    parcelas              int,
    valor_pagamento       double,
    data_pedido           string,
    ano                   int,
    mes                   int,
    ano_mes               string,
    status_pedido         string,
    uf_cliente            string,
    cidade_cliente        string
)
STORED AS PARQUET
LOCATION 's3://olist-datalake-raw-projeto-dados/gold/gold_pagamentos/';
