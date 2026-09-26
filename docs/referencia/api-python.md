# API Python

O `mapa-da-ciencia` também pode ser usado de dentro de um notebook ou script. A API ainda é pequena: cresce a cada marco junto com as etapas do pipeline, e uma fachada `mapa_da_ciencia.api` para notebooks chega no M2.

```python
from mapa_da_ciencia.projeto import Projeto
from mapa_da_ciencia.llm.perfis import sugerir_perfil

projeto = Projeto.criar("cp-scielo", modelo="ciencia-politica", perfil=sugerir_perfil())
print(projeto.config.recorte.anos)  # (2010, 2025)
print(len(projeto.codebook.variaveis))  # 6
```

## Projeto

::: mapa_da_ciencia.projeto.Projeto
    options:
      members: [abrir, criar, config, codebook]

## Configuração

::: mapa_da_ciencia.config.carregar_config

::: mapa_da_ciencia.config.carregar_codebook

::: mapa_da_ciencia.config.ErroConfig

## Manifesto de execução

::: mapa_da_ciencia.manifesto.registrar_execucao

::: mapa_da_ciencia.manifesto.ultima_execucao

## Recursos da máquina

::: mapa_da_ciencia.recursos.cabe_na_memoria

::: mapa_da_ciencia.llm.perfis.sugerir_perfil

## Diagnóstico

::: mapa_da_ciencia.diagnostico.diagnosticar

## Contrato de dados

::: mapa_da_ciencia.contrato.modelos.fragmento_de

::: mapa_da_ciencia.contrato.exemplo.gerar_exemplo
