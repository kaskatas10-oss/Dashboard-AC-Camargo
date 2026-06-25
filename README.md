#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera o dashboard AC Camargo a partir de duas abas publicadas do Google Sheets em CSV:
- BASE_PERFORMANCE: base operacional
- BASE_SPOT: serviços SPOT/exclusivos

Uso local:
  python build_dashboard.py

Variáveis opcionais:
  SHEET_PERFORMANCE_CSV_URL
  SHEET_SPOT_CSV_URL
  DASHBOARD_TEMPLATE
  DASHBOARD_OUTPUT
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from typing import Dict, Iterable, List, Tuple

DEFAULT_PERFORMANCE_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQrVDPONG5v4gwG-eiOZPeTJnOBqQ3oVdJRJdXNRHvIzVfaCHbEcbfDELy1g3p8JVHFIxFKU_B-LxBt/pub?gid=533271213&single=true&output=csv"
DEFAULT_SPOT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQrVDPONG5v4gwG-eiOZPeTJnOBqQ3oVdJRJdXNRHvIzVfaCHbEcbfDELy1g3p8JVHFIxFKU_B-LxBt/pub?gid=1383548094&single=true&output=csv"

PERFORMANCE_URL = os.getenv("SHEET_PERFORMANCE_CSV_URL", DEFAULT_PERFORMANCE_URL).strip()
SPOT_URL = os.getenv("SHEET_SPOT_CSV_URL", DEFAULT_SPOT_URL).strip()
TEMPLATE_PATH = os.getenv("DASHBOARD_TEMPLATE", "template_dashboard.html")
OUTPUT_PATH = os.getenv("DASHBOARD_OUTPUT", "index.html")
SUMMARY_PATH = os.getenv("DASHBOARD_SUMMARY", "dashboard_data_summary.json")


def log(msg: str) -> None:
    print(f"[dashboard] {msg}", flush=True)


def fetch_csv_text(url: str) -> str:
    if not url:
        raise ValueError("URL CSV vazia")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 dashboard-ac-camargo"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
    # Google usually returns UTF-8. utf-8-sig handles BOM when present.
    return raw.decode("utf-8-sig", errors="replace")


def sniff_delimiter(text: str) -> str:
    sample = text[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=";,\t,").delimiter
    except Exception:
        # Google Sheets em pt-BR frequentemente publica CSV com vírgula, mas bases exportadas do Excel podem vir com ;
        return ";" if sample.count(";") >= sample.count(",") else ","


def read_csv_url(url: str) -> List[Dict[str, str]]:
    text = fetch_csv_text(url)
    delimiter = sniff_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    rows: List[Dict[str, str]] = []
    for row in reader:
        if not row:
            continue
        clean = {str(k or "").strip(): str(v or "").strip() for k, v in row.items()}
        # Ignore linhas totalmente vazias
        if any(v for v in clean.values()):
            rows.append(clean)
    log(f"Linhas lidas: {len(rows)} | colunas: {len(reader.fieldnames or [])} | delimitador: {repr(delimiter)}")
    return rows


def pick(row: Dict[str, str], *names: str, default: str = "") -> str:
    # Busca direta e depois busca normalizada sem acentos simples/pontuação pesada.
    for name in names:
        if name in row and str(row[name]).strip() != "":
            return str(row[name]).strip()
    norm = {normalize_key(k): v for k, v in row.items()}
    for name in names:
        val = norm.get(normalize_key(name), "")
        if str(val).strip() != "":
            return str(val).strip()
    return default


def normalize_key(s: str) -> str:
    repl = str.maketrans("áàãâäéèêëíìîïóòõôöúùûüçÁÀÃÂÄÉÈÊËÍÌÎÏÓÒÕÔÖÚÙÛÜÇ", "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC")
    return re.sub(r"[^a-z0-9]+", "", str(s).translate(repl).lower())


def parse_number(value: str) -> float:
    if value is None:
        return 0.0
    s = str(value).strip()
    if not s:
        return 0.0
    s = s.replace("R$", "").replace("km", "").replace(" ", "")
    # Padrão pt-BR: 1.234,56
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    s = re.sub(r"[^0-9.\-]", "", s)
    if s in ("", "-", "."):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_int(value: str) -> int:
    try:
        return int(round(parse_number(value)))
    except Exception:
        return 0


def parse_date(value: str) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    # Google Sheet pode enviar yyyy-mm-dd, dd/mm/yyyy ou datetime.
    s = s.split()[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return s


def infer_month(data: str, mes: str = "") -> str:
    mes = str(mes or "").strip()
    if mes:
        return mes
    data = parse_date(data)
    try:
        dt = datetime.strptime(data, "%Y-%m-%d")
        nomes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        return f"{nomes[dt.month-1]}/{dt.year}"
    except Exception:
        return "Não informado"


def parse_duration_seconds(value: str, *, is_wait: bool = False) -> int:
    s = str(value or "").strip().lower()
    if not s:
        return 0
    # Já numérico em segundos
    if re.fullmatch(r"\d+(?:[\.,]\d+)?", s):
        return int(round(parse_number(s)))
    total = 0
    # Formatos: 2h 05m, 7min 55s, 31min 01s
    h = re.search(r"(\d+)\s*h", s)
    m = re.search(r"(\d+)\s*(?:min|m)(?![a-z])", s)
    sec = re.search(r"(\d+)\s*s", s)
    if h or m or sec:
        total += int(h.group(1)) * 3600 if h else 0
        total += int(m.group(1)) * 60 if m else 0
        total += int(sec.group(1)) if sec else 0
        return total
    # Formatos com dois ou três blocos: 00:07:55, 07:55
    if ":" in s:
        parts = [parse_int(p) for p in s.split(":") if p.strip() != ""]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            if is_wait:
                # Para espera, a operação usa MM:SS quando há apenas dois blocos.
                return parts[0] * 60 + parts[1]
            return parts[0] * 3600 + parts[1] * 60
    return 0


def infer_tipo_veiculo(veiculo: str, rota: str = "", tipo: str = "") -> Tuple[str, str]:
    tipo_original = str(tipo or "").strip()
    veiculo_original = str(veiculo or "").strip()
    base = " ".join([tipo_original, veiculo_original, str(rota or "")]).lower()
    if "moto" in base:
        tipo_limpo = "Moto"
        if not veiculo_original:
            veiculo_original = "Moto"
    elif "camin" in base:
        tipo_limpo = "Caminhão"
        if not veiculo_original:
            veiculo_original = "Caminhão"
    elif "carro" in base or "utilit" in base or "utilitário" in base or "utilitario" in base:
        tipo_limpo = "Carro"
        if not veiculo_original:
            veiculo_original = "Carro (Utilitário Leve)"
    else:
        tipo_limpo = tipo_original or "Não informado"
        veiculo_original = veiculo_original or "Não informado"
    # Normaliza algumas variações na classificação agregada
    low = tipo_limpo.lower()
    if "moto" in low:
        tipo_limpo = "Moto"
    elif "camin" in low:
        tipo_limpo = "Caminhão"
    elif "carro" in low or "utilit" in low:
        tipo_limpo = "Carro"
    return veiculo_original, tipo_limpo


def normalize_operational(row: Dict[str, str], source_fallback: str, idx: int) -> Dict[str, object] | None:
    tipo_reg = pick(row, "Tipo Registro", default="Operacional").lower()
    if tipo_reg and "spot" in tipo_reg:
        return None
    data = parse_date(pick(row, "Data", "Dt.Solicitação", "Dt. Solicitação", "Dt.Solicitacao"))
    mes = infer_month(data, pick(row, "Mês", "Mes"))
    veiculo_raw = pick(row, "Veículo", "Veiculo")
    rota = pick(row, "Rota", "Nome Rota Fixa", "Nome da Rota Fixa")
    tipo_veiculo_raw = pick(row, "Tipo Veículo", "Tipo de Veículo", "Tipo Veiculo")
    veiculo, tipo_veiculo = infer_tipo_veiculo(veiculo_raw, rota, tipo_veiculo_raw)
    departamento = pick(row, "Departamento", "Setor", default="Não informado") or "Não informado"
    espera_sec = parse_int(pick(row, "Tempo Espera Segundos", "Tempo de Espera Segundos", "Espera Segundos"))
    if not espera_sec:
        espera_sec = parse_duration_seconds(pick(row, "Tempo Espera", "Tempo de Espera", "Espera"), is_wait=True)
    # Correções solicitadas por Roberto após validação operacional.
    dep_norm = normalize_key(departamento)
    if dep_norm == normalize_key("U.I. 6º Andar-Tamandaré") and espera_sec > 20 * 60:
        espera_sec = 7 * 60 + 55
    if dep_norm == normalize_key("Desp. Estruturais-CIPE") and espera_sec > 20 * 60:
        espera_sec = 7 * 60 + 51
    percurso_sec = parse_int(pick(row, "Tempo Percurso Segundos", "Tempo de Percurso Segundos", "Percurso Segundos"))
    if not percurso_sec:
        percurso_sec = parse_duration_seconds(pick(row, "Tempo Percurso", "Tempo de Percurso", "Percurso"), is_wait=False)
    return {
        "mes": mes,
        "data": data,
        "status": pick(row, "Status", default="Concluída") or "Concluída",
        "os": pick(row, "OS", "Ordem de Serviço", "Ordem Servico"),
        "veiculo": veiculo,
        "tipoVeiculo": tipo_veiculo,
        "tipoServico": pick(row, "Tipo Serviço", "Tipo de Serviço", "Tipo Servico"),
        "filial": pick(row, "Filial"),
        "cliente": pick(row, "Cliente"),
        "contato": pick(row, "Contato/Solicitante", "Contato", "Solicitante"),
        "departamento": departamento,
        "rota": rota or "Não informado",
        "condutor": pick(row, "Condutor", "Motorista", default="Não informado") or "Não informado",
        "bairroDestino": pick(row, "Bairro Destino", "Bairro", default="Não informado") or "Não informado",
        "cidadeDestino": pick(row, "Cidade Destino", "Cidade", default="Não informado") or "Não informado",
        "unidadeCliente": pick(row, "Unidade Cliente", "Unidade", default=""),
        "unidadeCondutor": pick(row, "Unidade Condutor", default=""),
        "quantidadeEndereco": parse_int(pick(row, "Quantidade Endereços", "Quantidade Enderecos", "Endereços", "Enderecos")),
        "distancia": parse_number(pick(row, "Distância KM", "Distancia KM", "Distância", "Distancia")),
        "tempoPercursoSec": percurso_sec,
        "tempoEsperaSec": espera_sec,
        "tipoOperacao": pick(row, "Tipo Operação", "Tipo Operacao", default="Contrato") or "Contrato",
        "sourceSheet": pick(row, "Planilha Origem", default=source_fallback),
        "rowNumber": parse_int(pick(row, "Linha Origem", default=str(idx))),
    }


def normalize_spot(row: Dict[str, str], source_fallback: str, idx: int) -> Dict[str, object] | None:
    tipo_reg = pick(row, "Tipo Registro", default="SPOT").lower()
    # Se a aba for só de SPOT, aceita mesmo com tipo em branco. Se vier de base mista, pega só SPOT.
    data = parse_date(pick(row, "Data", "Dia", "Dt.Solicitação", "Dt. Solicitação", "Dt.Solicitacao"))
    solicitante = pick(row, "Solicitante", "Contato/Solicitante", "Nome Solicitante", "Contato")
    destino = pick(row, "Destino", "Endereço Destino", "Endereco Destino")
    origem = pick(row, "Origem", "Endereço Origem", "Endereco Origem")
    descricao = pick(row, "Descrição", "Descricao", "Descrição do serviço", "Descricao do servico")
    valor_total = parse_number(pick(row, "Valor Total", "Total"))
    valor_mercadoria = parse_number(pick(row, "Valor Mercadoria", "Valor da Mercadoria"))
    os_num = pick(row, "OS", "Ordem de Serviço", "Ordem Servico")
    if not any([data, solicitante, destino, origem, descricao, valor_total, valor_mercadoria, os_num]):
        return None
    veiculo_raw = pick(row, "Veículo", "Veiculo")
    rota = pick(row, "Rota", "Nome Rota Fixa")
    tipo_veiculo_raw = pick(row, "Tipo Veículo", "Tipo de Veículo", "Tipo Veiculo")
    veiculo, tipo_veiculo = infer_tipo_veiculo(veiculo_raw, rota, tipo_veiculo_raw)
    return {
        "mes": infer_month(data, pick(row, "Mês", "Mes")),
        "data": data,
        "origem": origem,
        "destino": destino,
        "solicitante": solicitante or "Não informado",
        "veiculo": veiculo,
        "tipoVeiculo": tipo_veiculo,
        "valor": parse_number(pick(row, "Valor")),
        "valorMercadoria": valor_mercadoria,
        "seguro": parse_number(pick(row, "Seguro")),
        "ajudante": parse_number(pick(row, "Ajudante")),
        "valorTotal": valor_total,
        "os": os_num,
        "descricao": descricao,
        "tipoOperacao": pick(row, "Tipo Operação", "Tipo Operacao", default="SPOT") or "SPOT",
        "sourceSheet": pick(row, "Planilha Origem", default=source_fallback),
        "rowNumber": parse_int(pick(row, "Linha Origem", default=str(idx))),
    }


def build() -> None:
    log("Lendo BASE_PERFORMANCE...")
    perf_raw = read_csv_url(PERFORMANCE_URL)
    log("Lendo BASE_SPOT...")
    spot_raw = read_csv_url(SPOT_URL)

    operational_rows: List[Dict[str, object]] = []
    fallback_spots: List[Dict[str, object]] = []
    for i, row in enumerate(perf_raw, start=2):
        op = normalize_operational(row, "BASE_PERFORMANCE", i)
        if op is not None:
            operational_rows.append(op)
        elif "spot" in pick(row, "Tipo Registro", default="").lower():
            sp = normalize_spot(row, "BASE_PERFORMANCE", i)
            if sp:
                fallback_spots.append(sp)

    spot_rows: List[Dict[str, object]] = []
    for i, row in enumerate(spot_raw, start=2):
        sp = normalize_spot(row, "BASE_SPOT", i)
        if sp:
            spot_rows.append(sp)
    if not spot_rows and fallback_spots:
        log("BASE_SPOT vazia; usando SPOTs encontrados na BASE_PERFORMANCE.")
        spot_rows = fallback_spots

    log(f"Operacionais normalizados: {len(operational_rows)}")
    log(f"SPOTs normalizados: {len(spot_rows)}")

    template = open(TEMPLATE_PATH, "r", encoding="utf-8").read()
    if "__OPERATIONAL_ROWS__" not in template or "__SPOT_ROWS__" not in template:
        raise RuntimeError("Template não contém os marcadores __OPERATIONAL_ROWS__ e __SPOT_ROWS__.")

    html = template.replace("__OPERATIONAL_ROWS__", json.dumps(operational_rows, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("__SPOT_ROWS__", json.dumps(spot_rows, ensure_ascii=False, separators=(",", ":")))
    # Marca discreta de rastreabilidade técnica no HTML.
    html = html.replace("</body>", f"<!-- Atualizado automaticamente em {datetime.utcnow().isoformat()}Z -->\n</body>")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    summary = {
        "updated_utc": datetime.utcnow().isoformat() + "Z",
        "performance_url_configured": bool(PERFORMANCE_URL),
        "spot_url_configured": bool(SPOT_URL),
        "operational_rows": len(operational_rows),
        "spot_rows": len(spot_rows),
        "months_operational": sorted({r.get("mes") for r in operational_rows}),
        "months_spot": sorted({r.get("mes") for r in spot_rows}),
        "vehicle_types": sorted({r.get("tipoVeiculo") for r in operational_rows}),
    }
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    log(f"Dashboard gerado em {OUTPUT_PATH}")
    log(f"Resumo gerado em {SUMMARY_PATH}")


if __name__ == "__main__":
    try:
        build()
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise
