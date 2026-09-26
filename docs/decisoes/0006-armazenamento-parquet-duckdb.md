# 0006. Armazenamento do corpus em Parquet via DuckDB

- **Status:** aceita
- **Data:** 2026-09-26
- **Marco:** M2

## Contexto

Depois da coleta, o corpus (cerca de 5 mil documentos no piloto, com títulos, resumos, autores e afiliações aninhados) precisa ficar num formato que:

- o M3 consiga agregar (tópico × ano × revista) e o M4 consiga desaninhar (afiliações);
- pesquisadores leiam direto em notebooks (pandas, polars, R);
- seja rápido de refazer a partir de `brutos/`, sempre que a normalização mudar;
- não pese demais na instalação, que precisa funcionar em máquinas de alunos e no Colab.

## Opções consideradas

- **JSONL comprimido:** simples, mas lento para agregar e sem tipos. Toda consulta vira código Python.
- **SQLite:** bom para dados que mudam aos pouquinhos, mas ruim para listas aninhadas e para leitura em notebooks.
- **Parquet via pyarrow:** o padrão do ecossistema, mas a dependência pesa 36 a 50 MB e não traz SQL.
- **Parquet via DuckDB:** o mesmo Parquet, com SQL embutido para as agregações.

## Evidência

- **Tamanho da dependência** (wheels do PyPI, setembro de 2026): `duckdb` 1.5.5 ocupa 15,5 MB no macOS arm64 e 21,5 MB no Linux, sem dependências. `pyarrow` ocupa de 36 a 50 MB.
- **Esquema aninhado:** num teste com listas de structs (`STRUCT(idioma, texto, origem)[]`), a gravação a partir de JSONL com esquema explícito (`read_json(..., columns=...)`) e a leitura de volta funcionaram. As listas voltam como listas de dicionários em Python, e `unnest` desaninha em SQL.
- **Ida e volta sem perda:** os 30 registros das fixtures (Opinião Pública 2024 e casos especiais) viram `Documento`, vão para Parquet e voltam idênticos (`tests/test_armazenamento.py`).
- **Views úteis:** `documentos`, `textos` (títulos e resumos por idioma), `autores` (com a ordem) e `afiliacoes` cobrem o que M3 e M4 precisam sem código de desaninhamento em Python.

## Decisão

- `dados/documentos.parquet`, com um `Documento` por linha (compressão zstd, ordenado por id). É **sempre refeito a partir de `brutos/`**, nunca editado.
- A gravação passa por um JSONL temporário, depois `COPY … TO parquet` com esquema explícito (`armazenamento.ESQUEMA`, que um teste mantém igual aos campos de `Documento`), e termina com uma troca atômica do arquivo.
- As listas aninhadas usam `LIST(STRUCT)`, e não `MAP`, porque pandas e polars leem esse formato melhor.
- As consultas do projeto usam `armazenamento.conectar()`, que abre o DuckDB com as views.

## Consequências

- Nova dependência obrigatória: `duckdb`.
- Em notebooks, `pandas.read_parquet("dados/documentos.parquet")` funciona sem o `mapa`.
- Dados que mudam aos poucos (cache do LLM, codificação humana, jobs do painel) continuam previstos para o SQLite (`estado.sqlite`).

## Como reproduzir

    uv run pytest tests/test_armazenamento.py
