import pytest

from mapa_da_ciencia.documento import (
    Documento,
    Texto,
    mais_restritiva,
    normalizar_licenca,
    pode_publicar_resumo,
)
from mapa_da_ciencia.texto import (
    contem_email,
    limpar,
    normalizar_doi,
    normalizar_orcid,
    normalizar_titulo,
    remover_emails,
    similaridade_titulo,
)


def test_limpar_desfaz_entidades_duplamente_escapadas_e_tags():
    bruto = "Resumo: O Brasil&amp;#8217;s   <i>welfare</i>\n state &amp;amp; a crise"
    assert limpar(bruto, prefixo_resumo=True) == "O Brasil’s welfare state & a crise"
    assert limpar(None) == ""


def test_prefixo_so_sai_quando_pedido_e_quando_e_prefixo():
    assert limpar("Abstract: The study", prefixo_resumo=True) == "The study"
    assert limpar("Resumo dos debates sobre", prefixo_resumo=True) == "dos debates sobre"
    assert limpar("Abstracts matter", prefixo_resumo=True) == "Abstracts matter"
    assert limpar("Resumo: texto") == "Resumo: texto"


def test_emails():
    assert remover_emails("Universidade X, joao.silva@ufmg.br; Belo Horizonte") == "Universidade X, ; Belo Horizonte"
    assert contem_email({"a": [{"b": "contato: x@y.org"}]})
    assert not contem_email({"a": ["sem arroba", 3, None]})


@pytest.mark.parametrize(
    ("entrada", "saida"),
    [
        ("https://doi.org/10.1590/1807-019120243011", "10.1590/1807-019120243011"),
        ("DOI: 10.1590/S0011-52582014000200007.", "10.1590/s0011-52582014000200007"),
        ("doi:10.1590/ABC)", "10.1590/abc"),
        ("sem doi", None),
        (None, None),
    ],
)
def test_normalizar_doi(entrada, saida):
    assert normalizar_doi(entrada) == saida


def test_orcid_e_titulo():
    assert normalizar_orcid("https://orcid.org/0000-0002-1825-009x") == "0000-0002-1825-009X"
    assert normalizar_orcid("0000") is None
    assert normalizar_titulo("Políticas Públicas: &amp; Saúde!") == "politicas publicas saude"
    assert similaridade_titulo("Coalizões no Congresso", "Coalizoes no congresso") == 1.0
    assert similaridade_titulo("Coalizões no Congresso", "A política externa chinesa") < 0.5
    assert similaridade_titulo("", "x") == 0.0


def test_licencas():
    assert normalizar_licenca("BY-NC") == "cc-by-nc"
    assert normalizar_licenca("cc-by") == "cc-by"
    assert normalizar_licenca("public-domain") == "cc0"
    assert normalizar_licenca("other-oa") == "other-oa"
    assert normalizar_licenca("licença esquisita") == "other-oa"
    assert normalizar_licenca(None) is None
    # a mais restritiva vence, e a fonte fica registrada (ADR 0003)
    assert mais_restritiva("cc-by-nc", "BY") == ("cc-by-nc", "openalex")
    assert mais_restritiva("cc-by", "BY-NC-ND") == ("cc-by-nc-nd", "revista")
    assert mais_restritiva("cc-by", "BY") == ("cc-by", "ambas")
    assert mais_restritiva(None, "BY") == ("cc-by", "revista")
    assert mais_restritiva(None, None) == ("desconhecida", "nenhuma")
    assert pode_publicar_resumo("cc-by-nc-nd")
    assert not pode_publicar_resumo("other-oa")
    assert not pode_publicar_resumo("desconhecida")


def test_documento_texto_em_idioma_preferido():
    d = Documento(
        id="S0104-62762024000100200",
        fonte="articlemeta",
        tipo="research-article",
        ano=2024,
        titulos=[Texto(idioma="en", texto="Title"), Texto(idioma="pt", texto="Título")],
    )
    assert d.texto_em("titulos", ["pt", "en"]).texto == "Título"
    assert d.texto_em("titulos", ["es"]).texto == "Title"
    assert d.texto_em("resumos", ["pt"]) is None
    with pytest.raises(ValueError):
        Documento(id="x", fonte="articlemeta", tipo=None, ano=2024, email="a@b.c")


@pytest.mark.parametrize(
    "texto",
    [
        "Univ. X, fulana @ exemplo.br",
        "Univ. X, fulana @exemplo.br",
        "Univ. X, fulana@exemplo. br",
        "Univ. X, fulana@ exemplo.com.br",
        "Univ. X, fulana.silva@ exemplo.es",
        "Univ. X, fulana99 @exemplo.com",
        "Univ. X, fulana@ exemplo.ca",
        "Univ. X, f.b.silva@exemplo. com",
        "beltrano [at] exemplo [dot] br",
        "ciclano {at} exemplo.br",
        "joao (arroba) exemplo (ponto) br",
        "maria@exemplo.com.br",
        # domínios de país fora da lista dos perfis, nas formas que um perfil de rede social não tem
        "Universidad de Panamá. maria@ exemplo.ac.pa",
        "Universidade de São Tomé e Príncipe. rosa@ exemplo.st",
        "UAB, Barcelona. fulana@ exemplo.cat",
        "Empresa X. fulana [at] exemplo [dot] io",
        "Univ. X. fulana (arroba) exemplo (ponto) ac (ponto) id",
        "Univ. X. fulana@exemplo (ponto) es",
        "UNAH, Honduras. juan.perez @exemplo.edu.hn",
    ],
)
def test_emails_com_espacos_e_disfarces(texto):
    """As variações de e-mail que aparecem em afiliações reais (espaço em volta do @ ou depois do ponto, [at])."""
    assert contem_email(texto)
    assert not contem_email(remover_emails(texto)) and "exemplo" not in remover_emails(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "p @ 0.05 no teste",
        "O perfil @fulano. Em seguida",
        "looking at data. Results",
        "RT @usuario: texto",
        # arrobas de rede social com ponto (Instagram, TikTok): nem o perfil nem a palavra anterior somem
        "Analisamos o perfil @maria.silva no Instagram",
        "a conta @camara.deputados publicou 300 posts",
        "RT @jair.bolsonaro: texto do tweet",
        "tweets de @lula.oficial e @bolsonaro.sp",
        "look [at] data.table and dplyr",
        "Recall@10. results show",
        "entre tod@s. em seguida",
        # perfis que terminam numa sigla de UF, ou de partido, que também é domínio de país
        "Analisamos o perfil @frente.pe no Instagram",
        "as contas @governo.es e @camara.ms",
        "o coletivo @mst.se publicou",
        "o perfil @lula.pt comenta",
        "a página @jornal.do.commercio",
        "para tod@s. no entanto",
        "precisão P@10. de acordo com a literatura",
    ],
)
def test_arroba_que_nao_e_email(texto):
    assert not contem_email(texto) and remover_emails(texto) == texto


def test_email_colado_a_outro_tambem_sai():
    """O segundo endereço começa no meio de uma sequência sem espaço: sai numa segunda passada."""
    for texto in ("Univ. X, fulana @ exemplo.br.joao@exemplo.org", "fulana@ exemplo.br-joao@exemplo.org; Rio"):
        limpo = remover_emails(texto)
        assert not contem_email(limpo) and "joao" not in limpo and "exemplo" not in limpo, limpo


def test_detector_de_email_e_linear_em_sequencias_longas_sem_espaco():
    """Um token enorme sem espaço (num JSON do `publicar`, num resumo mal formatado) não pode travar a varredura:
    sem a âncora no começo da sequência, 20 mil caracteres levavam ~6 s, e o dobro, quatro vezes isso."""
    import time

    for texto in ("a" * 20_000, "a.b-" * 5_000, "x" * 20_000 + " fulana@exemplo.br"):
        inicio = time.perf_counter()
        achado = contem_email(texto)
        assert time.perf_counter() - inicio < 0.5, texto[:10]
        assert achado == texto.endswith(".br")
