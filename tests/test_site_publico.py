"""O site da documentação é para o público (quem usa o mapa e quem lê os resultados). As decisões técnicas (ADRs), as
notas de desenvolvimento e a API HTTP do painel ficam no repositório, fora do site, e nenhuma página publicada aponta
para elas com um link relativo: o `mkdocs build --strict` só registra esse link como INFO, e o site publicaria um
404. Uma página que se apoia num ADR usa o link absoluto do GitHub."""

import json
import re
from pathlib import Path

import yaml

RAIZ = Path(__file__).parents[1]
DOCS = RAIZ / "docs"
FORA_DO_SITE = ("decisoes", "desenvolvimento")
# as cópias do iCloud ("index 2.md") também ficam fora do site (exclude_docs)
COPIA_DO_ICLOUD = re.compile(r" \d+(\.\w+)?$")
# links em linha (com ou sem título), definições de link por referência e href em HTML
LINK = re.compile(r"\]\(\s*<?([^)\s>]+)|^\s*\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)|href=\"([^\"]+)\"", re.MULTILINE)
PARA_FORA = re.compile(r"(^|/)(decisoes|desenvolvimento)/|api-http")
BASTIDOR = {
    "spike": re.compile(r"\bspikes?\b", re.IGNORECASE),
    "marco M": re.compile(r"\bmarcos? M\d"),
    "Mac de desenvolvimento": re.compile(r"Mac de desenvolvimento"),
    "computador de desenvolvimento": re.compile(r"computador de desenvolvimento"),
    "desenvolvimento do projeto": re.compile(r"desenvolvimento do projeto"),
    "ADR": re.compile(r"\bADRs?\b"),
}


class _Carregador(yaml.SafeLoader):
    """Lê o mkdocs.yml ignorando as tags do Python (`!!python/name:…`), que só o MkDocs resolve."""


_Carregador.add_multi_constructor("tag:yaml.org,2002:python/", lambda _carregador, _sufixo, _no: None)


def _config() -> dict:
    return yaml.load((RAIZ / "mkdocs.yml").read_text(encoding="utf-8"), Loader=_Carregador)


def _publicadas():
    """As páginas e os modelos que vão para o site: docs/, sem as pastas excluídas, e a abertura em overrides/."""
    for arq in sorted([*DOCS.rglob("*.md"), *(RAIZ / "overrides").glob("*.html")]):
        rel = arq.relative_to(RAIZ)
        if (rel.parts[0] == "docs" and rel.parts[1] in FORA_DO_SITE) or COPIA_DO_ICLOUD.search(arq.name):
            continue
        yield rel, arq.read_text(encoding="utf-8")


def test_o_menu_nao_tem_as_secoes_internas_e_elas_ficam_fora_do_build():
    config = _config()
    menu = json.dumps(config["nav"], ensure_ascii=False)
    for termo in ("decisoes/", "desenvolvimento/", "api-http"):
        assert termo not in menu, termo
    for pasta in FORA_DO_SITE:
        assert f"/{pasta}/" in config["exclude_docs"], pasta
    assert "content.action.edit" not in config["theme"]["features"]


def test_nenhuma_pagina_publicada_aponta_para_o_que_ficou_fora_do_site():
    problemas = []
    for rel, texto in _publicadas():
        for achado in LINK.finditer(texto):
            alvo = achado.group(1) or achado.group(2) or achado.group(3)
            if alvo.startswith(("http://", "https://", "#", "mailto:")):
                continue
            if PARA_FORA.search(alvo):
                problemas.append(f"{rel}: {alvo}")
    assert problemas == []


def test_as_paginas_publicadas_nao_falam_do_processo_de_desenvolvimento():
    problemas = [
        f"{rel}: {nome}"
        for rel, texto in _publicadas()
        for nome, padrao in BASTIDOR.items()
        # um link para o GitHub pode ter "decisoes" no endereço, mas o texto não fala de ADRs nem de marcos
        if padrao.search(re.sub(r"\(https://github\.com/[^)]+\)", "", texto))
    ]
    assert problemas == []
