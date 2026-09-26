<!-- Página gerada por scripts/gerar_referencias.py a partir do código. Não edite à mão. -->

# Codebook (codebook.yaml)

O codebook define as variáveis que o modelo preenche para cada resumo. Veja o guia [Escrever um codebook](../guias/codebook.md) para recomendações de redação.

## Codebook

Conteúdo do `codebook.yaml`.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `nome` | texto | **obrigatório** | Nome do codebook. |
| `versao` | texto | **obrigatório** | Versão; mude sempre que alterar definições. |
| `instrucoes` | texto | **obrigatório** | Instruções gerais ao modelo, lidas antes das variáveis. |
| `variaveis` | lista de [Variavel](#variavel) | **obrigatório** | Pelo menos uma variável. |

### Variavel

Uma pergunta que o modelo responde para cada resumo.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `id` | texto | **obrigatório** | Identificador em minúsculas, sem acento. |
| `rotulo` | texto | **obrigatório** | Nome curto exibido nas tabelas e gráficos. |
| `tipo` | `"categorica"` \\| `"multipla"` \\| `"booleana"` \\| `"texto"` | **obrigatório** | `categorica`: uma categoria; `multipla`: várias; `booleana`: sim/não; `texto`: resposta livre curta. |
| `pergunta` | texto | **obrigatório** | A pergunta, como o modelo vai lê-la. |
| `categorias` | lista de [Categoria](#categoria) | vazio | Obrigatórias (2 ou mais) em `categorica` e `multipla`. |

### Categoria

Uma das respostas possíveis de uma variável categórica.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `valor` | texto | **obrigatório** | Identificador em minúsculas, sem acento. |
| `rotulo` | texto ou vazio | vazio | Nome exibido; se vazio, usa o `valor`. |
| `definicao` | texto | **obrigatório** | Quando usar esta categoria. É o texto que o modelo lê. |
| `exemplos` | lista de texto | vazio | Trechos típicos (opcional). |
