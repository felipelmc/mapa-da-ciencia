# Explorar o exemplo em 5 minutos

Neste tutorial você instala o `mapa-da-ciencia` e abre o painel com um **exemplo sintético**: 1.500 artigos fictícios de ciência política, em 28 tópicos, publicados entre 2010 e 2025. Não é preciso Ollama, modelos nem internet (além da instalação).

!!! note "Dados fictícios"
    Títulos, autores, resumos e afiliações do exemplo são **inventados**. Só os nomes das revistas e das instituições são reais, para o exemplo parecer familiar. Não use esses dados em análises.

## 1. Instale o `uv`

O [uv](https://docs.astral.sh/uv/) gerencia o Python e as dependências do projeto.

=== "macOS"

    ```bash
    brew install uv
    ```

=== "Linux e macOS sem Homebrew"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Windows"

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

## 2. Baixe o projeto

Enquanto não há versão publicada, a instalação é a partir do código:

```bash
git clone https://github.com/felipelmc/mapa-da-ciencia.git
cd mapa-da-ciencia
uv sync
```

Confira a instalação:

```bash
uv run mapa --versao
```

## 3. Abra o painel com o exemplo

```bash
uv run mapa painel --exemplo
```

O navegador abre em `http://127.0.0.1:8765/`. A página inicial mostra os números do corpus e os sete macrotemas, cada um com sua cor. Use o trilho à esquerda para passear pelas vistas. O **Mapa** mostra os 1.500 documentos fictícios como pontos: arraste para mover, use a roda do mouse para aproximar, clique num ponto para ver o documento, e experimente a busca (<kbd>/</kbd>), o laço (<kbd>L</kbd>) e o Play da linha do tempo ([Ler o mapa](../guias/ler-o-mapa.md)). Tópicos, Classificação, Geografia e Validação ganham conteúdo nos próximos marcos.

Para encerrar, volte ao terminal e aperte ++ctrl+c++.

!!! tip "A página diz que a interface não foi compilada?"
    Quem instala a partir do código precisa compilar a interface uma vez (é preciso ter o [Node.js](https://nodejs.org) 20 ou mais recente):

    ```bash
    cd frontend
    npm ci
    npm run build
    npm run empacotar
    cd ..
    ```

    Na versão publicada no PyPI (a partir do M7), a interface já vem compilada.

## O que aconteceu

`mapa painel --exemplo` gerou os dados de exemplo numa pasta temporária, subiu um servidor local só na sua máquina e abriu o navegador. Os dados seguem o mesmo [contrato](../referencia/contrato.md) que o pipeline produz para um projeto real. Por isso o exemplo é uma prévia fiel do que você vai ver com os seus próprios dados.

## Próximos passos

- [Seu primeiro mapa, parte 1](primeiro-mapa.md), para coletar artigos de verdade.
- [Instalar e escolher os modelos](../guias/instalacao.md), para preparar o Ollama.
- [Criar um projeto](../guias/criar-projeto.md), para definir o seu recorte.
