"""Modelos de configuração do projeto (`mapa.yaml`) e do codebook (`codebook.yaml`).

São a fonte da verdade do formato desses arquivos: a documentação de referência e os
JSON Schemas publicados são gerados a partir daqui. Erros de validação viram
`ErroConfig`, com mensagens em português que apontam o campo problemático.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

Slug = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$", description="Identificador em minúsculas, sem acento.")]
Issn = Annotated[str, Field(pattern=r"^\d{4}-\d{3}[\dX]$", description="ISSN no formato 0000-0000.")]
Idioma = Literal["pt", "en", "es"]


class ErroConfig(ValueError):
    """Arquivo de configuração ou codebook inválido. A mensagem já vem pronta para o usuário."""


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ---------------------------------------------------------------- mapa.yaml
class FonteScielo(_Base):
    """Coleta pela ArticleMeta do SciELO, revista a revista."""

    colecao: str = Field("scl", description="Coleção do SciELO (`scl` = Brasil).")
    revistas: list[Issn] = Field(
        default_factory=list, description="ISSNs das revistas; vazio num projeto só com artigos importados."
    )
    tipos: list[str] = Field(
        ["research-article", "review-article"],
        description="Tipos de documento incluídos (`document_type` da ArticleMeta).",
    )


class FonteOpenAlex(_Base):
    """Enriquecimento (citações, licença) e busca por termo no OpenAlex."""

    enriquecer: bool = Field(True, description="Casar cada artigo com o OpenAlex para obter citações e licença.")
    consulta: str | None = Field(
        None,
        description="Busca por termo no título e no resumo, via OpenAlex. Com revistas no recorte, busca só nelas; "
        "sem revistas, em todo o SciELO. O corpus passa a ser os resultados da busca, e não as revistas inteiras.",
    )


class Fontes(_Base):
    """De onde vêm os artigos. Pode combinar mais de uma fonte."""

    scielo: FonteScielo | None = None
    openalex: FonteOpenAlex = FonteOpenAlex()
    importar: list[Path] = Field(
        default_factory=list,
        description="Arquivos RIS, CSV ou BibTeX exportados do search.scielo.org, ou listas de DOIs (.txt), "
        "relativos à pasta do projeto. Os da pasta `importados/` entram sempre, sem precisar listar aqui.",
    )


class Recorte(_Base):
    """Período e idiomas do corpus."""

    anos: tuple[int, int] = Field(description="Primeiro e último ano de publicação, inclusive.")
    idioma_analise: Idioma = Field(
        "en", description="Idioma dos textos usados nos embeddings e nos tópicos (ver ADR 0004)."
    )
    idioma_exibicao: Idioma = Field("pt", description="Idioma preferido para mostrar resumos e palavras-chave.")

    @field_validator("anos")
    @classmethod
    def _anos_em_ordem(cls, anos: tuple[int, int]) -> tuple[int, int]:
        inicio, fim = anos
        if not 1900 <= inicio <= fim <= 2100:
            raise ValueError("use [ano_inicial, ano_final], com o inicial menor ou igual ao final")
        return anos


class ModeloEmbeddings(_Base):
    """Modelo que transforma título e resumo em vetores (base dos tópicos e do mapa)."""

    provedor: Literal["ollama"] = Field("ollama", description="No MVP, só o Ollama local.")
    modelo: str = Field("qwen3-embedding:0.6b", description="Nome do modelo no Ollama (ver ADR 0004).")
    num_ctx: int = Field(
        2048,
        ge=512,
        le=32768,
        description="Contexto em tokens. Título e resumo cabem com folga em 2.048; o que passar é truncado. "
        "Contextos maiores ocupam mais memória.",
    )
    lote: int = Field(32, ge=1, le=256, description="Textos por requisição ao Ollama.")


class ModeloLLM(_Base):
    """Modelo de linguagem usado para classificar resumos ou nomear tópicos."""

    provedor: Literal["ollama"] = Field("ollama", description="No MVP, só o Ollama local.")
    modelo: str = Field("qwen3.5:9b", description="Nome do modelo no Ollama (ver `mapa diagnostico`).")
    num_ctx: int = Field(8192, ge=2048, description="Janela de contexto pedida ao Ollama.")
    temperatura: float = Field(0.0, ge=0, le=2, description="0 = respostas determinísticas (recomendado).")
    pensar: bool = Field(False, description="Liga o modo de raciocínio do modelo (mais lento).")
    concorrencia: int = Field(1, ge=1, le=16, description="Chamadas simultâneas ao Ollama.")
    semente: int = Field(7, description="Semente do gerador, para resultados reprodutíveis.")


class Modelos(_Base):
    """Modelos locais de cada papel. `mapa novo` preenche conforme a memória da máquina."""

    embeddings: ModeloEmbeddings = ModeloEmbeddings()
    classificacao: ModeloLLM = ModeloLLM()
    rotulos: ModeloLLM = ModeloLLM()


class ConfigTopicos(_Base):
    """Parâmetros do agrupamento em tópicos. Os padrões vêm da calibração no piloto (ADR 0007); para outro
    corpus, `scripts/calibrar_topicos.py` refaz a grade."""

    vizinhos: int = Field(
        15,
        ge=2,
        le=200,
        description="Vizinhos de cada documento no grafo do UMAP: mais vizinhos, estrutura mais global.",
    )
    min_dist: float = Field(
        0.0, ge=0, le=1, description="Distância mínima entre pontos no UMAP de 5 dimensões, usado no agrupamento."
    )
    min_dist_mapa: float = Field(
        0.1, ge=0, le=1, description="A mesma distância no mapa de 2 dimensões: maior, pontos mais espalhados."
    )
    min_cluster_size: int | None = Field(
        None, ge=5, description="Menor tópico, em documentos. Vazio: automático, 1 a cada 200 documentos (mínimo 10)."
    )
    min_samples: int = Field(
        5, ge=1, description="Quão conservador é o HDBSCAN: maior, mais documentos ficam de fora dos tópicos."
    )
    votos_minimos: int = Field(
        3,
        ge=1,
        le=50,
        description="Um documento que o HDBSCAN deixou sem tópico vai para o tópico com mais vizinhos seus no núcleo, "
        "se forem pelo menos estes (entre os `vizinhos` mais próximos). Menos que isso, fica sem tópico.",
    )
    selecao: Literal["eom", "leaf"] = Field(
        "leaf",
        description=(
            "`leaf` fica com as regiões densas mais finas, e os tópicos mudam pouco quando o corpus muda; `eom` "
            "prefere tópicos maiores, mas pode trocar um tópico grande por vários pequenos com uma mudança mínima."
        ),
    )
    macrotemas: int = Field(
        7,
        ge=1,
        le=8,
        description=(
            "Quantos macrotemas, no máximo (grupos de tópicos próximos, com cores bem distintas). Com poucos "
            "tópicos são menos, para que cada macrotema reúna em média ao menos 3 tópicos."
        ),
    )
    sementes: list[int] = Field(
        [42, 7, 2024],
        min_length=1,
        description="A primeira gera os tópicos; as demais medem a estabilidade (ARI entre as execuções).",
    )


class Validacao(_Base):
    """Amostra de resumos codificados por pessoas para medir a qualidade da classificação."""

    n: int = Field(200, ge=10, description="Tamanho da amostra para codificação humana.")
    estratificar_por: Literal["topico", "ano", "revista"] = Field(
        "topico", description="Garante que a amostra cubra todos os tópicos (ou anos, ou revistas)."
    )
    semente: int = Field(7, description="Semente do sorteio da amostra.")
    codificadores: list[str] = Field(default_factory=list, description="Nomes de quem vai codificar.")


class ConfigProjeto(_Base):
    """Conteúdo do `mapa.yaml`."""

    versao_config: Literal[1] = Field(1, description="Versão do formato deste arquivo.")
    nome: Slug
    titulo: str = Field(description="Título exibido no painel e no site publicado.")
    descricao: str = Field("", description="Um parágrafo sobre o recorte e o objetivo do projeto.")
    fontes: Fontes
    recorte: Recorte
    modelos: Modelos = Modelos()
    topicos: ConfigTopicos = ConfigTopicos()
    validacao: Validacao = Validacao()


# ---------------------------------------------------------------- codebook.yaml
class Categoria(_Base):
    """Uma das respostas possíveis de uma variável categórica."""

    valor: Slug
    rotulo: str | None = Field(None, description="Nome exibido; se vazio, usa o `valor`.")
    definicao: str = Field(description="Quando usar esta categoria. É o texto que o modelo lê.")
    exemplos: list[str] = Field(default_factory=list, description="Trechos típicos (opcional).")


class Variavel(_Base):
    """Uma pergunta que o modelo responde para cada resumo."""

    id: Slug
    rotulo: str = Field(description="Nome curto exibido nas tabelas e gráficos.")
    tipo: Literal["categorica", "multipla", "booleana", "texto"] = Field(
        description="`categorica`: uma categoria; `multipla`: várias; `booleana`: sim/não; "
        "`texto`: resposta livre curta."
    )
    pergunta: str = Field(description="A pergunta, como o modelo vai lê-la.")
    categorias: list[Categoria] = Field(
        default_factory=list, description="Obrigatórias (2 ou mais) em `categorica` e `multipla`."
    )

    @model_validator(mode="after")
    def _categorias_coerentes(self) -> Variavel:
        if self.tipo in ("categorica", "multipla"):
            if len(self.categorias) < 2:
                raise ValueError(f"a variável `{self.id}` ({self.tipo}) precisa de pelo menos 2 categorias")
            valores = [c.valor for c in self.categorias]
            if len(valores) != len(set(valores)):
                raise ValueError(f"a variável `{self.id}` tem categorias com o mesmo `valor`")
        elif self.categorias:
            raise ValueError(f"a variável `{self.id}` é do tipo `{self.tipo}` e não deve ter categorias")
        return self


class Codebook(_Base):
    """Conteúdo do `codebook.yaml`."""

    nome: str = Field(description="Nome do codebook.")
    versao: str = Field(description="Versão; mude sempre que alterar definições.")
    instrucoes: str = Field(description="Instruções gerais ao modelo, lidas antes das variáveis.")
    variaveis: list[Variavel] = Field(min_length=1, description="Pelo menos uma variável.")

    @field_validator("variaveis")
    @classmethod
    def _ids_unicos(cls, variaveis: list[Variavel]) -> list[Variavel]:
        ids = [v.id for v in variaveis]
        repetidos = sorted({i for i in ids if ids.count(i) > 1})
        if repetidos:
            raise ValueError(f"ids de variável repetidos: {', '.join(repetidos)}")
        return variaveis

    def hash(self) -> str:
        """Hash estável do conteúdo; muda sempre que qualquer definição muda."""
        canonico = json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonico.encode()).hexdigest()[:16]


# ---------------------------------------------------------------- leitura
def _explicar(erro: ValidationError, arquivo: Path) -> str:
    linhas = [f"{arquivo.name} tem {erro.error_count()} problema(s):"]
    for e in erro.errors():
        campo = ".".join(str(p) for p in e["loc"]) or "(raiz)"
        msg = e["msg"].removeprefix("Value error, ")
        if e["type"] == "extra_forbidden":
            msg = "campo desconhecido (erro de digitação?)"
        elif e["type"] == "missing":
            msg = "campo obrigatório ausente"
        elif campo == "recorte.anos" and e["type"] in ("tuple_type", "too_short", "too_long", "int_parsing"):
            msg = "use [ano_inicial, ano_final], por exemplo [2010, 2025]"
        linhas.append(f"  - {campo}: {msg}")
    return "\n".join(linhas)


def ler_yaml(texto: str, nome: str) -> object:
    """Lê um YAML do projeto recusando chaves repetidas: com o leitor padrão, uma seção repetida (duas `apelidos:`,
    por exemplo, ao colar um bloco no fim do arquivo) apagava a primeira em silêncio."""
    from ruamel.yaml import YAML
    from ruamel.yaml.constructor import DuplicateKeyError
    from ruamel.yaml.error import YAMLError

    try:
        return YAML(typ="safe", pure=True).load(texto)
    except DuplicateKeyError as e:
        raise ErroConfig(
            f"{nome} tem uma chave repetida ({e.problem_mark.line + 1 if e.problem_mark else '?'}ª linha): junte as "
            "duas seções numa só, senão a primeira é perdida."
        ) from e
    except YAMLError as e:
        raise ErroConfig(f"{nome} não é um YAML válido: {e}") from e


def _ler_yaml(arquivo: Path) -> dict:
    if not arquivo.exists():
        raise ErroConfig(f"Arquivo não encontrado: {arquivo}")
    dados = ler_yaml(arquivo.read_text(encoding="utf-8"), arquivo.name)
    if not isinstance(dados, dict):
        raise ErroConfig(f"{arquivo.name} deveria conter um mapeamento (chave: valor) no topo.")
    return dados


def carregar_config(arquivo: Path) -> ConfigProjeto:
    try:
        return ConfigProjeto.model_validate(_ler_yaml(arquivo))
    except ValidationError as e:
        raise ErroConfig(_explicar(e, arquivo)) from e


def carregar_codebook(arquivo: Path) -> Codebook:
    try:
        return Codebook.model_validate(_ler_yaml(arquivo))
    except ValidationError as e:
        raise ErroConfig(_explicar(e, arquivo)) from e
