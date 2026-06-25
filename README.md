# Dashboard AC Camargo — Atualização automática

Este repositório publica o painel **Performance Operacional AC Camargo** via GitHub Pages e atualiza o `index.html` automaticamente a partir do Google Sheets.

## Fontes de dados

- `BASE_PERFORMANCE`: base operacional publicada como CSV.
- `BASE_SPOT`: base de solicitações SPOT publicada como CSV.

## Como funciona

1. O operador cola/corrige os dados no Google Sheets.
2. O GitHub Actions executa o arquivo `build_dashboard.py`.
3. O script lê as duas abas em CSV, normaliza os dados e gera um novo `index.html`.
4. O GitHub Pages publica a versão atualizada no mesmo link.

## Atualização automática

O workflow roda diariamente às **23:59** no horário de São Paulo e também pode ser acionado manualmente em:

`Actions > Atualizar Dashboard AC Camargo > Run workflow`

## Arquivos principais

- `index.html`: painel publicado.
- `template_dashboard.html`: modelo visual do painel com marcadores de dados.
- `build_dashboard.py`: script que lê o Google Sheets e gera o painel.
- `.github/workflows/update-dashboard.yml`: automação de atualização.
- `dashboard_data_summary.json`: resumo técnico da última geração.

## Observação operacional

A base deve manter os cabeçalhos definidos no modelo do Google Sheets. Correções no Sheets, inclusive exclusão de linhas lançadas por engano, serão refletidas na próxima execução automática ou manual.
