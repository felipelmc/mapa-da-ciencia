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

import yaml
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
    revistas: list[Issn] = Field(min_length=1, description="ISSNs das revistas, como aparecem no SciELO.")
    tipos: list[str] = Field(
        ["research-article", "review-article"],
        description="Tipos de documento incluídos (`document_type` da ArticleMeta).",
    )


class FonteOpenAlex(_Base):
    """Enriquecimento (citações, licença) e busca por termo no OpenAlex."""

    enriquecer: bool = Field(True, description="Casar cada artigo com o OpenAlex para obter citações e licença.")
    consulta: str | None = Field(None, description="Busca por termo nas revistas do recorte (opcional).")


class Fontes(_Base):
    scielo: FonteScielo | None = None
    openalex: FonteOpenAlex = FonteOpenAlex()
    importar: list[Path] = Field(
        default_factory=list,
        description="Arquivos CSV/RIS exportados do search.scielo.org ou listas de DOIs (.txt).",
    )

    @model_validator(mode="after")
    def _alguma_fonte(self) -> Fontes:
        if self.scielo is None and not self.importar and not self.openalex.consulta:
            raise ValueError("defina ao menos uma fonte: `scielo`, `importar` ou `openalex.consulta`")
        return self


class Recorte(_Base):
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
    provedor: Literal["ollama"] = "ollama"
    modelo: str = "qwen3-embedding:0.6b"


class ModeloLLM(_Base):
    provedor: Literal["ollama"] = "ollama"
    modelo: str = "qwen3.5:9b"
    num_ctx: int = Field(8192, ge=2048, description="Janela de contexto pedida ao Ollama.")
    temperatura: float = Field(0.0, ge=0, le=2)
    pensar: bool = Field(False, description="Liga o modo de raciocínio do modelo (mais lento).")
    concorrencia: int = Field(1, ge=1, le=16, description="Chamadas simultâneas ao Ollama.")
    semente: int = 7


class Modelos(_Base):
    embeddings: ModeloEmbeddings = ModeloEmbeddings()
    classificacao: ModeloLLM = ModeloLLM()
    rotulos: ModeloLLM = ModeloLLM()


class Validacao(_Base):
    n: int = Field(200, ge=10, description="Tamanho da amostra para codificação humana.")
    estratificar_por: Literal["topico", "ano", "revista"] = "topico"
    semente: int = 7
    codificadores: list[str] = Field(default_factory=list)


class ConfigProjeto(_Base):
    """Conteúdo do `mapa.yaml`."""

    versao_config: Literal[1] = 1
    nome: Slug
    titulo: str
    descricao: str = ""
    fontes: Fontes
    recorte: Recorte
    modelos: Modelos = Modelos()
    validacao: Validacao = Validacao()


# ---------------------------------------------------------------- codebook.yaml
class Categoria(_Base):
    valor: Slug
    rotulo: str | None = None
    definicao: str
    exemplos: list[str] = Field(default_factory=list)


class Variavel(_Base):
    id: Slug
    rotulo: str
    tipo: Literal["categorica", "multipla", "booleana", "texto"]
    pergunta: str
    categorias: list[Categoria] = Field(default_factory=list)

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

    nome: str
    versao: str
    instrucoes: str
    variaveis: list[Variavel] = Field(min_length=1)

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
        linhas.append(f"  - {campo}: {msg}")
    return "\n".join(linhas)


def _ler_yaml(arquivo: Path) -> dict:
    if not arquivo.exists():
        raise ErroConfig(f"Arquivo não encontrado: {arquivo}")
    try:
        dados = yaml.safe_load(arquivo.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ErroConfig(f"{arquivo.name} não é um YAML válido: {e}") from e
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
