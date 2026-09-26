<script lang="ts">
	/**
	 * O codebook como formulário: o nome, a versão, as instruções e as variáveis, cada uma com o tipo, a pergunta e
	 * as categorias (valor, rótulo e definição). A validação de verdade é a do servidor (os mesmos modelos Pydantic
	 * do `codebook.yaml`); aqui só se evita o óbvio, como um `valor` com espaço.
	 */
	import type { CodebookEditavel } from '$lib/dados/api';

	let { codebook = $bindable() }: { codebook: CodebookEditavel } = $props();

	const TIPOS = [
		['categorica', 'uma categoria'],
		['multipla', 'várias categorias'],
		['booleana', 'sim ou não'],
		['texto', 'texto curto']
	] as const;
	const slug = (t: string) =>
		t
			.normalize('NFKD')
			.replace(/[̀-ͯ]/g, '')
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, '_')
			.replace(/^_|_$/g, '')
			.slice(0, 40);

	function novaVariavel() {
		const n = codebook.variaveis.length + 1;
		codebook.variaveis.push({
			id: `variavel_${n}`,
			rotulo: `Variável ${n}`,
			tipo: 'categorica',
			pergunta: '',
			categorias: [
				{ valor: 'sim', rotulo: 'Sim', definicao: '' },
				{ valor: 'nao_informado', rotulo: 'Não informado', definicao: 'O resumo não permite saber.' }
			]
		});
	}
</script>

<div class="editor" data-testid="editor-codebook">
	<div class="linha">
		<label>Nome <input bind:value={codebook.nome} /></label>
		<label class="curto">Versão <input bind:value={codebook.versao} /></label>
	</div>
	<label>Instruções ao modelo <textarea rows="4" bind:value={codebook.instrucoes}></textarea></label>

	{#each codebook.variaveis as v, i (i)}
		<details class="variavel" open={i === codebook.variaveis.length - 1 && !v.pergunta}>
			<summary>
				<strong>{v.rotulo || v.id}</strong>
				<span class="suave">{TIPOS.find(([t]) => t === v.tipo)?.[1]} · {v.categorias?.length ?? 0} categorias</span>
			</summary>
			<div class="linha">
				<label>Rótulo <input bind:value={v.rotulo} onchange={() => (v.id = v.id || slug(v.rotulo))} /></label>
				<label class="curto">Identificador <input bind:value={v.id} pattern="[a-z0-9_]+" /></label>
				<label class="curto">
					Tipo
					<select bind:value={v.tipo}>
						{#each TIPOS as [t, nome] (t)}<option value={t}>{nome}</option>{/each}
					</select>
				</label>
			</div>
			<label>Pergunta <input bind:value={v.pergunta} placeholder="Qual é a abordagem metodológica principal do estudo?" /></label>
			{#if v.tipo === 'categorica' || v.tipo === 'multipla'}
				<table class="categorias">
					<thead><tr><th>Valor</th><th>Rótulo</th><th>Definição</th><th></th></tr></thead>
					<tbody>
						{#each v.categorias ?? [] as c, j (j)}
							<tr>
								<td><input bind:value={c.valor} onblur={() => (c.valor = slug(c.valor))} aria-label="Valor" /></td>
								<td><input bind:value={c.rotulo} aria-label="Rótulo" /></td>
								<td><textarea rows="2" bind:value={c.definicao} aria-label="Definição"></textarea></td>
								<td><button type="button" class="tirar" aria-label="Tirar a categoria" onclick={() => v.categorias!.splice(j, 1)}>×</button></td>
							</tr>
						{/each}
					</tbody>
				</table>
				<button type="button" class="mais" onclick={() => (v.categorias ??= []).push({ valor: '', rotulo: '', definicao: '' })}>
					+ Categoria
				</button>
			{/if}
			<button type="button" class="remover" onclick={() => codebook.variaveis.splice(i, 1)}>Tirar a variável</button>
		</details>
	{/each}
	<button type="button" class="mais" onclick={novaVariavel} data-testid="nova-variavel">+ Variável</button>
</div>

<style>
	.editor {
		display: grid;
		gap: 0.8rem;
	}

	.linha {
		display: flex;
		flex-wrap: wrap;
		gap: 0.8rem;
	}

	label {
		display: grid;
		flex: 1;
		gap: 0.25rem;
		min-width: 12rem;
		font-size: 0.82rem;
		color: var(--texto-suave);
	}

	label.curto {
		flex: 0 1 12rem;
		min-width: 9rem;
	}

	input,
	textarea,
	select {
		width: 100%;
		padding: 0.35rem 0.5rem;
		border: 1px solid var(--linha-forte);
		border-radius: var(--raio-pequeno);
		background: var(--fundo);
		color: var(--texto);
		font: inherit;
		font-size: 0.88rem;
	}

	.variavel {
		display: grid;
		gap: 0.6rem;
		padding: 0.6rem 0.8rem;
		border: 1px solid var(--linha);
		border-radius: var(--raio);
	}

	.variavel[open] {
		display: grid;
	}

	summary {
		display: flex;
		gap: 0.6rem;
		align-items: baseline;
		cursor: pointer;
	}

	.suave {
		font-size: 0.8rem;
		color: var(--texto-fraco);
	}

	.categorias {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.82rem;
	}

	.categorias th {
		padding: 0.2rem;
		font-weight: 400;
		color: var(--texto-suave);
		text-align: left;
	}

	.categorias td {
		padding: 0.2rem;
		vertical-align: top;
	}

	.categorias td:nth-child(1),
	.categorias td:nth-child(2) {
		width: 22%;
	}

	button {
		justify-self: start;
		padding: 0.25rem 0.7rem;
		border: 1px solid var(--linha-forte);
		border-radius: var(--raio-pequeno);
		background: none;
		color: var(--texto);
		font: inherit;
		font-size: 0.82rem;
		cursor: pointer;
	}

	.tirar {
		padding: 0.1rem 0.45rem;
	}

	.remover {
		color: var(--texto-suave);
	}
</style>
