-- =====================================================================
-- Consultas do dashboard "Visão Financeira e Comportamento de Pagamentos"
-- Tabelas: gold_pedidos (1 linha por pedido) e gold_pagamentos (1 linha por pagamento)
--
-- SQL padrão (ANSI): roda no Athena sem alteração e também localmente (run_queries.py).
-- Filtro padrão do protótipo: Status = Entregue  ->  status_pedido = 'delivered'
-- Para simular os outros filtros do Figma, acrescente no WHERE:
--     AND ano = 2018            (filtro Ano)
--     AND uf_cliente = 'SP'     (filtro UF)
-- =====================================================================


-- name: q1_kpis_gerais
-- Cards do topo: Receita Total, Total de Pedidos, Ticket Médio, % Compra no Cartão
SELECT
    ROUND(SUM(valor_total), 2)                                   AS receita_total,
    COUNT(*)                                                     AS total_pedidos,
    ROUND(SUM(valor_total) / COUNT(*), 2)                        AS ticket_medio,
    ROUND(100.0 * SUM(flag_cartao_credito) / COUNT(*), 1)        AS pct_compra_cartao
FROM gold_pedidos
WHERE status_pedido = 'delivered';


-- name: q2_evolucao_receita_mensal
-- Gráfico de linha: faturamento por mês, com variação sobre o mês anterior.
-- A série começa em 2017-01: em 2016 há só 4 meses com pedidos (set e nov não existem e dez tem 1 pedido),
-- o que distorceria a variação mensal.
WITH mensal AS (
    SELECT ano_mes,
           SUM(valor_total) AS receita,
           COUNT(*)         AS pedidos
    FROM gold_pedidos
    WHERE status_pedido = 'delivered'
      AND ano_mes >= '2017-01'
    GROUP BY ano_mes
)
SELECT ano_mes,
       ROUND(receita, 2) AS receita,
       pedidos,
       ROUND(100.0 * (receita - LAG(receita) OVER (ORDER BY ano_mes))
                   / LAG(receita) OVER (ORDER BY ano_mes), 1) AS variacao_mensal_pct
FROM mensal
ORDER BY ano_mes;


-- name: q3_receita_por_metodo
-- Gráfico de rosca: distribuição do faturamento por método de pagamento
SELECT metodo_pagamento,
       ROUND(SUM(valor_pagamento), 2)                                         AS receita,
       COUNT(*)                                                               AS pagamentos,
       ROUND(100.0 * SUM(valor_pagamento) / SUM(SUM(valor_pagamento)) OVER (), 1) AS pct_receita
FROM gold_pagamentos
WHERE status_pedido = 'delivered'
GROUP BY metodo_pagamento
ORDER BY receita DESC;


-- name: q4_distribuicao_parcelamento
-- Gráfico de barras: volume de pagamentos no cartão de crédito por número de parcelas (12 = 12x ou mais)
WITH cartao AS (
    SELECT CASE WHEN parcelas >= 12 THEN 12 ELSE parcelas END AS n_parcelas,
           valor_pagamento
    FROM gold_pagamentos
    WHERE metodo_pagamento = 'credit_card'
      AND status_pedido = 'delivered'
)
SELECT n_parcelas,
       CASE WHEN n_parcelas = 12 THEN '12x+' ELSE CAST(n_parcelas AS VARCHAR) || 'x' END AS rotulo,
       COUNT(*)                          AS pagamentos,
       ROUND(SUM(valor_pagamento), 2)    AS receita,
       ROUND(AVG(valor_pagamento), 2)    AS valor_medio
FROM cartao
GROUP BY n_parcelas
ORDER BY n_parcelas;


-- name: q5_top5_estados_por_receita
-- Tabela: UFs que mais geram faturamento e seu ticket médio
SELECT uf_cliente,
       ROUND(SUM(valor_total), 2)             AS receita_total,
       COUNT(*)                               AS pedidos,
       ROUND(SUM(valor_total) / COUNT(*), 2)  AS ticket_medio
FROM gold_pedidos
WHERE status_pedido = 'delivered'
GROUP BY uf_cliente
ORDER BY receita_total DESC
LIMIT 5;


-- name: q6_pedidos_por_status
-- Apoio ao filtro "Status": quanto cada status representa
SELECT status_pedido,
       COUNT(*)                                                     AS pedidos,
       ROUND(SUM(valor_total), 2)                                   AS receita,
       ROUND(100.0 * SUM(valor_total) / SUM(SUM(valor_total)) OVER (), 2) AS pct_receita
FROM gold_pedidos
GROUP BY status_pedido
ORDER BY receita DESC;


-- name: q7_receita_por_ano_e_metodo
-- Apoio ao filtro "Ano": receita de cada método por ano (tabela cruzada)
SELECT ano,
       ROUND(SUM(CASE WHEN metodo_pagamento = 'credit_card' THEN valor_pagamento ELSE 0 END), 2) AS credit_card,
       ROUND(SUM(CASE WHEN metodo_pagamento = 'boleto'      THEN valor_pagamento ELSE 0 END), 2) AS boleto,
       ROUND(SUM(CASE WHEN metodo_pagamento = 'voucher'     THEN valor_pagamento ELSE 0 END), 2) AS voucher,
       ROUND(SUM(CASE WHEN metodo_pagamento = 'debit_card'  THEN valor_pagamento ELSE 0 END), 2) AS debit_card,
       ROUND(SUM(valor_pagamento), 2)                                                            AS total
FROM gold_pagamentos
WHERE status_pedido = 'delivered'
GROUP BY ano
ORDER BY ano;
