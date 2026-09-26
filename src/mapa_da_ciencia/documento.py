"""O documento normalizado: a unidade do corpus depois da coleta.

Todas as fontes (ArticleMeta, OpenAlex, arquivos importados) viram `Documento`. É ele
que vai para `dados/documentos.parquet` e alimenta tópicos (M3), geografia (M4) e
classificação (M5). Nenhum campo guarda e-mail.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Casamento = Literal["1_doi", "2_pid_url", "3_doi_derivado", "4_titulo_ano", "sem_casamento", "nao_tentado"]
FonteLicenca = Literal["openalex", "revista", "ambas", "nenhuma"]
FonteAfiliacao = Literal["v240", "v70", "openalex", "nenhuma"]

# Da mais aberta para a mais restritiva. "desconhecida" é a pior: não dá para saber o que se pode fazer.
ORDEM_LICENCAS = [
    "cc0",
    "cc-by",
    "cc-by-sa",
    "cc-by-nd",
    "cc-by-nc",
    "cc-by-nc-sa",
    "cc-by-nc-nd",
    "other-oa",
    "desconhecida",
]
_SINONIMOS_LICENCA = {"public-domain": "cc0", "pd": "cc0", "by": "cc-by", "cc-by-4.0": "cc-by"}


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Texto(_Base):
    """Um texto num idioma (título, resumo ou palavra-chave)."""

    idioma: str | None = Field(description="Código ISO 639-1 (`pt`, `en`, `es`...) ou vazio se desconhecido.")
    texto: str
    origem: Literal["articlemeta", "openalex"] = "articlemeta"


class Afiliacao(_Base):
    """Uma afiliação como a fonte informa, já sem e-mails. A normalização geográfica é do M4."""

    id: str | None = Field(None, description="Rótulo interno da fonte (`aff1`), usado pelos autores.")
    instituicao: str | None = None
    divisoes: list[str] = Field(default_factory=list, description="Departamento, faculdade, programa.")
    cidade: str | None = None
    uf: str | None = Field(None, description="Estado como a fonte escreve (nome ou sigla).")
    pais: str | None = Field(None, description="País como a fonte escreve (ISO-2 na `v240`, nome na `v70`).")
    fonte: Literal["v240", "v70", "openalex"]


class Autor(_Base):
    """Um autor, na ordem da publicação."""

    nome: str | None = Field(description="Prenomes.")
    sobrenome: str | None
    orcid: str | None = None
    afiliacoes: list[str] = Field(default_factory=list, description="Ids das afiliações (`aff1`...).")


class InstituicaoOpenAlex(_Base):
    """Uma instituição que o OpenAlex associou a um autor (o id sem o prefixo `https://openalex.org/`)."""

    id: str = Field(description="Id do OpenAlex, como `I17974374`.")
    ror: str | None = Field(None, description="Id do ROR sem o prefixo, como `036rp1748`.")
    nome: str | None = None
    pais: str | None = Field(None, description="ISO 3166-1 alfa-2.")
    tipo: str | None = Field(None, description="`education`, `government`, `nonprofit`…")
    linhagem: list[str] = Field(default_factory=list, description="Instituições acima dela (sem ela própria).")


class AfiliacaoOpenAlex(_Base):
    """O texto de afiliação como o OpenAlex o recebeu, e as instituições que ele reconheceu nesse texto."""

    texto: str
    instituicoes: list[str] = Field(default_factory=list, description="Ids do OpenAlex.")


class AutoriaOpenAlex(_Base):
    """Um autor segundo o OpenAlex, na ordem da obra: base do casamento das afiliações na geografia (M4)."""

    nome: str | None = None
    instituicoes: list[InstituicaoOpenAlex] = Field(default_factory=list)
    paises: list[str] = Field(default_factory=list)
    afiliacoes: list[AfiliacaoOpenAlex] = Field(default_factory=list)


class Documento(_Base):
    """Um documento do corpus, normalizado a partir de uma ou mais fontes."""

    id: str = Field(description="PID do SciELO; `doi:…` ou `openalex:W…` para documentos de fora do SciELO.")
    pid: str | None = None
    colecao: str | None = Field(None, description="Coleção do SciELO (`scl` = Brasil).")
    doi: str | None = None
    openalex_id: str | None = None
    fonte: Literal["articlemeta", "openalex"] = Field(description="Fonte principal dos metadados.")
    origens: list[str] = Field(
        default_factory=list, description="Como o documento entrou: `scielo:ISSN`, `importar:arquivo`..."
    )
    tipo: str | None = Field(description="Tipo de documento (`research-article`, `review-article`...).")
    ano: int
    idioma_original: str | None = None
    revista_issn: str | None = None
    revista_acronimo: str | None = None
    revista_titulo: str | None = None
    titulos: list[Texto] = Field(default_factory=list)
    resumos: list[Texto] = Field(default_factory=list)
    palavras_chave: list[Texto] = Field(default_factory=list)
    autores: list[Autor] = Field(default_factory=list)
    afiliacoes: list[Afiliacao] = Field(default_factory=list)
    afiliacoes_fonte: FonteAfiliacao = "nenhuma"
    autorias_openalex: list[AutoriaOpenAlex] = Field(
        default_factory=list, description="Autores e instituições segundo o OpenAlex, para a geografia."
    )
    url: str | None = None
    citacoes: int | None = Field(None, description="Citações recebidas, segundo o OpenAlex.")
    n_referencias: int | None = Field(None, description="Referências citadas pelo documento.")
    licenca: str = Field("desconhecida", description="A mais restritiva entre OpenAlex e revista (ADR 0003).")
    licenca_fonte: FonteLicenca = "nenhuma"
    licenca_openalex: str | None = None
    licenca_revista: str | None = None
    casamento: Casamento = "nao_tentado"
    possivel_duplicata_de: str | None = Field(None, description="Id de outro documento suspeito de ser o mesmo.")

    @property
    def chave_revista(self) -> str:
        """Identificador da revista no contrato e nas contagens: o acrônimo, ou o ISSN, ou "?"."""
        return self.revista_acronimo or self.revista_issn or "?"

    def texto_em(self, campo: Literal["titulos", "resumos"], preferidos: list[str]) -> Texto | None:
        """O primeiro texto nos idiomas preferidos, ou qualquer um, ou `None`."""
        textos: list[Texto] = getattr(self, campo)
        for idioma in preferidos:
            for t in textos:
                if t.idioma == idioma:
                    return t
        return textos[0] if textos else None


def normalizar_licenca(licenca: str | None) -> str | None:
    """Uniformiza os nomes de licença das fontes: `BY-NC` (ArticleMeta) e `cc-by-nc` (OpenAlex) → `cc-by-nc`."""
    if not licenca:
        return None
    chave = licenca.strip().lower().replace("_", "-").replace(" ", "-")
    chave = _SINONIMOS_LICENCA.get(chave, chave)
    if not chave.startswith("cc") and chave.startswith("by"):
        chave = f"cc-{chave}"
    return chave if chave in ORDEM_LICENCAS else "other-oa"


def mais_restritiva(openalex: str | None, revista: str | None) -> tuple[str, FonteLicenca]:
    """A licença mais restritiva entre as duas fontes, e de onde ela veio (ADR 0003)."""
    a, b = normalizar_licenca(openalex), normalizar_licenca(revista)
    if a and b:
        if a == b:
            return a, "ambas"
        return (a, "openalex") if ORDEM_LICENCAS.index(a) > ORDEM_LICENCAS.index(b) else (b, "revista")
    if a:
        return a, "openalex"
    if b:
        return b, "revista"
    return "desconhecida", "nenhuma"


def pode_publicar_resumo(licenca: str) -> bool:
    """Resumos com licença Creative Commons (ou domínio público) podem ir, sem alteração, para um site sem fins
    comerciais (ADR 0003). Os demais ficam só no painel local."""
    return licenca.startswith("cc")
