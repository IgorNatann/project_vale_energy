# A sessão Spark é fornecida pelo runtime do pipeline.
# ruff: noqa: F821
from pyspark import pipelines as dp
from pyspark.sql import functions as F

catalogo = spark.conf.get("catalogo")
bronze = spark.conf.get("schema_bronze")
silver = spark.conf.get("schema_silver")
usar_ia = spark.conf.get("usar_ia", "true").lower() == "true"

CPF = r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"
TELEFONE = r"(?<!\d)(?:\(?\d{2}\)?[ .-]?)?9?\d{4}[ .-]?\d{4}(?!\d)"
RISCO = r"(?i)oxig[eê]nio|di[aá]lise|rem[eé]dio|crian[cç]a|hospital|fa[ií]sca|inc[eê]ndio|idoso"


@dp.materialized_view(
    name=f"{catalogo}.{silver}.chamados_anonimizados", table_properties={"delta.feature.timestampNtz": "supported"}
)
def chamados_anonimizados():
    """Remove dados pessoais do texto antes de disponibilizá-lo para análise."""
    chamados = spark.read.table(f"{catalogo}.{bronze}.chamados").alias("c")
    cadastro = spark.read.table(f"{catalogo}.{silver}.unidades_consumidoras").alias("u")
    dados = chamados.join(cadastro, F.col("c.id_uc") == F.col("u.id_uc"), "inner")
    texto = F.replace(F.col("c.transcricao"), F.coalesce(F.col("c.nome_solicitante"), F.lit("")), F.lit("[MASCARADO]"))
    texto = F.regexp_replace(F.regexp_replace(texto, CPF, "[MASCARADO]"), TELEFONE, "[MASCARADO]")
    if usar_ia:
        texto = F.call_function(
            "ai_mask", texto, F.array(*[F.lit(tipo) for tipo in ("person", "phone", "address", "ssn", "email")])
        )
    # Se o mascaramento não retornar texto, nunca exponha o original como fallback.
    texto = F.coalesce(texto, F.lit("[RESTRITO]"))
    return dados.select(
        "c.id_chamado",
        "c.id_uc",
        "u.id_cliente",
        "u.id_conjunto",
        "u.nome_conjunto",
        "u.bairro",
        "u.classe_consumo",
        "c.abertura",
        F.to_date("c.abertura").alias("data_chamado"),
        F.hour("c.abertura").alias("hora_chamado"),
        "c.canal",
        "c.duracao_segundos",
        "c.origem",
        "c.ingerido_em",
        "c.arquivo_origem",
        "c.ingerido_bronze_em",
        texto.alias("transcricao_anonimizada"),
        F.lit("ia" if usar_ia else "regras_de_texto").alias("anonimizado_por"),
    )


@dp.materialized_view(
    name=f"{catalogo}.{silver}.chamados_enriquecidos", table_properties={"delta.feature.timestampNtz": "supported"}
)
def chamados_enriquecidos():
    """Enriquece somente a transcrição já anonimizada."""
    dados = spark.read.table(f"{catalogo}.{silver}.chamados_anonimizados")
    texto = F.col("transcricao_anonimizada")
    disponivel = texto != "[RESTRITO]"
    risco = F.when(disponivel, texto.rlike(RISCO))
    if usar_ia:
        sentimento = F.expr("ai_analyze_sentiment(transcricao_anonimizada)")
        motivo = F.expr("""ai_classify(transcricao_anonimizada,
          '{"religacao_urgente":"Religacao urgente por pessoa em risco de saude",
            "falta_energia":"Falta ou interrupcao de energia",
            "oscilacao_tensao":"Oscilacao de tensao ou equipamento queimado",
            "erro_leitura":"Erro ou duvida na leitura do medidor",
            "fatura_alta":"Conta de energia alta ou inesperada",
            "poste_avariado":"Poste, rede ou iluminacao publica avariada",
            "religacao":"Solicitacao comum de religacao",
            "duvida_cadastral":"Duvida ou alteracao cadastral"}',
          map('version','2.0','instructions','Ligacoes para uma distribuidora de energia brasileira.')):response[0]::STRING""")
        equipamento = F.expr("""ai_extract(transcricao_anonimizada, '["equipamento_citado"]',
          map('version','2.0','instructions','Extraia o equipamento eletrico mencionado no chamado.')):response:equipamento_citado::STRING""")
    else:
        sentimento = (
            F.when(texto.rlike(r"(?i)reclama|irritad|absurdo|insatisfeit|péssim|pessim"), "negative")
            .when(texto.rlike(r"(?i)obrigad|agrade[cç]|excelente"), "positive")
            .otherwise("neutral")
        )
        motivo = (
            F.when(risco, "religacao_urgente")
            .when(texto.rlike(r"(?i)escuro|sem energia|apagou|falta de energia|sem luz"), "falta_energia")
            .when(texto.rlike(r"(?i)piscando|oscila|queimou|tens[aã]o"), "oscilacao_tensao")
            .when(texto.rlike(r"(?i)releitura|estimativa|n[aã]o bate"), "erro_leitura")
            .when(texto.rlike(r"(?i)conta veio|dobro|fatura subiu|trezentos reais"), "fatura_alta")
            .when(texto.rlike(r"(?i)poste|galho|l[aâ]mpada da rua"), "poste_avariado")
            .when(texto.rlike(r"(?i)religa[cç][aã]o|religar|paguei"), "religacao")
            .otherwise("duvida_cadastral")
        )
        equipamento = F.regexp_extract(texto, r"(?i)poste|transformador|medidor|geladeira|chuveiro", 0)
    return (
        dados.withColumn(
            "sentimento", F.when(disponivel, F.coalesce(sentimento, F.lit("indisponivel"))).otherwise("indisponivel")
        )
        .withColumn("motivo", F.when(disponivel, F.coalesce(motivo, F.lit("indisponivel"))).otherwise("indisponivel"))
        .withColumn("equipamento_citado", F.when(disponivel, equipamento))
        .withColumn("risco_a_saude", risco)
        .withColumn(
            "urgencia",
            F.when(~disponivel, "indeterminada")
            .when(risco, "alta")
            .when(F.col("motivo") == "indisponivel", "indeterminada")
            .when(F.col("motivo").isin("falta_energia", "religacao_urgente", "poste_avariado"), "media")
            .otherwise("baixa"),
        )
        .withColumn("ameacou_ouvidoria", F.when(disponivel, texto.rlike(r"(?i)ouvidoria|aneel|procon|processo")))
        .withColumn("enriquecido_por", F.lit("ia" if usar_ia else "regras_de_texto"))
    )
