"""Testes opcionais de acesso efetivo com uma segunda identidade no mesmo workspace."""

import json
import subprocess

import pytest

pytestmark = pytest.mark.databricks


def consultar_com_identidade(perfil, sql):
    """Consulta sem imprimir conteúdo das colunas pessoais ou credenciais."""
    return subprocess.run(
        ["databricks", "experimental", "aitools", "tools", "query", "--profile", perfil, "--output", "json"],
        input=sql, capture_output=True, text=True, encoding="utf-8", timeout=300, check=False,
    )


@pytest.fixture(scope="module")
def identidade_externa(perfil_nao_atendimento, perfil):
    """Confirma a identidade corrente e a ausência de vínculo com atendimento."""
    descricoes = []
    for nome in (perfil, perfil_nao_atendimento):
        resultado = subprocess.run(
            ["databricks", "auth", "describe", "--profile", nome, "-o", "json"],
            capture_output=True, text=True, encoding="utf-8", timeout=60, check=False,
        )
        assert resultado.returncode == 0, "Não foi possível verificar o workspace de um dos perfis"
        descricoes.append(json.loads(resultado.stdout))
    assert descricoes[0]["details"]["host"] == descricoes[1]["details"]["host"], "Os perfis usam workspaces diferentes"
    assert descricoes[0].get("username") != descricoes[1].get("username"), "Os perfis usam a mesma identidade"
    resultado = consultar_com_identidade(perfil_nao_atendimento, "SELECT current_user() AS usuario, is_member('atendimento') AS membro")
    assert resultado.returncode == 0, "Não foi possível verificar a identidade no workspace de teste"
    linha = json.loads(resultado.stdout)[0]
    assert linha["usuario"], "A identidade do perfil de teste não foi identificada"
    assert str(linha["membro"]).lower() == "false", "O perfil de teste pertence ao grupo atendimento"
    return perfil_nao_atendimento


def test_mascaras_ocultam_dados_para_usuario_fora_do_grupo(identidade_externa, catalogo):
    """Consulta apenas contagens e exige máscara nas três colunas para quem tem SELECT."""
    resultado = consultar_com_identidade(identidade_externa, f"""
      SELECT count(*) AS total, count_if(nome_solicitante IS NULL OR nome_solicitante <> '[RESTRITO]'
        OR telefone_solicitante IS NULL OR telefone_solicitante <> '[RESTRITO]'
        OR transcricao IS NULL OR transcricao <> '[RESTRITO]') AS nao_mascarados
      FROM `{catalogo}`.bronze.chamados
    """)
    assert resultado.returncode == 0, "O perfil de teste precisa de SELECT na tabela para validar a máscara"
    linha = json.loads(resultado.stdout)[0]
    assert int(linha["total"]) > 0
    assert int(linha["nao_mascarados"]) == 0


def test_landing_de_chamados_nao_esta_aberta_a_identidade_externa(identidade_externa, catalogo):
    """Um perfil de consulta mascarada não deve conseguir ler os arquivos originais."""
    resultado = consultar_com_identidade(identidade_externa, f"""
      SELECT count(*) FROM parquet.`/Volumes/{catalogo}/raw/landing/chamados/`
    """)
    assert resultado.returncode != 0, "A identidade externa conseguiu ler os arquivos originais na landing"
    erro = (resultado.stderr + resultado.stdout).upper()
    assert any(codigo in erro for codigo in ("PERMISSION_DENIED", "INSUFFICIENT_PERMISSIONS", "ACCESS_DENIED")), (
        "Falha na consulta não foi identificada como negação de acesso; verifique o erro no workspace"
    )
