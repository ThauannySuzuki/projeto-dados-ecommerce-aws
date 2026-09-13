-- Arquivo: create_tables.sql
-- Objetivo: Criar a estrutura do banco de dados analítico (Camada Gold) no Amazon Athena

-- 1. Tabela de Clientes
CREATE EXTERNAL TABLE IF NOT EXISTS tb_clientes (
    customer_id STRING,
    customer_unique_id STRING,
    customer_zip_code_prefix STRING,
    customer_city STRING,
    customer_state STRING
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 's3://meu-bucket-datalake/gold/clientes/'
TBLPROPERTIES ('skip.header.line.count'='1');

-- 2. Tabela de Pedidos
CREATE EXTERNAL TABLE IF NOT EXISTS tb_pedidos (
    order_id STRING,
    customer_id STRING,
    order_status STRING,
    order_purchase_timestamp TIMESTAMP,
    order_approved_at TIMESTAMP,
    order_delivered_carrier_date TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 's3://meu-bucket-datalake/gold/pedidos/'
TBLPROPERTIES ('skip.header.line.count'='1');

-- 3. Tabela de Pagamentos (Foco Financeiro)
CREATE EXTERNAL TABLE IF NOT EXISTS tb_pagamentos (
    order_id STRING,
    payment_sequential INT,
    payment_type STRING,
    payment_installments INT,
    payment_value DOUBLE
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 's3://meu-bucket-datalake/gold/pagamentos/'
TBLPROPERTIES ('skip.header.line.count'='1');
