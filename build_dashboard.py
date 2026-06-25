name: Atualizar Dashboard AC Camargo

on:
  workflow_dispatch:
  schedule:
    - cron: "59 23 * * *"
      timezone: "America/Sao_Paulo"

permissions:
  contents: write

jobs:
  update-dashboard:
    runs-on: ubuntu-latest
    steps:
      - name: Baixar repositório
        uses: actions/checkout@v4

      - name: Configurar Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Gerar dashboard a partir do Google Sheets
        env:
          SHEET_PERFORMANCE_CSV_URL: "https://docs.google.com/spreadsheets/d/e/2PACX-1vQrVDPONG5v4gwG-eiOZPeTJnOBqQ3oVdJRJdXNRHvIzVfaCHbEcbfDELy1g3p8JVHFIxFKU_B-LxBt/pub?gid=533271213&single=true&output=csv"
          SHEET_SPOT_CSV_URL: "https://docs.google.com/spreadsheets/d/e/2PACX-1vQrVDPONG5v4gwG-eiOZPeTJnOBqQ3oVdJRJdXNRHvIzVfaCHbEcbfDELy1g3p8JVHFIxFKU_B-LxBt/pub?gid=1383548094&single=true&output=csv"
        run: python build_dashboard.py

      - name: Publicar atualização no repositório
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add index.html dashboard_data_summary.json
          if git diff --cached --quiet; then
            echo "Sem alterações para publicar."
          else
            git commit -m "Atualização automática do painel AC Camargo"
            git push
          fi
