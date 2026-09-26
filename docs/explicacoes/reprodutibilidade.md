# Reprodutibilidade

Um resultado do `mapa-da-ciencia` deve poder ser refeito, e explicado, por outra pessoa. Quatro mecanismos cuidam disso. O manifesto e os hashes já existem; os demais chegam com as etapas correspondentes (coleta no M2, tópicos no M3, classificação no M5).

## 1. Respostas brutas guardadas

Toda resposta das APIs (ArticleMeta, OpenAlex) é gravada comprimida em `brutos/`, antes de qualquer processamento. Rodar a coleta de novo não refaz requisições, e toda a normalização pode ser refeita a partir desses arquivos, mesmo que a API mude ou saia do ar.

## 2. Manifesto de cada execução

Cada vez que uma etapa roda, o `mapa` grava em `execucoes/` um arquivo como `20260926-120000-coleta.json`:

```json
{
  "etapa": "coleta",
  "versao_pacote": "0.1.0",
  "python": "3.12.14",
  "plataforma": "macOS-26.3-arm64-arm-64bit",
  "inicio": "2026-09-26T11:58:30+00:00",
  "fim": "2026-09-26T12:00:00+00:00",
  "duracao_s": 90.0,
  "hash_config": "3f1c9a0e7b2d4c11",
  "hash_codebook": null,
  "modelos": {},
  "parametros": {},
  "contagens": {"documentos": 403}
}
```

`mapa status` lê esses manifestos, e o site publicado os transforma numa página de metodologia.

## 3. Hashes de configuração e codebook

- O **hash da configuração** muda sempre que o `mapa.yaml` muda.
- O **hash do codebook** muda sempre que qualquer definição muda. Toda classificação fica associada a ele, e resultados de versões diferentes do codebook nunca se misturam.

## 4. Modelos, sementes e temperatura

- Os modelos são registrados com o **digest** do Ollama, e não só com o nome. A mesma etiqueta (`qwen3.5:9b`) pode apontar para arquivos diferentes com o tempo.
- UMAP, HDBSCAN e o sorteio da amostra de validação usam **sementes fixas**.
- A classificação usa **temperatura 0** e semente fixa. Mesmo assim, modelos de linguagem podem variar um pouco entre versões do Ollama ou entre máquinas. Por isso as respostas ficam em cache, e a validação mede a qualidade do que foi efetivamente usado.
- A **estabilidade dos tópicos** entre sementes diferentes é medida (índice de Rand ajustado) e publicada com os resultados.

## O que não é versionado

Os dados (`brutos/`, `dados/`, `saida/`) ficam fora do git, porque são grandes e recriáveis. O que vai para o git é a receita: `mapa.yaml`, `codebook.yaml` e os manifestos.
