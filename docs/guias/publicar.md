# Publicar o site do projeto

`mapa publicar` gera um site estático com o painel do projeto: as mesmas vistas, lendo os mesmos dados, mas sem a API local. Ele funciona em qualquer servidor de arquivos, como o GitHub Pages, sem Python nem Ollama do outro lado.

## Gerar

```bash
uv run mapa publicar
```

O site fica em `saida/site/` (ou onde `--destino` indicar: uma pasta vazia, uma que ainda não existe ou um site publicado antes; a publicação troca todo o conteúdo do destino e, por isso, recusa uma pasta com outros arquivos ou a própria pasta do projeto). A saída diz quantos documentos entraram e quantos resumos foram publicados ou retirados. Antes de publicar, confira no navegador:

```bash
python -m http.server -d saida/site
```

e abra `http://localhost:8000`.

## O que muda em relação ao painel local

- **Só leitura.** Sem API, não há como rodar etapas, editar o projeto nem codificar a amostra. A vista Projeto vira a página **Metodologia**, com o que o manifesto registra: fontes, recorte, modelos (com a versão exata), sementes, durações e licenças.
- **Resumos só com licença aberta.** O resumo de um artigo só vai para o site se a licença for Creative Commons (a mais restritiva entre a do OpenAlex e a da revista, ADR 0003). Os outros aparecem com título, autores, revista, DOI e a licença, sem o resumo; os trechos que a classificação citou deles também saem, e os valores ficam. Com `--sem-resumos`, nenhum resumo vai.
- **Nada pessoal.** O site não tem e-mails nem ORCIDs (uma varredura final confere cada arquivo e interrompe a publicação se achar um) nem as codificações de pessoas da validação: só as métricas agregadas e, das divergências, as de codificadores de referência.

Veja [Privacidade e licenças](../explicacoes/privacidade-e-licencas.md).

## No GitHub Pages

O site é uma pasta com um `index.html` e os dados ao lado, e funciona na raiz de um domínio ou numa subpasta (`usuario.github.io/projeto/`). Uma forma simples:

1. Crie um repositório (pode ser o do seu projeto) e copie o conteúdo de `saida/site/` para uma pasta `docs/`.
2. Em **Settings › Pages**, escolha publicar a partir da pasta `docs/` do ramo principal.
3. Em alguns minutos, o site está em `https://<usuario>.github.io/<repositorio>/`.

Para republicar depois de uma etapa nova, rode `mapa publicar` de novo e troque o conteúdo da pasta: ele é sempre gerado inteiro.

!!! warning "Os dados brutos não vão"
    Publique só a pasta do site. `brutos/`, `dados/`, o `estado.sqlite` e o `.env` ficam na sua máquina: o `.gitignore` que o `mapa novo` cria já os deixa de fora do git.
