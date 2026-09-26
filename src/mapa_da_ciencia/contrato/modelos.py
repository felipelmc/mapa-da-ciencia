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
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

VERSAO_CONTRATO = "1.3"
# 1.1: marcas do texto de análise, fonte do rótulo, núcleo dos tópicos, ruído por ano
# 1.2: tendências (com o método), séries dos macrotemas, sem tópico por ano, geografia completa
# 1.3: classificação por variável, evidência dispensada e campo da evidência, participantes da validação com o
#      tipo, métricas por classe, comparação entre modelos
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
    inicio: int | None = Field(None, description="Posição do trecho no resumo exibido (caracteres), se localizado.")
    fim: int | None = None
    campo: Literal["titulo", "resumo"] | None = Field(
        None, description="Onde o trecho foi localizado; `inicio` e `fim` são posições nesse texto."
    )


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
}
