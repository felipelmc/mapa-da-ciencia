"""Modelos do contrato de dados v1 (arquivos de `saida/dados/`).

Convenções:
- Todo arquivo tem `versao_contrato`. Mudança incompatível = nova versão maior; versões menores
  (1.1, 1.2…) só acrescentam campos, e quem lê a 1.0 lê qualquer 1.x.
- Tabelas grandes são **colunares**: `colunas` com listas do mesmo tamanho, e campos
  categóricos guardados como índices em `dicionarios` (economiza espaço e acelera o
  filtro cruzado no navegador). `-1` significa "sem valor".
- Resumos e evidências ficam fora de `documentos.json`, em fragmentos
  `detalhes/{00..3f}.json`, carregados sob demanda (ver `fragmento_de`).
- Nenhum arquivo do contrato pode conter e-mails ou codificações humanas individuais (as divergências de
  `validacao.json` vêm só de codificadores de referência; as de pessoas ficam na API local do painel).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

VERSAO_CONTRATO = "1.5"
# 1.1: marcas do texto de análise, fonte do rótulo, núcleo dos tópicos, ruído por ano
# 1.2: tendências (com o método), séries dos macrotemas, sem tópico por ano, geografia completa
# 1.3: classificação por variável, evidência dispensada e campo da evidência, participantes da validação com o
#      tipo, métricas por classe, comparação entre modelos
# 1.4: publicação no manifesto (quando e o que o `mapa publicar` retirou)
# 1.5: júri de modelos locais (votos e estágio por documento da amostra, resumo na validação), família dos
#      participantes e comparações circulares; redes (`redes.json`) e citações (`citacoes.json`)
N_FRAGMENTOS = 64
SIGLAS_UF = (
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
)  # fmt: skip
NAO_IDENTIFICADA = "nao-identificada"

StatusEvidencia = Literal["literal", "aproximada", "ausente", "dispensada"]
TipoParticipante = Literal["humano", "referencia", "modelo"]
Atribuicao = Literal["cluster", "vizinho"]
FonteAnalise = Literal["resumo", "reserva", "so_titulo"]
FonteRotulo = Literal["llm", "palavras", "manual"]
DirecaoTendencia = Literal["alta", "queda", "estavel", "insuficiente"]
MotivoTendencia = Literal["poucos_anos", "poucos_documentos", "sem_variacao", "sem_convergencia"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Arquivo(_Base):
    versao_contrato: str = Field(
        VERSAO_CONTRATO,
        pattern=r"^1\.\d+$",
        description="Versão do contrato. Versões 1.x só acrescentam campos: quem lê 1.0 lê qualquer 1.x.",
    )


def fragmento_de(doc_id: str) -> str:
    """Nome do fragmento de detalhes (`"00"`…`"3f"`) de um documento: FNV-1a 32 bits do id, módulo 64.

    A mesma função existe no frontend (`frontend/src/lib/dados/fragmentos.ts`); os testes
    garantem que as duas dão o mesmo resultado.
    """
    h = 0x811C9DC5
    for byte in doc_id.encode("utf-8"):
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h % N_FRAGMENTOS:02x}"


# ---------------------------------------------------------------- manifesto.json
class ProjetoInfo(_Base):
    """Identificação do projeto."""

    nome: str
    titulo: str
    descricao: str = ""


class RecorteInfo(_Base):
    """Recorte do corpus: período, fontes e idiomas."""

    anos: tuple[int, int]
    fontes: list[str] = Field(description="Ex.: ['scielo:scl', 'openalex'].")
    idioma_analise: str
    idioma_exibicao: str


class Contagens(_Base):
    """Números do corpus, usados na capa do painel."""

    documentos: int
    topicos: int = 0
    classificados: int = 0
    validados: int = 0
    com_afiliacao: int = 0
    com_instituicao: int = Field(0, description="Documentos com ao menos uma instituição identificada.")


class ExecucaoInfo(_Base):
    """Dados de reprodutibilidade da última execução de cada etapa."""

    versao_pacote: str
    modelos: dict[str, str] = Field(default_factory=dict, description="Papel → `modelo@digest`.")
    hash_codebook: str | None = None
    sementes: dict[str, int] = Field(default_factory=dict)
    duracao_s: dict[str, float] = Field(default_factory=dict, description="Etapa → segundos da última execução.")


class PublicacaoInfo(_Base):
    """O que o `mapa publicar` fez: quando, e quantos resumos foram ou não publicados."""

    em: datetime
    resumos_publicados: int = Field(description="Resumos com licença Creative Commons, publicados sem alteração.")
    resumos_retirados: int = Field(
        description="Resumos que ficaram de fora (licença não aberta, desconhecida ou `--sem-resumos`)."
    )
    sem_resumos: bool = False


class Manifesto(_Arquivo):
    """Índice do projeto publicado: o que existe, de onde veio e como foi gerado. É o primeiro arquivo que
    a interface lê.
    """

    api: bool = Field(description="True no painel local (há API); False no site estático publicado.")
    gerado_em: datetime
    projeto: ProjetoInfo
    recorte: RecorteInfo
    contagens: Contagens
    arquivos: list[str] = Field(description="Arquivos do contrato presentes nesta pasta.")
    execucao: ExecucaoInfo
    licencas: dict[str, int] = Field(default_factory=dict, description="Licença → número de documentos.")
    publicacao: PublicacaoInfo | None = Field(None, description="Presente só no site publicado (`mapa publicar`).")
    desatualizadas: list[str] = Field(
        default_factory=list,
        description="Etapas com resultado desatualizado (as entradas mudaram depois), que por isso ficou fora destes "
        "dados: `topicos`, `geografia`, `redes` ou `classificacao`. A interface diz o que rodar de novo.",
    )


# ---------------------------------------------------------------- revistas.json
class Revista(_Base):
    """Uma revista do corpus."""

    id: str = Field(description="Acrônimo no SciELO, ex.: `dados`.")
    issn: str
    titulo: str
    areas: list[str] = Field(default_factory=list)
    n: int


class Revistas(_Arquivo):
    """Revistas presentes no corpus, com o número de documentos de cada uma."""

    revistas: list[Revista]


# ---------------------------------------------------------------- documentos.json
class ColunasDocumentos(_Base):
    """Colunas da tabela de documentos (todas com `n` itens, na mesma ordem)."""

    id: list[str]
    doi: list[str | None]
    titulo: list[str]
    ano: list[int]
    revista: list[int] = Field(description="Índice em `dicionarios.revista`.")
    idioma: list[int] = Field(description="Índice em `dicionarios.idioma` (idioma do resumo exibido).")
    x: list[float]
    y: list[float]
    topico: list[int] = Field(description="Id do tópico (ver topicos.json) ou -1.")
    atribuicao: list[int] = Field(
        description="Índice em `dicionarios.atribuicao`: `cluster` (o HDBSCAN agrupou o documento) ou `vizinho` "
        "(o HDBSCAN o deixou sem tópico; os vizinhos o atribuíram, ou não, se `topico` = -1)."
    )
    autores_curto: list[str] = Field(description="Ex.: `Limongi, F.; +2`.")
    vizinhos: list[list[int]] = Field(description="Índices (nesta tabela) dos 5 documentos mais próximos.")
    cls: dict[str, list[int]] = Field(
        default_factory=dict, description="Variável do codebook → índice em `dicionarios.cls[variavel]` ou -1."
    )


class DicionariosDocumentos(_Base):
    """Valores por trás dos índices das colunas categóricas."""

    revista: list[str]
    idioma: list[str]
    atribuicao: list[Atribuicao] = ["cluster", "vizinho"]
    cls: dict[str, list[str]] = Field(default_factory=dict)


class Documentos(_Arquivo):
    """Tabela principal: um documento por posição, com coordenadas no mapa, tópico e classificações."""

    n: int
    colunas: ColunasDocumentos
    dicionarios: DicionariosDocumentos

    @model_validator(mode="after")
    def _colunas_do_mesmo_tamanho(self) -> Documentos:
        c = self.colunas
        tamanhos = {nome: len(v) for nome, v in c if isinstance(v, list)}
        tamanhos |= {f"cls.{k}": len(v) for k, v in c.cls.items()}
        errados = {k: t for k, t in tamanhos.items() if t != self.n}
        if errados:
            raise ValueError(f"colunas com tamanho diferente de n={self.n}: {errados}")
        return self


# ---------------------------------------------------------------- afiliacoes.json
class Instituicao(_Base):
    """Uma instituição de afiliação, já normalizada."""

    id: str = Field(
        description="`ror:…` quando houver, `openalex:I…` sem ROR, um apelido do projeto, ou `nao-identificada` "
        "(reservado: afiliação informada que não casou com nenhuma instituição)."
    )
    nome: str
    sigla: str | None = None
    uf: str | None = None
    pais: str = Field(description="ISO 3166-1 alfa-2; vazio em `nao-identificada`.")


class ColunasAfiliacoes(_Base):
    """Colunas da tabela longa de afiliações: uma linha por documento × (instituição, UF, país), pesos somados."""

    doc: list[int] = Field(description="Índice do documento em documentos.json.")
    instituicao: list[int] = Field(
        description="Índice em `dicionarios.instituicao`, ou -1 quando o autor não informou afiliação."
    )
    uf: list[int] = Field(description="Índice em `dicionarios.uf` ou -1 (fora do Brasil ou desconhecida).")
    pais: list[int] = Field(description="Índice em `dicionarios.pais` ou -1 (desconhecido).")
    peso: list[float] = Field(
        description="Contagem fracionária: 1 por documento, dividido entre os autores e depois entre as afiliações "
        "de cada um. A soma por documento é 1."
    )


class DicionariosAfiliacoes(_Base):
    """Instituições, UFs e países por trás dos índices."""

    instituicao: list[Instituicao]
    uf: list[str] = Field(description="Siglas das UFs (as 27, em ordem alfabética, para índices estáveis).")
    pais: list[str] = Field(description="Códigos ISO 3166-1 alfa-2 presentes nas afiliações.")


class Afiliacoes(_Arquivo):
    """Afiliações com contagem fracionária, base da vista de geografia."""

    n: int
    colunas: ColunasAfiliacoes
    dicionarios: DicionariosAfiliacoes


# ---------------------------------------------------------------- detalhes/{xx}.json
class Evidencia(_Base):
    """Valor de uma variável do codebook e o trecho do resumo que o justifica."""

    valor: str | bool | list[str] | None
    evidencia: str
    status: StatusEvidencia = Field(
        description="`literal`: o trecho está no texto; `aproximada`: quase (90% dos caracteres); `ausente`: não "
        "está; `dispensada`: vazia numa resposta sem informação."
    )
    inicio: int | None = Field(
        None,
        description="Posição do trecho no resumo exibido, se localizado, em pontos de código Unicode (como o Python "
        "conta; em JavaScript, converta para UTF-16).",
    )
    fim: int | None = None
    campo: Literal["titulo", "resumo"] | None = Field(
        None, description="Onde o trecho foi localizado; `inicio` e `fim` são posições nesse texto."
    )


class VotoJuri(_Base):
    """O voto de um membro do júri numa variável, numa rodada (1: votação; 2: deliberação)."""

    membro: str
    rodada: Literal[1, 2]
    valor: str | bool | list[str] | None
    evidencia: str = Field(description="Vazia no site publicado quando a licença do resumo não é aberta.")
    status: StatusEvidencia
    revisou: bool = Field(False, description="Na rodada 2: o membro mudou de valor na deliberação.")


class DecisaoJuri(_Base):
    """Como o júri decidiu uma variável de um documento da amostra de validação."""

    etapa: Literal["unanime", "maioria", "deliberacao", "sem_maioria"]
    virou: bool = Field(False, description="A deliberação mudou a decisão (outra maioria, ou antes não havia).")
    valor: str | bool | list[str] | None = Field(description="A decisão final (com o supervisor, se ele decidiu).")
    valor_sem_supervisor: str | bool | list[str] | None
    supervisor: str | None = Field(None, description="Quem arbitrou, quando não houve maioria.")
    justificativa: str | None = Field(None, description="A justificativa do supervisor (vazia no site publicado).")
    votos: list[VotoJuri] = Field(default_factory=list)


class Detalhe(_Base):
    """O que a interface mostra ao abrir um documento: resumo, autores, licença e evidências."""

    resumo: str | None = Field(description="None quando a licença não permite publicar o resumo.")
    idioma: str | None
    palavras_chave: list[str] = Field(default_factory=list)
    autores: list[str]
    url: str | None
    licenca: str
    licenca_fonte: str
    evidencias: dict[str, Evidencia] = Field(default_factory=dict)
    idioma_analise: str | None = Field(None, description="Idioma do texto usado nos embeddings e nos tópicos.")
    fonte_analise: FonteAnalise | None = Field(
        None,
        description="`resumo`: título e resumo no idioma de análise; `reserva`: resumo em outro idioma (não havia "
        "no de análise); `so_titulo`: o documento não tem resumo. O texto em si não é publicado.",
    )
    juri: dict[str, DecisaoJuri] = Field(
        default_factory=dict, description="Variável → decisão do júri (só nos documentos da amostra, com júri)."
    )


class Fragmento(_Arquivo):
    """Um dos 64 fragmentos de detalhes, carregados sob demanda."""

    fragmento: str
    documentos: dict[str, Detalhe]


# ---------------------------------------------------------------- topicos.json
class Serie(_Base):
    """Série temporal de um tópico."""

    n: list[int] = Field(description="Documentos por ano, alinhado a `anos`.")
    prop: list[float] = Field(description="Proporção do total do ano.")


class Tendencia(_Base):
    """Tendência da participação anual no período inteiro, sem filtros (ADR 0009): o gabarito para o painel."""

    direcao: DirecaoTendencia
    inclinacao: float | None = Field(None, description="Inclinação na escala logit, por ano.")
    erro_padrao: float | None = Field(None, description="Erro-padrão da inclinação, já corrigido pela dispersão.")
    ic95: tuple[float, float] | None = None
    dispersao: float | None = Field(None, description="φ de Pearson (1 na binomial pura).")
    prop_inicio: float | None = Field(None, description="Participação ajustada no primeiro ano com documentos.")
    prop_fim: float | None = Field(None, description="Participação ajustada no último ano com documentos.")
    pp_periodo: float | None = Field(None, description="Variação em pontos percentuais no período.")
    pp_por_ano: float | None = None
    anos: tuple[int, int] | None = None
    motivo: MotivoTendencia | None = Field(None, description="Por que não há tendência, quando é `insuficiente`.")


class MetodoTendencia(_Base):
    """Como a tendência é calculada. O painel lê daqui os parâmetros para recalcular com os filtros."""

    modelo: Literal["logistica_binomial"] = "logistica_binomial"
    dispersao: Literal["quase", "binomial"] = "quase"
    nivel: float = 0.95
    z: float = 1.959963984540054
    anos_minimos: int = 5
    docs_minimos: int = 10


class Topico(_Base):
    """Um tópico: rótulo e descrição escritos pelo LLM, palavras-chave, cor estável e série no tempo."""

    id: int
    macro_id: int
    rotulo: str
    descricao: str
    palavras_chave: list[tuple[str, float]]
    n: int
    centroide: tuple[float, float]
    cor: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    serie: Serie
    por_revista: dict[str, int]
    representativos: list[str] = Field(description="Ids de documentos.")
    rotulo_fonte: FonteRotulo = Field(
        "llm", description="Quem escreveu o rótulo: o modelo de linguagem, as palavras-chave ou você (rotulos.yaml)."
    )
    n_nucleo: int | None = Field(
        None, description="Documentos do núcleo, que o HDBSCAN agrupou (os demais foram reatribuídos por vizinhança)."
    )
    tendencia: Tendencia | None = None


class Macrotema(_Base):
    """Agrupamento de tópicos próximos, usado para a cor e a navegação."""

    id: int
    rotulo: str
    cor: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    topicos: list[int]
    descricao: str = ""
    serie: Serie | None = Field(None, description="Soma das séries dos tópicos do macrotema.")
    tendencia: Tendencia | None = None


class Outliers(_Base):
    """Documentos que o agrupamento não encaixou em nenhum tópico."""

    n: int = Field(description="Documentos que o HDBSCAN deixou sem tópico.")
    reatribuidos: int = Field(description="Quantos deles foram atribuídos ao tópico mais próximo.")
    por_ano: list[int] = Field(
        default_factory=list,
        description="Documentos que o HDBSCAN deixou de fora, por ano (inclui os reatribuídos depois), alinhado a "
        "`anos`.",
    )
    sem_topico_por_ano: list[int] = Field(
        default_factory=list, description="Documentos que ficaram sem tópico (−1) no fim, por ano."
    )


class Topicos(_Arquivo):
    """Tópicos e macrotemas do corpus, com as séries por ano."""

    anos: list[int]
    total_por_ano: list[int]
    parametros: dict[str, float | int | str]
    estabilidade_ari: float | None
    macrotemas: list[Macrotema]
    topicos: list[Topico]
    outliers: Outliers
    metodo_tendencia: MetodoTendencia | None = None


# ---------------------------------------------------------------- codebook.json
class CategoriaContrato(_Base):
    """Categoria de uma variável, como o codebook define."""

    valor: str
    rotulo: str
    definicao: str
    exemplos: list[str] = Field(default_factory=list)


class VariavelContrato(_Base):
    """Variável do codebook."""

    id: str
    rotulo: str
    tipo: Literal["categorica", "multipla", "booleana", "texto"]
    pergunta: str
    categorias: list[CategoriaContrato] = Field(default_factory=list)


class CodebookContrato(_Arquivo):
    """Cópia publicada do codebook, com o hash que identifica a versão usada."""

    nome: str
    versao: str
    hash: str
    instrucoes: str
    variaveis: list[VariavelContrato]


# ---------------------------------------------------------------- classificacoes.json
class VariavelClassificada(_Base):
    """Como uma variável saiu na classificação."""

    n: int = Field(description="Documentos com resposta nesta variável.")
    sem_informacao: float = Field(
        description="Fração das respostas sem informação (`nao_informado`, `nao_se_aplica` ou falso)."
    )
    evidencia: dict[str, float] = Field(
        default_factory=dict, description="Status → fração das evidências, sem as dispensadas."
    )


class Classificacoes(_Arquivo):
    """Resumo da classificação por codebook: modelo, cobertura e contagens por categoria."""

    modelo: str
    hash_codebook: str
    cobertura: float = Field(description="Fração dos documentos com classificação válida.")
    evidencia_literal: float = Field(description="Fração das evidências encontradas literalmente no resumo.")
    contagens: dict[str, dict[str, int]] = Field(
        description="Variável → valor → documentos. Nas de múltipla escolha, cada categoria conta à parte; as de "
        "texto ficam de fora."
    )
    classificados: int = 0
    documentos: int = Field(0, description="Documentos com resumo, que podiam ser classificados.")
    sem_resumo: int = 0
    parcial: bool = Field(False, description="A classificação ainda não cobre todos os documentos com resumo.")
    json_valido_na_primeira: float | None = None
    por_variavel: dict[str, VariavelClassificada] = Field(default_factory=dict)


# ---------------------------------------------------------------- validacao.json
class Matriz(_Base):
    """Matriz de confusão entre dois participantes."""

    rotulos: list[str]
    valores: list[list[int]] = Field(description="Linhas = a referência do par; colunas = o outro participante.")


class MetricaClasse(_Base):
    """Precisão, revocação e F1 de uma categoria, tomando o primeiro do par como referência."""

    rotulo: str
    suporte: int = Field(description="Quantas vezes a referência deu esta categoria.")
    precisao: float | None
    revocacao: float | None
    f1: float | None


class MetricaVariavel(_Base):
    """Concordância entre dois participantes (codificador × modelo, codificadores ou modelos) numa variável.
    Nas de múltipla escolha, `variavel` é `id:categoria` (uma variável sim/não por categoria)."""

    variavel: str
    comparacao: str = Field(description="Ex.: `claude-opus × qwen3.5:9b` (referência primeiro).")
    n: int
    concordancia: float | None
    kappa: float | None
    kappa_ic95: tuple[float, float] | None
    pabak: float | None
    alfa: float | None
    matriz: Matriz
    referencia: str = Field("", description="Participante tomado como referência (linhas da matriz).")
    comparado: str = ""
    por_classe: list[MetricaClasse] = Field(default_factory=list)
    circular: bool = Field(
        False,
        description="Os dois participantes são da mesma família de modelo (a referência e o supervisor do júri, "
        "por exemplo): um limite superior, e não uma medida independente.",
    )


class Divergencia(_Base):
    """Um caso em que um codificador de referência e o modelo principal discordam, para arbitragem."""

    doc: str
    variavel: str
    humano: str = Field(description="Valor dado pelo codificador (o nome do campo vem da versão 1.0).")
    modelo: str
    evidencia: str = Field(description="Trecho que o modelo citou.")
    codificador: str = ""
    status: StatusEvidencia | None = None
    incerto: bool = Field(False, description="O codificador marcou a resposta como incerta.")


class AmostraInfo(_Base):
    """Como a amostra de validação foi sorteada."""

    n: int
    estratificar_por: str
    semente: int


class Participante(_Base):
    """Quem respondeu na amostra: um codificador (`humano` ou `referencia`, que não é uma pessoa) ou um modelo."""

    nome: str
    tipo: TipoParticipante
    n: int = Field(description="Documentos da amostra com resposta.")
    familia: str | None = Field(None, description="Família de modelo, quando se conhece (ver `circular`).")


class ComparacaoModelos(_Base):
    """McNemar exato entre dois modelos, contra a mesma referência, numa variável."""

    variavel: str
    referencia: str
    modelo_a: str
    modelo_b: str
    n: int
    acertos_a: int
    acertos_b: int
    p: float


class AuditoriaJuri(_Base):
    """A conferência, pelo supervisor, de uma amostra das decisões unânimes do júri."""

    n: int
    erros: int
    taxa: float | None
    ic95: tuple[float, float] | None = Field(description="Intervalo de Wilson de 95% da taxa de erro.")
    por_variavel: dict[str, tuple[int, int]] = Field(default_factory=dict, description="Variável → (erros, n).")


class ConcordanciaSupervisor(_Base):
    """A concordância com a referência nas decisões sem maioria que o supervisor arbitrou, com a escolha dele."""

    n: int
    acertos: int
    circular: bool = Field(description="O supervisor e a referência são da mesma família: não é medida independente.")


class ResumoJuri(_Base):
    """O júri de modelos locais na amostra: estágios, deliberação, concordância por estágio e auditoria."""

    referencia: str | None = Field(description="O codificador tomado como referência nas contagens.")
    membros: list[str]
    supervisor: str | None
    familia_supervisor: str | None
    documentos: int
    etapas: dict[str, dict[str, int]] = Field(description="Variável → estágio → decisões.")
    virou: dict[str, int] = Field(default_factory=dict, description="Variável → decisões que a deliberação mudou.")
    concordancia_por_etapa: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Estágio → {n, acertos} contra a referência, com a decisão do júri sem o supervisor (no estágio "
        "`sem_maioria`, o voto do primeiro membro).",
    )
    concordancia_supervisor: ConcordanciaSupervisor | None = Field(
        None, description="Nas decisões sem maioria arbitradas, a concordância com a escolha do supervisor."
    )
    deliberacao: dict[str, dict[str, int]] = Field(
        default_factory=dict,
        description="Membro → {votos, mudou, para_referencia, contra}: votos revistos na deliberação e a direção.",
    )
    auditoria: AuditoriaJuri | None = None


class Validacao(_Arquivo):
    """Resultados da validação da classificação: concordância por variável e por par de participantes."""

    amostra: AmostraInfo
    metricas: list[MetricaVariavel]
    modelos: list[str]
    divergencias: list[Divergencia]
    codificadores: list[Participante] = Field(default_factory=list, description="Participantes, com o tipo.")
    modelo_principal: str | None = None
    hash_codebook: str | None = None
    comparacoes_modelos: list[ComparacaoModelos] = Field(default_factory=list)
    evidencia_literal: dict[str, float] = Field(
        default_factory=dict, description="Modelo → fração das evidências literais na amostra."
    )
    juri: ResumoJuri | None = Field(None, description="O júri de modelos locais, quando o projeto tem um.")


# ---------------------------------------------------------------- agregados.json
class Agregados(_Arquivo):
    """Gabarito calculado no Python para testar o filtro cruzado do frontend."""

    topico_ano_revista: list[tuple[int, int, str, int]] = Field(description="(tópico, ano, revista, n).")
    uf: dict[str, float] = Field(description="Contagem fracionária por UF (sigla).")
    pais: dict[str, float] = Field(description="Contagem fracionária por país (ISO alfa-2).")
    instituicao: dict[str, float] = Field(default_factory=dict, description="Contagem fracionária por instituição.")
    uf_inteiro: dict[str, int] = Field(default_factory=dict, description="Documentos com alguma afiliação na UF.")
    pais_inteiro: dict[str, int] = Field(default_factory=dict)
    instituicao_inteiro: dict[str, int] = Field(default_factory=dict)
    sem_afiliacao: float = Field(0, description="Peso dos autores sem afiliação informada.")
    sem_pais: float = Field(0, description="Peso das afiliações de país desconhecido (inclui `sem_afiliacao`).")
    arestas_coautoria: int = Field(0, description="Pares de coautores no corpus inteiro.")
    uf_pares: list[tuple[str, str, float, int]] = Field(
        default_factory=list, description="(UF, UF ou EX, peso, documentos) na colaboração entre estados."
    )
    canone_n: list[int] = Field(default_factory=list, description="Documentos que citam cada obra do cânone.")


# ---------------------------------------------------------------- redes.json e citacoes.json
class ColunasPessoas(_Base):
    """As pessoas (autores identificados), em colunas. `x` e `y` só para quem teve coautor (o desenho da rede)."""

    id: list[str] = Field(
        description="Id publicado: um HMAC curto do id interno com o segredo do projeto (o site não publica ORCIDs "
        "nem ids do OpenAlex, e o id não se liga a eles sem o segredo)."
    )
    nome: list[str]
    documentos: list[int]
    grau: list[int] = Field(description="Coautores distintos.")
    comunidade: list[int] = Field(description="Índice em `comunidades` da rede de coautoria; -1 nas pequenas.")
    x: list[float | None]
    y: list[float | None]


class AutoriasRede(_Base):
    """Quem escreveu cada documento: pares (índice do documento em `documentos.json`, índice da pessoa)."""

    doc: list[int]
    pessoa: list[int]


class ColunasInstituicoesRede(_Base):
    """As instituições que colaboraram com outra, com o desenho da rede (os ids são os de `afiliacoes.json`)."""

    id: list[str]
    grau: list[int]
    comunidade: list[int]
    x: list[float]
    y: list[float]


class ComunidadeRede(_Base):
    rede: Literal["coautoria", "instituicoes"]
    id: int
    n: int = Field(description="Nós da comunidade.")
    documentos: int
    macro: int | None = Field(description="Macrotema mais frequente nos documentos da comunidade.")
    topicos: list[int] = Field(description="Os tópicos mais frequentes, em ordem.")
    rotulo: str = Field(description="Os dois tópicos mais frequentes (a comunidade não recebe nome de pessoa).")


class MetricasRede(_Base):
    nos: int
    arestas: int
    componentes: int
    maior_componente: int
    fracao_maior: float
    densidade: float
    grau_medio: float
    agrupamento: float
    modularidade: float | None


class ColaboracaoAno(_Base):
    """A colaboração num ano, em frações dos documentos do ano."""

    ano: int
    documentos: int
    com_coautoria: float
    autores_medio: float
    com_instituicoes: float | None = Field(None, description="Duas ou mais instituições identificadas.")
    entre_ufs: float | None = Field(None, description="Duas ou mais UFs brasileiras.")
    com_exterior: float | None = Field(None, description="Brasil e exterior no mesmo documento.")


class Redes(_Arquivo):
    """Coautoria (pessoas), colaboração entre instituições e as séries da colaboração."""

    pessoas: ColunasPessoas
    autorias: AutoriasRede
    instituicoes: ColunasInstituicoesRede | None = None
    comunidades: list[ComunidadeRede] = Field(default_factory=list)
    metricas: dict[str, MetricasRede] = Field(default_factory=dict)
    colaboracao: list[ColaboracaoAno] = Field(default_factory=list)
    parametros: dict[str, Any] = Field(default_factory=dict)


class ObraCitada(_Base):
    """Uma obra de fora do corpus entre as mais citadas (o cânone), na ordem de `n` (e do id, no empate)."""

    id: str = Field(description="Id do OpenAlex (`W…`).")
    titulo: str | None
    ano: int | None = Field(
        description="O ano da obra (o das referências, quando o registro do OpenAlex é uma resenha)."
    )
    autores: list[str] = Field(description="Até três autores, conferidos nas referências da ArticleMeta.")
    veiculo: str | None
    tipo: str | None
    doi: str | None
    n: int = Field(description="Documentos do corpus que a citam.")
    edicoes: list[str] = Field(default_factory=list, description="Outros registros da mesma obra, somados a este.")
    resenha: bool = Field(
        False,
        description="O registro do OpenAlex é uma resenha da obra (tipo `book-review`, Choice Reviews, ou um primeiro "
        "autor que as referências não citam): autores e ano vêm das referências.",
    )
    registro_openalex: str | None = Field(
        None,
        description="Autores e ano do registro do OpenAlex, quando diferem dos mostrados (a conferência os mudou).",
    )


class ArestasCitacao(_Base):
    """Citações dentro do corpus: índices de documentos (quem cita → quem é citado)."""

    de: list[int]
    para: list[int]


class CitantesCanone(_Base):
    doc: list[int]
    obra: list[int] = Field(description="Índice em `canone`.")


class Citacoes(_Arquivo):
    """A rede de citação pelas referências do OpenAlex e o cânone."""

    n_referencias: list[int] = Field(
        description="Referências de cada documento resolvidas no OpenAlex (0: casado, sem nenhuma); -1: sem casamento."
    )
    internas: ArestasCitacao
    canone: list[ObraCitada]
    canone_citantes: CitantesCanone
    fluxo_macrotemas: list[list[int]] = Field(
        description="Citações internas de macrotema (linha) a macrotema (coluna), na ordem de `topicos.macrotemas` "
        "(pela posição, e não pelo id, que não é contíguo)."
    )
    cobertura: dict[str, int] = Field(
        default_factory=dict,
        description="Documentos (`documentos`, `com_referencias`), referências resolvidas (`referencias`) e, nos "
        "documentos casados, as listadas na ArticleMeta (`referencias_listadas`), as resolvidas entre elas "
        "(`referencias_resolvidas`) e a mediana por documento da fração resolvida (`resolvidas_mediana_pct`); citações "
        "internas, anacrônicas e autorreferências; referências a obras apagadas (`a_obras_apagadas`); citantes, "
        "resenhas e autorias corrigidas do cânone; obras sem metadados entre as mais citadas.",
    )


ARQUIVOS: dict[str, type[_Arquivo]] = {
    "manifesto": Manifesto,
    "revistas": Revistas,
    "documentos": Documentos,
    "afiliacoes": Afiliacoes,
    "fragmento": Fragmento,
    "topicos": Topicos,
    "codebook": CodebookContrato,
    "classificacoes": Classificacoes,
    "validacao": Validacao,
    "agregados": Agregados,
    "redes": Redes,
    "citacoes": Citacoes,
}
