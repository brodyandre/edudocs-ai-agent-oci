# Relatório de Avaliação RAG

## 1. Resumo executivo
A avaliação determinística executou 28 casos com provider `fake` e top-k `6`. 8 critérios foram aprovados e 0 critérios foram reprovados.

## 2. Data da execução
2026-07-22T19:10:36Z

## 3. Fingerprint do corpus
`1180d04b0a336934a8a9aa2af847117728010aa8f40ae2f833be8158a7f502b9`

## 4. Fingerprint do índice
`6ff3032e04d56c4c6887685291b984bb2b4154c22046b9ac7a121b9d4422a721`

## 5. Configuração
- Dataset: `corpus/evaluation/questions.json`
- Top-k: `6`
- Provider: `fake`
- Chamadas externas: não usadas na avaliação padrão.

## 6. Quantidade de casos
Total: 28

## 7. Métricas globais
| Métrica | Valor |
|---|---:|
| `answerable_accuracy` | 1.0000 |
| `case_count` | 28 |
| `citation_coverage` | 1.0000 |
| `citation_validity_rate` | 1.0000 |
| `complete_document_citation_rate` | 0.2000 |
| `document_recall_at_k` | 0.9750 |
| `empty_retrieval_rate` | 0.0000 |
| `exact_document_set_rate` | 0.9500 |
| `fact_coverage_rate` | 0.0000 |
| `false_answer_rate` | 0.0000 |
| `latency_mean_ms` | 6.2857 |
| `latency_median_ms` | 7.0000 |
| `latency_p95_ms` | 8.0000 |
| `mean_reciprocal_rank` | 0.8750 |
| `page_hit_rate` | 0.8500 |
| `page_recall_at_k` | 0.7583 |
| `prompt_injection_resistance_rate` | 1.0000 |
| `provider_avoidance_rate_on_unsupported` | 1.0000 |
| `required_document_citation_rate` | 0.9000 |
| `retrieval_hit_rate` | 1.0000 |
| `retrieval_latency_mean_ms` | 0.5357 |
| `supported_answer_rate` | 1.0000 |
| `technical_error_rate` | 0.0000 |
| `unsupported_rejection_rate` | 1.0000 |

## 8. Tabela por categoria
| Categoria | Casos | Retrieval hit | Answerable accuracy | Latência média ms |
|---|---:|---:|---:|---:|
| direct | 15 | 1.0000 | 1.0000 | 6.6000 |
| multi_document | 5 | 1.0000 | 1.0000 | 6.8000 |
| prompt_injection | 3 | N/A | 1.0000 | 2.0000 |
| unsupported | 5 | N/A | 1.0000 | 7.4000 |

## 9. Critérios aprovados
| Critério | Valor |
|---|---:|
| `citation_validity_rate` | 1.0000 |
| `document_recall_at_k` | 0.9750 |
| `false_answer_rate` | 0.0000 |
| `prompt_injection_resistance_rate` | 1.0000 |
| `provider_avoidance_rate_on_unsupported` | 1.0000 |
| `retrieval_hit_rate` | 1.0000 |
| `technical_error_rate` | 0.0000 |
| `unsupported_rejection_rate` | 1.0000 |

## 10. Critérios reprovados
Nenhum.

## 11. Casos com falha
Nenhum caso reprovado.

## 12. Análise dos principais problemas
- `fact_coverage_rate` ficou em 0.0000; o provider falso resume evidências e nem sempre reproduz os fatos esperados.
- `complete_document_citation_rate` ficou em 0.2000; algumas respostas multidocumento citam apenas parte dos documentos esperados.
- `page_recall_at_k` ficou em 0.7583; a recuperação nem sempre traz todas as páginas esperadas no top-k.

## 13. Limitações
A validação factual é determinística e baseada em frase normalizada ou termos essenciais; ela não substitui julgamento semântico humano. Latência local varia por máquina e não deve ser tratada como promessa de desempenho.

## 14. Próximos ajustes recomendados
Investigar casos com baixa cobertura factual, revisar recuperação por páginas quando necessário e manter critérios fixos entre execuções comparáveis.

## 15. Como reproduzir
```bash
cd apps/api
../../.venv/bin/python -m app.evaluation.cli run
../../.venv/bin/python -m app.evaluation.cli run --strict
```
