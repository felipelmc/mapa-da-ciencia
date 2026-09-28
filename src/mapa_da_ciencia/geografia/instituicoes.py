"""As instituições que a geografia conhece: os registros do OpenAlex e as correções do projeto.

- `dados/instituicoes_openalex.parquet` (gravado pela coleta): nome, siglas, nomes alternativos, país, região,
  cidade, tipo e linhagem de cada instituição que aparece nas autorias do OpenAlex e acima delas.
- `geografia/dados/apelidos.csv` (do pacote): textos de afiliação que o casamento automático erra ou não acha,
  ligados a uma instituição do OpenAlex.
- `instituicoes.yaml` (do projeto, opcional) tem prioridade sobre os dois:

```yaml
apelidos:                      # texto de afiliação (como aparece) → instituição
  IUPERJ: I4210131232
  Centro Brasileiro de Análise e Planejamento: cebrap
instituicoes:
  cebrap:                      # instituição que o OpenAlex não tem
    nome: Centro Brasileiro de Análise e Planejamento
    sigla: CEBRAP
    pais: BR
    uf: SP
  I4210089234:                 # instituição do OpenAlex: corrige campos ou fica separada da "mãe"
    uf: RJ
    separada: true
```
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from importlib import resources
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from ..armazenamento import ARQUIVO_INSTITUICOES, ler_tabela
from ..config import ErroConfig, ler_yaml
from ..documento import Documento
from . import normalizar

ARQUIVO_PROJETO = "instituicoes.yaml"


@dataclass(frozen=True)
class Registro:
    """Uma instituição: do OpenAlex (`id` = `I…`) ou do projeto (`id` = o nome dado no `instituicoes.yaml`)."""

    id: str
    nome: str
    ror: str | None = None
    siglas: tuple[str, ...] = ()
    nomes: tuple[str, ...] = ()
    pais: str | None = None
    regiao: str | None = None
    cidade: str | None = None
    tipo: str | None = None
    linhagem: tuple[str, ...] = ()
    super_sistema: bool = False
    uf: str | None = None  # só quando o projeto informa; senão sai da região ou da cidade
    separada: bool = False  # não sobe para a instituição "mãe"

    @property
    def do_openalex(self) -> bool:
        return self.id.startswith("I") and self.id[1:].isdigit()


# países de língua portuguesa: o nome exibido é o português, quando o registro tem um
_LUSOFONOS = frozenset({"BR", "PT", "AO", "MZ", "CV", "GW", "ST", "TL"})
_PORTUGUES = re.compile(
    r"\b(Universidade|Instituto|Fundação|Centro|Escola|Faculdade|Pontifícia|Ministério|Secretaria|Conselho|"
    r"Empresa|Câmara|Senado|Tribunal|Banco|Associação|Sociedade|Hospital|Museu|Exército|Marinha)\b"
)
_SIGLA_NO_FIM = re.compile(r"\s*\(([^()]{2,15})\)\s*$")


def nome_de_exibicao(r: Registro) -> tuple[str, str | None]:
    """(nome, sigla) para mostrar: em português para instituições de países lusófonos (o OpenAlex às vezes dá o
    nome em inglês: "Institute of Applied Economic Research" para o Ipea) e sem a sigla entre parênteses no fim
    ("Universidade Estadual de Campinas (UNICAMP)" → "Universidade Estadual de Campinas", sigla "UNICAMP")."""
    from .casamento import palavras  # o casamento importa este módulo

    nome = r.nome
    if r.pais in _LUSOFONOS and not _PORTUGUES.search(nome):
        # entre os nomes em português, o que diz o mesmo que o nome em inglês (e não um nome antigo)
        original = palavras(nome)
        opcoes = [n for n in r.nomes if _PORTUGUES.search(n)]
        nome = max(opcoes, key=lambda n: len(palavras(n) & original) / len(palavras(n) | original), default=nome)
    sigla = r.siglas[0] if r.siglas else None
    if m := _SIGLA_NO_FIM.search(nome):
        nome, sigla = nome[: m.start()], sigla or m.group(1)
    return nome, sigla


def ler_openalex(dados: Path) -> dict[str, Registro]:
    """Os registros gravados pela coleta; vazio se a coleta não os buscou (corpus antigo ou sem OpenAlex)."""
    arquivo = dados / ARQUIVO_INSTITUICOES
    if not arquivo.exists():
        return {}
    return {
        r["id"]: Registro(
            id=r["id"],
            ror=r["ror"],
            nome=r["nome"] or r["id"],
            siglas=tuple(x.strip() for x in r["siglas"] or () if x.strip()),  # o OpenAlex tem "FGV "
            nomes=tuple(dict.fromkeys([*(r["nomes"] or ()), *([r["nome_pt"]] if r.get("nome_pt") else [])])),
            pais=r["pais"],
            regiao=r["regiao"],
            cidade=r["cidade"],
            tipo=r["tipo"],
            linhagem=tuple(r["linhagem"] or ()),
            super_sistema=bool(r["super_sistema"]),
        )
        for r in ler_tabela(arquivo)
    }


def completar(registros: dict[str, Registro], documentos: Iterable[Documento]) -> dict[str, Registro]:
    """Acrescenta as instituições das autorias que faltam nos registros (coleta sem `/institutions`), com o que a
    própria autoria diz: nome, país, tipo e linhagem, sem siglas nem nomes alternativos."""
    saida = dict(registros)
    for doc in documentos:
        for autoria in doc.autorias_openalex:
            for i in autoria.instituicoes:
                if i.id not in saida:
                    saida[i.id] = Registro(
                        id=i.id, nome=i.nome or i.id, ror=i.ror, pais=i.pais, tipo=i.tipo, linhagem=tuple(i.linhagem)
                    )
    return saida


def apelidos_do_pacote() -> dict[str, str]:
    """Apelido (texto de afiliação) → id do OpenAlex, do `apelidos.csv` do pacote."""
    texto = resources.files("mapa_da_ciencia.geografia").joinpath("dados", "apelidos.csv").read_text("utf-8")
    linhas = csv.DictReader(linha for linha in texto.splitlines() if not linha.startswith("#"))
    return {linha["apelido"]: linha["instituicao"] for linha in linhas}


# ---------------------------------------------------------------- instituicoes.yaml
class _Instituicao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome: str | None = None
    sigla: str | None = None
    pais: str | None = Field(None, description="ISO 3166-1 alfa-2 ou nome do país.")
    uf: str | None = Field(None, description="Sigla ou nome da UF.")
    cidade: str | None = None
    separada: bool = False

    @field_validator("pais")
    @classmethod
    def _pais(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if codigo := normalizar.pais(v):
            return codigo
        raise ValueError(f"país desconhecido: {v!r}")

    @field_validator("uf")
    @classmethod
    def _uf(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if sigla := normalizar.uf(v):
            return sigla
        raise ValueError(f"UF desconhecida: {v!r}")


_ID = re.compile(r"[A-Za-z0-9_.:-]{1,64}")  # o mesmo que o filtro `inst=` da interface aceita


class _Arquivo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    apelidos: dict[str, str] = Field(default_factory=dict)
    instituicoes: dict[str, _Instituicao] = Field(default_factory=dict)

    @field_validator("instituicoes")
    @classmethod
    def _ids(cls, v: dict[str, _Instituicao]) -> dict[str, _Instituicao]:
        ruins = [k for k in v if not _ID.fullmatch(str(k))]
        if ruins:
            raise ValueError(
                f"id de instituição inválido: {', '.join(map(repr, ruins))} (use só letras sem acento, números, "
                "`-`, `_`, `.` e `:`, até 64 caracteres, como `cem` ou `inct-ineu`)"
            )
        return v

    @field_validator("apelidos", "instituicoes", mode="before")
    @classmethod
    def _vazio(cls, v: object) -> object:
        return {} if v is None else v  # uma seção só com linhas comentadas (o bloco do `--revisar`)


@dataclass
class Correcoes:
    """O que o projeto corrige: apelidos (texto → id) e instituições próprias ou ajustadas."""

    apelidos: dict[str, str]
    instituicoes: dict[str, _Instituicao]


def ler_projeto(raiz: Path) -> Correcoes:
    arquivo = raiz / ARQUIVO_PROJETO
    if not arquivo.exists():
        return Correcoes({}, {})
    try:
        dados = _Arquivo.model_validate(ler_yaml(arquivo.read_text(encoding="utf-8"), arquivo.name) or {})
    except (yaml.YAMLError, ValidationError) as e:
        raise ErroConfig(
            f"{ARQUIVO_PROJETO} inválido: {e}. O formato é `apelidos: {{texto: id}}` e "
            "`instituicoes: {id: {nome: ..., pais: ..., uf: ...}}`."
        ) from e
    return Correcoes({str(k): str(v) for k, v in dados.apelidos.items()}, dados.instituicoes)


def combinar(openalex: dict[str, Registro], correcoes: Correcoes) -> tuple[dict[str, Registro], dict[str, str]]:
    """Registros e apelidos finais: os do OpenAlex e do pacote, com as correções do projeto por cima.

    Um apelido que aponta para uma instituição desconhecida é um erro (quase sempre um id digitado errado).
    """
    registros = dict(openalex)
    for id_, info in correcoes.instituicoes.items():
        if id_ in registros:
            campos = {k: v for k, v in info.model_dump(exclude_unset=True).items() if k != "sigla"}
            if info.sigla:
                campos["siglas"] = (info.sigla, *registros[id_].siglas)
            registros[id_] = replace(registros[id_], **campos)
        elif info.nome and info.pais:
            registros[id_] = Registro(
                id=id_,
                nome=info.nome,
                siglas=(info.sigla,) if info.sigla else (),
                pais=info.pais,
                uf=info.uf,
                cidade=info.cidade,
                separada=True,
            )
        else:
            raise ErroConfig(
                f"{ARQUIVO_PROJETO}: a instituição {id_!r} não está nos registros do OpenAlex; "
                "para criar uma instituição própria, informe ao menos `nome` e `pais`."
            )
    apelidos = {k: v for k, v in apelidos_do_pacote().items() if v in registros}
    for texto, id_ in correcoes.apelidos.items():
        if id_ not in registros:
            raise ErroConfig(
                f"{ARQUIVO_PROJETO}: o apelido {texto!r} aponta para {id_!r}, que não é uma instituição conhecida. "
                "Use um id do OpenAlex (I…) que apareça no corpus ou declare a instituição em `instituicoes:`."
            )
        apelidos[texto] = id_
    return registros, apelidos
