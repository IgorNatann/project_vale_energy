"""Cria ou atualiza o Genie de operações a partir da definição versionada."""

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

TITULO = "Grid Intelligence - Copiloto de Operacoes"
ARQUIVO = Path(__file__).resolve().parents[1] / "src/genie/grid_intelligence.json"


def executar_cli(argumentos, perfil):
    """Executa a CLI autenticada e converte a resposta JSON."""
    resultado = subprocess.run(
        ["databricks", *argumentos, "--profile", perfil, "-o", "json"],
        check=True, capture_output=True, text=True, encoding="utf-8", timeout=180,
    )
    return json.loads(resultado.stdout) if resultado.stdout.strip() else {}


def enviar_json(metodo, caminho, payload, perfil):
    """Preserva Unicode e aspas no corpo enviado à API pelo arquivo temporário."""
    with tempfile.TemporaryDirectory() as pasta:
        arquivo = Path(pasta) / "pedido.json"
        arquivo.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return executar_cli(["api", metodo, caminho, "--json", f"@{arquivo}"], perfil)


def obter_warehouse_padrao(perfil):
    """Usa o warehouse padrão do workspace quando nenhum é informado."""
    return executar_cli(["experimental", "aitools", "tools", "get-default-warehouse"], perfil)["id"]


def preparar_definicao(catalogo):
    """Substitui o catálogo validado sem incluir identificadores fixos no JSON."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", catalogo):
        raise ValueError("O catálogo deve conter somente letras, números e sublinhados")
    return json.loads(ARQUIVO.read_text(encoding="utf-8").replace("${catalogo}", catalogo))


def identificar_espaco(perfil, definicao, titulo=TITULO):
    """Encontra uma implantação compatível pelo título, sem sobrescrever outro espaço."""
    espacos = executar_cli(["genie", "list-spaces"], perfil).get("spaces", [])
    candidatos = [espaco for espaco in espacos if espaco.get("title") == titulo]
    if len(candidatos) > 1:
        raise ValueError("Há mais de um espaço com esse título. Informe --space-id explicitamente")
    if not candidatos:
        return None
    identificador = candidatos[0]["space_id"]
    existente = executar_cli(["genie", "get-space", identificador, "--include-serialized-space"], perfil)
    fontes = json.loads(existente["serialized_space"])["data_sources"]

    def identificadores(dados):
        return {item["identifier"] for tipo in ("tables", "metric_views") for item in dados.get(tipo, [])}

    if identificadores(fontes) != identificadores(definicao["data_sources"]):
        raise ValueError("O espaço encontrado usa fontes diferentes. Informe --space-id após revisar o destino")
    return identificador


def principal():
    """Aplica o espaço no catálogo e workspace explicitamente escolhidos."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--perfil", required=True, help="Perfil autenticado da CLI Databricks")
    parser.add_argument("--catalogo", required=True, help="Catálogo com as tabelas gold")
    parser.add_argument("--warehouse-id", help="SQL warehouse para as consultas do Genie (padrão: o do workspace)")
    parser.add_argument("--titulo", default=TITULO, help="Título usado para localizar ou criar o espaço")
    parser.add_argument("--space-id", help="Atualiza explicitamente um espaço existente")
    parser.add_argument("--parent-path", help="Pasta existente para criar um novo espaço")
    args = parser.parse_args()

    definicao = preparar_definicao(args.catalogo)
    identificador = args.space_id or identificar_espaco(args.perfil, definicao, args.titulo)
    warehouse_id = args.warehouse_id or obter_warehouse_padrao(args.perfil)
    payload = {"serialized_space": json.dumps(definicao, ensure_ascii=False), "warehouse_id": warehouse_id}
    if identificador:
        resposta = enviar_json("patch", f"/api/2.0/genie/spaces/{identificador}", payload, args.perfil)
        acao = "atualizado"
    else:
        payload.update({"title": args.titulo, "description": "Copiloto de operações sobre dados sintéticos da camada gold."})
        if args.parent_path:
            payload["parent_path"] = args.parent_path
        resposta = enviar_json("post", "/api/2.0/genie/spaces", payload, args.perfil)
        identificador = resposta["space_id"]
        acao = "criado"
    print(f"Espaço {acao}: {identificador}")


if __name__ == "__main__":
    principal()
