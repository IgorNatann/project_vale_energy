import json
import re
import subprocess
from pathlib import Path

import pytest

TRANSFORMACOES = Path(__file__).resolve().parents[1] / "src/pipelines/grid_intelligence/transformations"


def pytest_addoption(parser):
    """Configura o acesso aos testes no workspace e a reexecução opcional em dev."""
    parser.addoption("--databricks", action="store_true", help="Executa testes no Databricks")
    parser.addoption("--perfil", default="project_vale_energy", help="Perfil da CLI Databricks")
    parser.addoption("--catalogo", default="grid_dev", help="Catálogo com as tabelas implantadas")
    parser.addoption("--reexecutar-pipeline", action="store_true", help="Reexecuta o pipeline em dev")


def pytest_collection_modifyitems(config, items):
    """Evita acesso ao warehouse e reexecução do pipeline sem opções explícitas."""
    for item in items:
        if "databricks" in item.keywords and not config.getoption("--databricks"):
            item.add_marker(pytest.mark.skip(reason="Use --databricks para executar no warehouse"))
        if "reexecucao" in item.keywords and not config.getoption("--reexecutar-pipeline"):
            item.add_marker(pytest.mark.skip(reason="Use --reexecutar-pipeline para executar o pipeline em dev"))


@pytest.fixture(scope="session")
def catalogo(request):
    """Valida o identificador antes de utilizá-lo nas consultas de integração."""
    valor = request.config.getoption("--catalogo")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", valor):
        pytest.fail("O catálogo deve conter somente letras, números e sublinhados")
    return valor


@pytest.fixture(scope="session")
def perfil(request):
    return request.config.getoption("--perfil")


@pytest.fixture(scope="session")
def consultar(perfil):
    """Executa uma consulta no warehouse com o perfil escolhido e devolve linhas JSON."""
    def executar(sql):
        comando = ["databricks", "experimental", "aitools", "tools", "query", "--profile", perfil, "--output", "json"]
        resultado = subprocess.run(comando, input=sql, capture_output=True, text=True, encoding="utf-8", timeout=300, check=False)
        if resultado.returncode:
            pytest.fail(f"Consulta falhou: {resultado.stderr}\n{resultado.stdout}")
        return json.loads(resultado.stdout)

    return executar


def consulta_transformacao(arquivo, indice=0):
    """Extrai a consulta real; os testes substituem apenas as fontes por fixtures SQL."""
    conteudo = (TRANSFORMACOES / arquivo).read_text(encoding="utf-8")
    instrucoes = [item for item in conteudo.split(";") if "CREATE OR REFRESH" in item]
    consulta = re.split(r"\bAS\s+(?=SELECT\b|WITH\b)", instrucoes[indice], maxsplit=1, flags=re.IGNORECASE)[1]
    return consulta.strip()
