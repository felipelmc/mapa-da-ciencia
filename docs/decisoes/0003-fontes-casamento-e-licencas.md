# 0003. Fontes do corpus, casamento ArticleMeta↔OpenAlex e licenças

- **Status:** aceita
- **Data:** 2026-09-26
- **Marco:** M0 (spikes M0c e M0e)

## Contexto

O corpus sai da **ArticleMeta** (SciELO): lista de PIDs por revista, resumos multilíngues, palavras-chave e afiliações. O **OpenAlex** complementa com citações, busca por termo e licença por artigo. Três perguntas precisavam de resposta:

1. Quanto do piloto (10 revistas de ciência política, 2010–2025) tem resumo, DOI e afiliação normalizada?
2. Como casar cada PID da ArticleMeta com um trabalho do OpenAlex, se a ArticleMeta não tem DOI em cerca de 27% dos registros?
3. De onde tirar a licença de cada artigo, para decidir o que pode ir para um site público?

## Evidência

Script `spikes/s01_fontes.py`, rodado nas 10 revistas em 2026-09-26 (4.947 registros da ArticleMeta, cerca de 30 min com 4 requisições simultâneas, e 5.038 trabalhos do OpenAlex).

**Cobertura**

| Revista | PIDs | c/ resumo | DOI (AM) | v240 | casados c/ OpenAlex |
|---|---|---|---|---|---|
| RBCP | 468 | 392 | 359 | 325 | 467 |
| Dados | 547 | 510 | 406 | 310 | 532 |
| Opinião Pública | 403 | 390 | 311 | 280 | 402 |
| Lua Nova | 484 | 416 | 339 | 299 | 483 |
| Rev. Sociologia e Política | 535 | 484 | 327 | 225 | 534 |
| BPSR | 360 | 265 | 330 | 257 | 360 |
| Contexto Internacional | 458 | 402 | 373 | 226 | 452 |
| RBPI | 438 | 399 | 311 | 205 | 424 |
| Novos Estudos CEBRAP | 504 | 391 | 334 | 285 | 466 |
| RBCS | 750 | 548 | 528 | 441 | 744 |
| **Total** | **4.947** | **4.197 (84,8%)** | **3.618 (73,1%)** | **2.853 (57,7%)** | **4.864 (98,3%)** |

- **Tipos:**
  - 4.267 `research-article` e 10 `review-article`;
  - o resto é resenha (322), editorial (128), `undefined` (62), errata (58) e outros.
- **Entre os 4.277 artigos:**
  - 4.166 têm resumo;
  - o **inglês cobre 4.159 (99,8%)** e o português 3.410 (81,9%);
  - 3.403 têm os dois idiomas.
- O ano embutido no PID (`pid[10:14]`) bateu com `publication_year` em **100%** dos registros.
- A **afiliação normalizada (`v240`) só existe em 57,7%** dos registros. A `v70` (não normalizada) aparece em 89%.

**Casamento com o OpenAlex, por passo da cascata**

| Passo | Casados |
|---|---|
| 1. DOI da ArticleMeta | 3.554 |
| 2. PID na `landing_page_url` do OpenAlex | 984 |
| 3. DOI derivado do PID (`10.1590/{PID}`) | 320 |
| 4. Título normalizado + ano | 6 |
| Sem casamento | 83 (Novos Estudos 38, Dados 15, RBPI 14) |

**Licenças**

| Fonte | O que diz |
|---|---|
| ArticleMeta, registro da revista (`v541`) | `BY` para as 10 revistas |
| OpenAlex, `primary_location.license` (casados) | `cc-by-nc` 2.428 · `cc-by` 2.174 · sem licença 252 · `other-oa` 7 · `cc-by-nc-nd` 3 |
| JATS da ArticleMeta (`format=xmlrsps`) | `by/4.0` em 7 de 9 artigos sorteados, inclusive num de **2010**, anterior ao lançamento do CC BY 4.0 (nov. 2013) |

Numa amostra de 9 artigos, em 2 de 3 casos em que o OpenAlex diz `cc-by-nc` o JATS diz `by/4.0`. O JATS antigo parece preenchido com a licença **atual** da revista, e não com a da publicação original. Portanto, nem a licença da revista nem o JATS servem como licença do artigo.

## Decisão

1. **Recorte por ano** pelo ano do PID. O filtro `from/until` da ArticleMeta usa a data de processamento e não serve para isso.
2. **Tipos de documento padrão** no recorte: `research-article` e `review-article`. Os demais podem ser incluídos pela configuração.
3. **Cascata de casamento** com o OpenAlex: DOI → PID na URL → DOI derivado → título+ano, com o passo usado gravado em cada documento. Os 1,7% sem casamento seguem no corpus, só sem os dados do OpenAlex.
4. **Afiliação:** `v240` quando existir, `v70` normalizada nos outros casos (43% dos registros) e o OpenAlex como complemento. A normalização da `v70` é essencial para a geografia (M4).
5. **Licença por artigo = a mais restritiva entre o OpenAlex e a licença da revista (`v541`)**, com a fonte registrada. Na falta das duas, o artigo fica como `desconhecida`.
6. **O que vai para um site publicado** (`mapa publicar`, que é sem fins comerciais):
   - resumos com qualquer licença CC (BY, BY-NC, BY-NC-ND) são exibidos **na íntegra, sem alteração**, com atribuição (autores, revista, DOI e licença);
   - resumos com licença `desconhecida` ou não CC ficam de fora (só título, metadados e link);
   - `--sem-resumos` omite todos.

   Isso é uma regra prática do projeto, **não um parecer jurídico**, e a documentação dirá isso.

## Consequências

- O modelo `Documento` ganha os campos `casamento` (passo da cascata), `licenca`, `licenca_fonte` e `afiliacoes_fonte`.
- Os 38 casos sem casamento da Novos Estudos devem ser investigados no M2. Podem ser seções sem DOI.
- **Idioma para os embeddings:** o inglês é o único idioma disponível em praticamente todo o corpus. A política final depende do spike M0a (ADR 0004).
- Coleta completa do piloto: cerca de 30 minutos na primeira vez e zero requisições nas seguintes (cache).

## Como reproduzir

    uv run spikes/s01_fontes.py               # 10 revistas, ~30 min na 1ª vez
    uv run spikes/s01_fontes.py --revistas op # só a Opinião Pública, ~3 min

## Adendo (2026-09-26, marco M2): a coleta de produção

O código de produção (`mapa coletar`, marco M2) refez o piloto com a cascata **conferida** e com as correções que a própria coleta revelou. O texto acima continua valendo como registro do spike. Os números abaixo substituem os de cima para quem for usar o corpus.

**O corpus.** Das 4.947 PIDs, ficam 4.275 documentos: os artigos de pesquisa e de revisão de 2010 a 2025 (670 de outros tipos ficam de fora), depois de fundir 2 artigos carregados duas vezes na ArticleMeta (*Dados* e *Lua Nova*, 2025).

| Revista | Documentos | Com resumo | Resumo só do OpenAlex | Resumo em inglês | DOI | `v240` | Casados c/ OpenAlex |
|---|---|---|---|---|---|---|---|
| RBCP | 404 | 398 | 9 | 389 | 400 | 282 | 399 |
| Dados | 506 | 506 | 3 | 503 | 503 | 300 | 503 |
| Opinião Pública | 396 | 395 | 7 | 388 | 396 | 280 | 396 |
| Lua Nova | 431 | 429 | 15 | 414 | 426 | 268 | 429 |
| Rev. Sociologia e Política | 487 | 486 | 2 | 484 | 487 | 220 | 487 |
| BPSR | 260 | 260 | 3 | 260 | 260 | 194 | 260 |
| Contexto Internacional | 403 | 403 | 2 | 401 | 403 | 195 | 403 |
| RBPI | 401 | 401 | 4 | 397 | 401 | 196 | 401 |
| Novos Estudos CEBRAP | 427 | 420 | 33 | 386 | 426 | 242 | 411 |
| RBCS | 560 | 559 | 15 | 539 | 560 | 346 | 560 |
| **Total** | **4.275** | **4.257 (99,6%)** | **93** | **4.161 (97,3%)** | **4.262 (99,7%)** | **2.523 (59,0%)** | **4.249 (99,4%)** |

"Com resumo" inclui os 93 resumos que só o OpenAlex tinha (a reserva da decisão 3). O DOI inclui os que vieram do OpenAlex.

**Cascata conferida.** DOI 3.105 · PID na URL 949 · DOI derivado 192 · título e ano 3 · sem casamento 26. A conferência (ano ±1, título parecido, cada trabalho usado uma vez) e três correções mudaram o resultado do spike:

- **DOIs trocados** (*Dados*, 2014): o spike casava os dois PIDs com o mesmo trabalho. Agora só o artigo certo casa, e o outro perde o DOI, que o OpenAlex confirmou ser do primeiro.
- **Location principal num repositório.** O OpenAlex às vezes registra o LA Referencia ou o DOAJ como fonte principal de um artigo de revista, e ele sumia da lista da revista. A lista passou a considerar qualquer location (`locations.source.issn`).
- **Trabalhos fora do índice de filtros e anos errados.** Quem sobra é procurado pelo DOI, numa lista e depois no endereço direto (grátis). Com ano divergente, vale título longo praticamente igual: o OpenAlex registra artigos da *Novos Estudos* de 2025 como de 2005.

A investigação pedida acima para a *Novos Estudos* (38 sem casamento no spike) termina aqui: sobram 16, dos quais 15 têm DOI do CEBRAP (`10.25091`) que o OpenAlex não conhece. Os 26 sem casamento seguem no corpus, só sem citações e sem a licença do OpenAlex.

**Licenças.** `cc-by` 2.142 · `cc-by-nc` 2.098 · `other-oa` 26 · `cc-by-sa` 6 · `cc-by-nc-nd` 3. A licença veio do OpenAlex (mais restritiva que a da revista) em 2.133 casos, as duas fontes concordaram em 1.934, e só a da revista existia em 208. A licença do OpenAlex passou a ser lida na location da própria revista, quando ela informa. Com a regra da decisão 6, **4.249 resumos (99,4%) podem ir para um site publicado**.

**Custo.** Com o cache da ArticleMeta aproveitado do spike, a primeira coleta levou 58 s e 32 créditos do OpenAlex (30 das listas por revista e 2 da busca por DOI). As seguintes fazem 0 requisições e levam cerca de 10 s. O pico de memória é de 0,36 GB: normalizar cada registro assim que chega evita guardar os brutos, que chegavam a 2,65 GB.

**Consequência para o M3.** 96 documentos (2,3%) não têm resumo em inglês, quase todos porque o resumo veio só do OpenAlex, no idioma original. A etapa de tópicos precisa decidir o que fazer com eles (título em inglês, tradução ou exclusão marcada), sem misturar idiomas em silêncio (ADR 0004).

**Correção no M3.** Dez desses resumos de reserva, todos iguais, não eram resumos: o OpenAlex guardava para dez artigos da *Novos Estudos CEBRAP* a apresentação da biblioteca virtual Americanae. A coleta passou a descartar resumos repetidos em documentos diferentes ([Fontes de dados](../explicacoes/fontes.md#openalex)); no piloto, ficam 4.247 artigos com resumo (99,3%) e 4.159 com resumo em inglês.

Reprodução: `mapa novo projetos/cp-scielo` e `mapa coletar -P projetos/cp-scielo`. A tabela sai de `mapa status` e de uma consulta com `mapa_da_ciencia.api.consultar`.
