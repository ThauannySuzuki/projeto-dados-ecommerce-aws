# Relatório de qualidade e conciliação (gerado automaticamente)

## Volumes por tabela

| Tabela | Linhas raw | Linhas silver |
|---|---:|---:|
| orders | 99,441 | 99,441 |
| customers | 99,441 | 99,441 |
| payments | 103,886 | 103,877 |
| items | 112,650 | 112,650 |
| products | 32,951 | 32,951 |
| sellers | 3,095 | 3,095 |
| reviews | 99,224 | 99,224 |
| geolocation | 1,000,163 | 19,015 |

## Regras de limpeza aplicadas

- orders: 0 linhas removidas (duplicadas ou sem data de compra: 0).
- payments: 2 pagamentos com 0 parcelas ajustados para 1x (pagamento à vista).
- payments: 9 pagamentos removidos (método 'not_defined' ou valor <= 0; soma removida = R$ 0.00). Duplicados removidos: 0.
- products: 610 produtos sem categoria -> 'sem_categoria'; colunas com 'lenght' renomeadas para 'length'.
- reviews: 0 linhas removidas (duplicadas ou nota fora de 1-5).
- geolocation: consolidada em 1 linha por prefixo de CEP (média de lat/lng; cidade e UF mais frequentes).

## Tabelas gold

- gold_pagamentos: 103,877 linhas (1 por pagamento).
- gold_pedidos: 99,437 linhas (1 por pedido com pagamento válido).
- Pedidos do raw sem nenhum pagamento válido (ficam fora do gold): 4.

## Conciliação

- Soma de pagamentos (silver): R$ 16,008,872.12
- Soma gold_pagamentos: R$ 16,008,872.12
- Soma gold_pedidos: R$ 16,008,872.12
- Receita dos pedidos entregues (status = delivered): R$ 15,422,461.77 em 96,477 pedidos.
- Entre os pedidos entregues, 99.7% têm (preço + frete) dos itens igual ao total pago (nos demais a diferença pode vir de juros de parcelamento, vouchers ou arredondamentos; não investigado).

## Validações automáticas

- Todas as validações passaram (somas batem, sem order_id duplicado, sem UF nula, parcelas >= 1).
