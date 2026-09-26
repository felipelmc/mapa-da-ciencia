"""Projeto = uma pasta com `mapa.yaml`, `codebook.yaml` e os dados de cada etapa.

Layout:

    meu-projeto/
      mapa.yaml  codebook.yaml  .env  .gitignore  LEIAME.md
      brutos/        respostas brutas das APIs (cache; fonte da verdade da coleta)
      dados/         tabelas analíticas (Parquet) e embeddings
      execucoes/     um manifesto JSON por execução de etapa
      saida/         arquivos do contrato de dados e site publicado
      estado.sqlite  cache do LLM, codificação humana e jobs do painel
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from string import Template

from mapa_da_ciencia.config import Codebook, ConfigProjeto, ErroConfig, carregar_codebook, carregar_config
from mapa_da_ciencia.llm.perfis import Perfil

ARQUIVO_CONFIG = "mapa.yaml"
ARQUIVO_CODEBOOK = "codebook.yaml"
MODELOS_DE_PROJETO = ("ciencia-politica", "vazio")

# Etapas do pipeline, na ordem em que rodam.
ETAPAS = ("coleta", "embeddings", "topicos", "classificacao", "geografia", "validacao", "exportacao")

_GITIGNORE = """\
# Gerado pelo `mapa novo`. Dados e segredos ficam fora do git.
.env
brutos/
dados/
saida/
estado.sqlite*
"""

_ENV_EXEMPLO = """\
# Copie este arquivo para `.env` e preencha. O `.env` nunca vai para o git.

# E-mail enviado no User-Agent das requisições (boa prática com APIs públicas).
MAPA_EMAIL=

# Chave gratuita do OpenAlex (opcional; aumenta o limite diário). https://openalex.org
OPENALEX_API_KEY=
"""


class ProjetoNaoEncontrado(ErroConfig):
    """Não há `mapa.yaml` na pasta indicada nem nas pastas acima dela."""


@dataclass
class Projeto:
    raiz: Path
    _config: ConfigProjeto | None = field(default=None, repr=False)
    _codebook: Codebook | None = field(default=None, repr=False)

    # ------------------------------------------------------------ localizar e criar
    @classmethod
    def abrir(cls, caminho: Path | str = ".") -> Projeto:
        """Abre o projeto na pasta indicada ou na primeira pasta acima que tenha `mapa.yaml`."""
        inicio = Path(caminho).resolve()
        for pasta in (inicio, *inicio.parents):
            if (pasta / ARQUIVO_CONFIG).exists():
                return cls(pasta)
        raise ProjetoNaoEncontrado(
            f"Nenhum projeto encontrado em {inicio}. Entre na pasta de um projeto ou crie um com `mapa novo <pasta>`."
        )

    @classmethod
    def criar(cls, pasta: Path | str, *, modelo: str, perfil: Perfil, nome: str | None = None) -> Projeto:
        """Cria a pasta do projeto a partir de um modelo, com os modelos de LLM do perfil."""
        if modelo not in MODELOS_DE_PROJETO:
            raise ErroConfig(f"Modelo de projeto desconhecido: {modelo}. Opções: {', '.join(MODELOS_DE_PROJETO)}")
        raiz = Path(pasta).resolve()
        if (raiz / ARQUIVO_CONFIG).exists():
            raise ErroConfig(f"Já existe um projeto em {raiz}.")
        raiz.mkdir(parents=True, exist_ok=True)

        nome = nome or _slug(raiz.name)
        textos = resources.files("mapa_da_ciencia.modelos_projeto")
        config = Template(textos.joinpath(f"{modelo}.yaml").read_text(encoding="utf-8")).substitute(
            nome=nome,
            perfil=perfil.nome,
            modelo_embeddings=perfil.embeddings,
            modelo_classificacao=perfil.classificacao,
            modelo_rotulos=perfil.rotulos,
        )
        (raiz / ARQUIVO_CONFIG).write_text(config, encoding="utf-8")
        codebook = "codebook-exemplo.yaml" if modelo == "ciencia-politica" else "codebook-vazio.yaml"
        (raiz / ARQUIVO_CODEBOOK).write_text(textos.joinpath(codebook).read_text(encoding="utf-8"), encoding="utf-8")
        (raiz / ".gitignore").write_text(_GITIGNORE, encoding="utf-8")
        (raiz / ".env.exemplo").write_text(_ENV_EXEMPLO, encoding="utf-8")
        for sub in ("brutos", "dados", "execucoes", "saida"):
            (raiz / sub).mkdir(exist_ok=True)

        projeto = cls(raiz)
        projeto.config  # valida o que acabou de ser escrito  # noqa: B018
        return projeto

    # ------------------------------------------------------------ conteúdo
    @property
    def config(self) -> ConfigProjeto:
        if self._config is None:
            self._config = carregar_config(self.raiz / ARQUIVO_CONFIG)
        return self._config

    @property
    def codebook(self) -> Codebook:
        if self._codebook is None:
            self._codebook = carregar_codebook(self.raiz / ARQUIVO_CODEBOOK)
        return self._codebook

    # ------------------------------------------------------------ caminhos
    @property
    def brutos(self) -> Path:
        return self.raiz / "brutos"

    @property
    def dados(self) -> Path:
        return self.raiz / "dados"

    @property
    def execucoes(self) -> Path:
        return self.raiz / "execucoes"

    @property
    def saida(self) -> Path:
        return self.raiz / "saida"

    @property
    def estado(self) -> Path:
        return self.raiz / "estado.sqlite"

    def remover_dados(self) -> None:
        """Apaga dados derivados (não a configuração). Usado em testes e em `--refazer`."""
        for sub in (self.dados, self.saida):
            shutil.rmtree(sub, ignore_errors=True)
            sub.mkdir()


def _slug(texto: str) -> str:
    import re
    import unicodedata

    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "_", base).strip("_")
    return base if base and base[0].isalpha() else f"projeto_{base}".rstrip("_")
