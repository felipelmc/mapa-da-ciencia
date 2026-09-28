"""Limpeza e normalização de textos e identificadores vindos das fontes.

- Resumos da ArticleMeta trazem entidades HTML (às vezes duplamente escapadas, como
  `&amp;#8217;`), tags e prefixos como "Resumo:". A limpeza precisa ser estável, porque
  os offsets das evidências do M5 são calculados sobre o texto limpo.
- E-mails aparecem em vários campos das fontes e nunca podem chegar aos dados do projeto.
"""

from __future__ import annotations

import html
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

# E-mails, com as variações que aparecem em afiliações: espaço em volta do @ ou depois do ponto, e "[at]"/"(arroba)"
# e "[dot]"/"(ponto)" entre colchetes ou parênteses. O primeiro ramo é o padrão comum. Os outros exigem que o domínio
# termine, em minúsculas, num domínio de topo: sem isso, pegariam "p @ 0.05" e "o perfil @fulano. Em seguida", e
# apagariam junto a palavra anterior, que tomam pela parte local do endereço.
#
# A forma "palavra @perfil.x" (espaço antes do @ e nenhum depois) é também a de um perfil de rede social com ponto
# ("o perfil @maria.silva", "RT @fulano.oficial", "@frente.pe"). Nela, o domínio precisa passar por um dos domínios
# de topo de `_TLDS_PERFIL`: os genéricos e os de países frequentes em afiliações que não são siglas de UF nem de
# partido (fora pe, es, se, pa, ma, ms, mt, pt…). Nas outras formas com espaço ou disfarce, que um perfil não tem
# ("maria@ up.ac.pa", "[at] … [dot] io"), vale qualquer domínio de país (`_CCTLDS`) e os genéricos comuns.
#
# Todos os ramos só começam no início de uma sequência de [\w.+-] (o lookbehind): sem ele, cada posição de uma
# sequência longa sem espaço (um token de 20 mil caracteres num JSON) seria tentada até o fim dela, em tempo
# quadrático. O resultado de uma busca não muda, porque um endereço achado no meio da sequência também seria achado
# a partir do começo dela; na remoção, ver `remover_emails`.
_GENERICOS = (  # noqa: SIM905 (uma lista longa de códigos fica mais legível numa string)
    "com org net edu gov mil int info biz name pro cat eus gal museum coop aero asia app dev online site xyz tech"
).split()
# os domínios de país da IANA (os códigos ISO 3166 de duas letras, mais ac, eu, su e uk)
_CCTLDS = (  # noqa: SIM905 (uma lista longa de códigos fica mais legível numa string)
    "ac ad ae af ag ai al am ao aq ar as at au aw ax az ba bb bd be bf bg bh bi bj bm bn bo br bs bt bv bw by bz ca "
    "cc cd cf cg ch ci ck cl cm cn co cr cu cv cw cx cy cz de dj dk dm do dz ec ee eg er es et eu fi fj fk fm fo fr "
    "ga gb gd ge gf gg gh gi gl gm gn gp gq gr gs gt gu gw gy hk hm hn hr ht hu id ie il im in io iq ir is it je jm "
    "jo jp ke kg kh ki km kn kp kr kw ky kz la lb lc li lk lr ls lt lu lv ly ma mc md me mg mh mk ml mm mn mo mp mq "
    "mr ms mt mu mv mw mx my mz na nc ne nf ng ni nl no np nr nu nz om pa pe pf pg ph pk pl pm pn pr ps pt pw py qa "
    "re ro rs ru rw sa sb sc sd se sg sh si sj sk sl sm sn so sr ss st su sv sx sy sz tc td tf tg th tj tk tl tm tn "
    "to tr tt tv tw tz ua ug uk us uy uz va vc ve vg vi vn vu wf ws ye yt za zm zw"
).split()
_TLDS_PERFIL = (  # noqa: SIM905 (uma lista longa de códigos fica mais legível numa string)
    "com org net edu gov mil int info eu "
    "br ao mz cv st gw tl ar bo cl co cr cu ec gt mx py uy ve "
    "uk ie fr it de at ch be nl dk no fi pl ru us ca au nz jp cn kr in za il"
).split()


def _tld(nomes: list[str]) -> str:
    return rf"(?-i:(?:{'|'.join(sorted(set(nomes), key=lambda n: (-len(n), n)))}))(?!\w)"


_TLD = _tld(_CCTLDS + _GENERICOS)
_TLD_PERFIL = _tld(_TLDS_PERFIL)
_LOCAL = r"[\w.+-]*\w"
_ROTULO = r"[\w-]+"
_ARROBA = r"(?:@|＠|﹫)"
_AT_DISFARCADO = r"[\[({][ \t]*(?:at|arroba)[ \t]*[\])}]"
_DOT_DISFARCADO = r"[ \t]*[\[({][ \t]*(?:dot|ponto)[ \t]*[\])}][ \t]*"
_DOT = rf"(?:\.|{_DOT_DISFARCADO})"
_DOMINIO = rf"{_ROTULO}(?:{_DOT}{_ROTULO})*{_DOT}{_TLD}"
EMAIL = re.compile(
    r"(?<![\w.+-])(?:"
    r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"  # fulana@exemplo.br
    rf"|{_LOCAL}(?:"  # a parte local uma vez só, para as formas com espaço ou disfarce:
    # fulana @exemplo.br, a forma de um perfil: o domínio passa por um de `_TLDS_PERFIL` (até o fim dele)
    rf"[ \t]+{_ARROBA}{_ROTULO}(?:\.{_ROTULO})*\.{_TLD_PERFIL}(?:\.{_ROTULO})*(?![\w-])"
    rf"|[ \t]*{_ARROBA}[ \t]+{_DOMINIO}"  # fulana@ exemplo.br, fulana @ exemplo.br
    rf"|[ \t]*{_AT_DISFARCADO}[ \t]*{_DOMINIO}"  # fulana [at] exemplo [dot] br
    rf"|[ \t]*{_ARROBA}{_ROTULO}(?:{_DOT}{_ROTULO})*{_DOT_DISFARCADO}{_TLD}"  # fulana@exemplo (ponto) br
    # fulana@exemplo. br: o primeiro rótulo com duas letras ou mais (não "tod@s. no entanto" nem "P@10. de acordo")
    rf"|@(?=[\w-]*[^\W\d_])[\w-]{{2,}}(?:\. ?{_ROTULO})*\. ?{_TLD}"
    r"))",
    re.IGNORECASE,
)
_TAG = re.compile(r"<[^>]+>")
_ESPACOS = re.compile(r"\s+")
_PREFIXO_RESUMO = re.compile(r"^\s*(resumo|abstract|resumen|résumé)\s*[:.\-–—]?\s+", re.IGNORECASE)
_DOI = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)
_ORCID = re.compile(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", re.IGNORECASE)


def desescapar(texto: str) -> str:
    """Desfaz entidades HTML, inclusive as escapadas mais de uma vez (`&amp;#8217;` → `’`)."""
    for _ in range(3):
        novo = html.unescape(texto)
        if novo == texto:
            break
        texto = novo
    return texto


def limpar(texto: str | None, *, prefixo_resumo: bool = False) -> str:
    """Texto pronto para exibir e analisar: sem entidades, tags nem espaços sobrando, em NFC."""
    if not texto:
        return ""
    texto = desescapar(texto)
    texto = _TAG.sub(" ", texto)
    texto = unicodedata.normalize("NFC", texto)
    texto = _ESPACOS.sub(" ", texto).strip()
    if prefixo_resumo:
        texto = _PREFIXO_RESUMO.sub("", texto, count=1)
    return texto


def remover_emails(texto: str) -> str:
    """Tira endereços de e-mail de um texto (ex.: afiliações que trazem o e-mail no meio)."""
    # de novo até não sobrar nenhum: um endereço colado ao fim de outro ("fulana @ x.br.joao@y.br") começa no meio
    # de uma sequência, e o padrão só o acha depois que o primeiro sai
    while (novo := EMAIL.sub("", texto)) != texto:
        texto = novo
    return _ESPACOS.sub(" ", texto).strip(" ,;")


def contem_email(valor: Any) -> bool:
    """Procura e-mails em qualquer estrutura JSON (usado na varredura final e nos testes)."""
    if isinstance(valor, str):
        return bool(EMAIL.search(valor))
    if isinstance(valor, dict):
        return any(contem_email(v) for v in valor.values())
    if isinstance(valor, list | tuple):
        return any(contem_email(v) for v in valor)
    return False


def normalizar_doi(doi: str | None) -> str | None:
    """`https://doi.org/10.1590/ABC` → `10.1590/abc`. Devolve `None` se não parecer um DOI."""
    if not doi:
        return None
    achado = _DOI.search(doi.strip())
    if not achado:
        return None
    return achado.group(0).rstrip(".,;)]").lower()


def normalizar_orcid(orcid: str | None) -> str | None:
    if not orcid:
        return None
    achado = _ORCID.search(orcid)
    return achado.group(1).upper() if achado else None


def normalizar_titulo(titulo: str | None) -> str:
    """Forma canônica para comparar títulos: sem acentos, minúsculas, só letras e números."""
    base = unicodedata.normalize("NFKD", desescapar(titulo or "")).encode("ascii", "ignore").decode().lower()
    return _ESPACOS.sub(" ", re.sub(r"[^a-z0-9]+", " ", base)).strip()


def similaridade_titulo(a: str | None, b: str | None) -> float:
    """Similaridade entre 0 e 1 de dois títulos, depois de normalizados."""
    na, nb = normalizar_titulo(a), normalizar_titulo(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb, autojunk=False).ratio()
