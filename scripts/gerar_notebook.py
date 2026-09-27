"""Gera o caderno da oficina no Colab (`notebooks/oficina_colab.ipynb`).

O caderno é gerado, e não editado à mão, para a versão do pacote que ele instala ficar sempre igual à do
`pyproject.toml` (sem o sufixo `.dev`): ele baixa o *wheel* da *release* dessa versão. Os comandos dele rodam no CI
(`tests/test_notebook.py`), menos as células marcadas `colab`, que só funcionam lá.

Uso (da raiz do repo):
    uv run python scripts/gerar_notebook.py            # escreve o caderno
    uv run python scripts/gerar_notebook.py --checar   # só confere se está em dia
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path
from textwrap import dedent

RAIZ = Path(__file__).resolve().parents[1]
CADERNO = RAIZ / "notebooks" / "oficina_colab.ipynb"
DOCS = "https://felipelamarca.com/mapa-da-ciencia"


def versao() -> str:
    """A versão do pacote, sem o sufixo de desenvolvimento: a *release* que o caderno instala."""
    v = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    return re.sub(r"\.dev\d+$", "", v)


def _linhas(texto: str) -> list[str]:
    return dedent(texto).strip("\n").splitlines(keepends=True)


def md(texto: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": _linhas(texto)}


def codigo(texto: str, *tags: str) -> dict:
    return {
        "cell_type": "code",
        "metadata": {"tags": list(tags)} if tags else {},
        "execution_count": None,
        "outputs": [],
        "source": _linhas(texto),
    }


def celulas(versao: str) -> list[dict]:
    """As células, na ordem. As marcadas `colab` só rodam no Colab (GPU, Ollama, o *proxy* do painel)."""
    return [
        md(f"""
            # Oficina: seu mapa da ciência no Colab

            Neste caderno você monta, do zero, um mapa dos artigos da revista *Opinião Pública* de 2020 a 2024:

            1. coleta os títulos e resumos no SciELO e no OpenAlex;
            2. agrupa os artigos em tópicos, com um modelo de *embeddings*;
            3. descobre de onde vêm os autores;
            4. classifica uma amostra de resumos com um modelo de linguagem, que cita o trecho que justifica cada resposta;
            5. abre o painel, com o mapa, os tópicos no tempo, a geografia e a classificação.

            Tudo roda nesta máquina do Colab, com modelos abertos, sem chave de API e sem mandar os textos para ninguém. Leva uns 30 minutos, a maior parte com os modelos trabalhando sozinhos.

            **Antes de começar:** no menu, *Ambiente de execução › Alterar o tipo de ambiente de execução*, escolha **GPU T4**. Depois rode as células em ordem (Shift+Enter).

            O que cada etapa faz está na [documentação]({DOCS}/), e o roteiro da oficina, em [Oficina no Colab]({DOCS}/tutoriais/oficina-colab/).
        """),
        md("""
            ## 1. Instalar

            O `mapa-da-ciencia` e o [Ollama](https://ollama.com), que roda os modelos. Uns 2 minutos.
        """),
        codigo(
            f"""
            VERSAO = "{versao}"  # a versão do mapa-da-ciencia desta oficina

            !nvidia-smi -L || echo "Sem GPU: escolha a T4 em Ambiente de execução › Alterar o tipo de ambiente de execução."
            !pip install -q "https://github.com/felipelmc/mapa-da-ciencia/releases/download/v{{VERSAO}}/mapa_da_ciencia-{{VERSAO}}-py3-none-any.whl"
            !mapa --version
            """,
            "colab",
        ),
        codigo(
            """
            !curl -fsSL https://ollama.com/install.sh | sh

            import subprocess
            import time

            ollama = subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(5)
            """,
            "colab",
        ),
        md("""
            ## 2. Baixar os modelos

            Dois modelos abertos: um de *embeddings* (0,6 GB), que transforma cada resumo num vetor, e um de linguagem (6,6 GB), que escreve os rótulos dos tópicos e classifica os resumos. Uns 3 minutos.
        """),
        codigo(
            """
            !ollama pull qwen3-embedding:0.6b
            !ollama pull qwen3.5:9b
            """,
            "colab",
        ),
        md("""
            ## 3. Criar o projeto e coletar

            Um projeto é uma pasta com a configuração (`mapa.yaml`), o codebook (`codebook.yaml`) e os dados. O recorte: a *Opinião Pública*, de 2020 a 2024, com o perfil de modelos `padrao`, o que cabe na T4.
        """),
        codigo("""
            !mapa novo oficina --revista op --anos 2020-2024 --perfil padrao
            %cd oficina
            !mapa coletar
        """),
        md("""
            ## 4. Tópicos e geografia

            `mapa topicos` calcula os *embeddings*, agrupa os artigos e pede ao modelo um rótulo em português para cada tópico. `mapa geografia` liga as afiliações dos autores às instituições e conta a produção por UF e país.
        """),
        codigo("""
            !mapa topicos
            !mapa geografia
        """),
        md("""
            ## 5. Classificar uma amostra

            O `codebook.yaml` pergunta a abordagem, a técnica, o recorte geográfico, a subárea e o período de cada artigo. Sorteamos 30 artigos, e o modelo lê cada um e responde com a evidência de cada resposta. Uns 6 minutos. (No seu computador, `mapa classificar` sem opções classifica o corpus inteiro.)
        """),
        codigo("""
            !mapa validar amostra --n 30
            !mapa classificar --somente-amostra
            !mapa status
        """),
        md("""
            ## 6. Abrir o painel

            O painel abre numa janela nova, pelo *proxy* do Colab. Explore o **Mapa** (cada ponto é um artigo), os **Tópicos** no tempo, a **Geografia** e a **Classificação**. Em **Validação › Codificar a amostra**, você mesmo classifica os 30 artigos, às cegas, e vê quanto concorda com o modelo.

            A célula termina logo, e o painel continua no ar enquanto o caderno estiver aberto. Se a janela não abrir, libere as janelas *pop-up* do Colab e rode a célula de novo.
        """),
        codigo(
            """
            import mapa_da_ciencia.api as mapa

            mapa.painel(".")
            """,
            "colab",
        ),
        md(f"""
            ## Para ir além

            - Troque a revista ou o período em `!mapa novo` (`!mapa revistas "ciência política"` lista as revistas).
            - Edite o `codebook.yaml` (no painel de arquivos, à esquerda) com as suas perguntas e rode `!mapa classificar --somente-amostra` de novo.
            - Leve o projeto: `!zip -r oficina.zip . -x "brutos/*"` e baixe o zip pelo painel de arquivos. A máquina do Colab é apagada quando a sessão termina.
            - No seu computador, siga o tutorial [Seu primeiro mapa]({DOCS}/tutoriais/primeiro-mapa/).
        """),
    ]


def gerar() -> str:
    cadernos = celulas(versao())
    for i, c in enumerate(cadernos):
        c["id"] = f"celula-{i:02d}"
    nb = {
        "cells": cadernos,
        "metadata": {
            "accelerator": "GPU",
            "colab": {"gpuType": "T4", "provenance": []},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    return json.dumps(nb, ensure_ascii=False, indent=1) + "\n"


def main() -> None:
    texto = gerar()
    if "--checar" in sys.argv:
        if not CADERNO.exists() or CADERNO.read_text(encoding="utf-8") != texto:
            sys.exit("O caderno da oficina está desatualizado: rode `uv run python scripts/gerar_notebook.py`.")
        print("Caderno em dia.")
        return
    CADERNO.write_text(texto, encoding="utf-8")
    print(f"Caderno gerado em {CADERNO.relative_to(RAIZ)} (versão {versao()}).")


if __name__ == "__main__":
    main()
