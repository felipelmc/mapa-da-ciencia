<script lang="ts">
	/**
	 * O editor dos rótulos dos tópicos, no painel: cada macrotema com os tópicos dele, o rótulo e a descrição de cada
	 * um (o atual, escrito pelo modelo, pelas palavras-chave ou à mão), as palavras-chave e o tamanho do tópico. O que
	 * mudar vai para o `rotulos.yaml` (sem perder os comentários) e é aplicado pela etapa de tópicos, sem refazê-los
	 * nem chamar o modelo. "Voltar ao do modelo" tira a entrada do arquivo.
	 */
	import { onMount, tick } from 'svelte';
	import type { FonteApi, MudancaDeRotulos, RotuloManual, RotulosDoProjeto } from '$lib/dados/api';
	import { ErroDaApi } from '$lib/dados/pedir';
	import { formatarInteiro } from '$lib/formato';

	let {
		fonte,
		foco = null,
		aoFechar
	}: {
		fonte: FonteApi;
		/** Um tópico para abrir à vista (o link "Editar o rótulo" da gaveta do tópico). */
		foco?: number | null;
		aoFechar: (r: { salvou: boolean; avisos: string[] }) => void;
	} = $props();

	const MAXIMO = 80;
	const FONTE = { llm: 'do modelo', palavras: 'palavras-chave', manual: 'à mão' } as const;

	let dados = $state<RotulosDoProjeto | null>(null);
	let erro = $state<string | null>(null);
	let salvando = $state(false);
	/** O que está nos campos, por `t:<id>` ou `m:<id>`, e as entradas que voltam ao modelo. */
	let campos = $state<Record<string, RotuloManual>>({});
	let voltar = $state<Record<string, boolean>>({});

	const chave = (grupo: 't' | 'm', id: number) => `${grupo}:${id}`;

	onMount(async () => {
		try {
			dados = await fonte.rotulos();
		} catch (e) {
			erro = e instanceof ErroDaApi ? e.message : `Não foi possível ler os rótulos: ${(e as Error).message}`;
			return;
		}
		for (const t of dados.topicos) campos[chave('t', t.id)] = { rotulo: t.rotulo, descricao: t.descricao };
		for (const m of dados.macrotemas) campos[chave('m', m.id)] = { rotulo: m.rotulo, descricao: m.descricao };
		if (foco !== null) {
			await tick();
			const campo = document.getElementById(`rotulo-t-${foco}`) as HTMLInputElement | null;
			campo?.scrollIntoView({ block: 'center' });
			campo?.focus();
		}
	});

	const grupos = $derived(
		dados ? dados.macrotemas.map((m) => ({ m, topicos: dados!.topicos.filter((t) => t.macro === m.id) })) : []
	);
	/** Só o que mudou: um campo diferente do atual, ou uma entrada que volta ao modelo. */
	const mudanca = $derived.by(() => {
		const saida: Required<MudancaDeRotulos> = { topicos: {}, macrotemas: {} };
		if (!dados) return saida;
		const conferir = (grupo: 't' | 'm', x: { id: number; rotulo: string; descricao: string }) => {
			const k = chave(grupo, x.id);
			const destino = grupo === 't' ? saida.topicos : saida.macrotemas;
			if (voltar[k]) destino[x.id] = null;
			else if (campos[k] && (campos[k].rotulo.trim() !== x.rotulo || campos[k].descricao.trim() !== x.descricao))
				destino[x.id] = { rotulo: campos[k].rotulo.trim(), descricao: campos[k].descricao.trim() };
		};
		for (const t of dados.topicos) conferir('t', t);
		for (const m of dados.macrotemas) conferir('m', m);
		return saida;
	});
	const mudou = $derived(Object.keys(mudanca.topicos).length + Object.keys(mudanca.macrotemas).length);
	const vazio = $derived(Object.values(campos).some((c) => !c.rotulo.trim()));

	async function salvar() {
		salvando = true;
		erro = null;
		try {
			const r = await fonte.mudarRotulos(mudanca);
			aoFechar({ salvou: true, avisos: r.avisos ?? [] });
		} catch (e) {
			erro = e instanceof ErroDaApi ? e.message : `Não foi possível salvar: ${(e as Error).message}`;
		} finally {
			salvando = false;
		}
	}
</script>

<section class="editor" aria-labelledby="titulo-rotulos" data-testid="editor-rotulos">
	<header>
		<h2 id="titulo-rotulos">Rótulos dos tópicos</h2>
		<button type="button" class="fechar" onclick={() => aoFechar({ salvou: false, avisos: [] })}>Fechar sem salvar</button>
	</header>
	<p class="suave">
		O que você escrever vai para o <code>rotulos.yaml</code> do projeto e vale também quando os tópicos forem refeitos.
		Salvar aplica os rótulos sem refazer os tópicos e sem chamar o modelo. O rótulo de um macrotema com vários tópicos,
		quando escrito pelo modelo, só muda na próxima vez que a etapa Tópicos rodar inteira.
	</p>
	{#if erro}<p class="aviso" role="alert" data-testid="erro-rotulos">{erro}</p>{/if}
	{#if dados && dados.pendentes > 0 && !mudou}
		<p class="aviso" role="status">{formatarInteiro(dados.pendentes)} rótulo(s) do arquivo ainda não aplicado(s): salve para aplicar.</p>
	{/if}

	{#if !dados && !erro}
		<p class="suave" role="status">Carregando os rótulos…</p>
	{:else if dados}
		{#each grupos as { m, topicos } (m.id)}
			<fieldset class="macro" style:--cor={m.cor}>
				<legend><span class="cor" aria-hidden="true"></span> Macrotema {m.id}</legend>
				{@render campo('m', m, `${topicos.length} tópico(s)`)}
				<ol class="topicos">
					{#each topicos as t (t.id)}
						<li style:--cor={t.cor}>
							{@render campo('t', t, `${formatarInteiro(t.n_nucleo)} documentos · ${t.palavras.slice(0, 5).join(', ')}`)}
						</li>
					{/each}
				</ol>
			</fieldset>
		{/each}
		<footer>
			<button type="button" class="botao" disabled={!(mudou || dados.pendentes) || vazio || salvando} onclick={salvar} data-testid="salvar-rotulos">
				{mudou ? `Salvar e aplicar ${mudou === 1 ? '1 rótulo' : `${mudou} rótulos`}` : 'Aplicar'}
			</button>
			{#if vazio}<span class="suave">Um rótulo não pode ficar vazio.</span>{/if}
		</footer>
	{/if}
</section>

{#snippet campo(grupo: 't' | 'm', x: { id: number; rotulo: string; descricao: string; fonte: 'llm' | 'palavras' | 'manual'; manual: RotuloManual | null }, detalhe: string)}
	{@const k = chave(grupo, x.id)}
	{@const id = `rotulo-${grupo}-${x.id}`}
	<div class="campo" data-testid="campo-{k}">
		<label for={id}>
			<span class="cor" aria-hidden="true"></span>
			<span class="numero">{grupo === 't' ? 'Tópico' : 'Rótulo do macrotema'} {grupo === 't' ? x.id : ''}</span>
			<span class="selo" data-testid="fonte-{k}">{voltar[k] ? 'volta ao do modelo' : FONTE[x.fonte]}</span>
		</label>
		{#if campos[k]}
			<input {id} type="text" maxlength={MAXIMO} bind:value={campos[k].rotulo} disabled={voltar[k]} />
			<span class="contador suave">{campos[k].rotulo.length}/{MAXIMO}</span>
			<textarea aria-label="Descrição" rows="2" maxlength="1000" bind:value={campos[k].descricao} disabled={voltar[k]}></textarea>
		{/if}
		<p class="detalhe suave">{detalhe}</p>
		{#if x.manual}
			<label class="voltar"><input type="checkbox" bind:checked={voltar[k]} data-testid="voltar-{k}" /> Voltar ao do modelo</label>
		{/if}
	</div>
{/snippet}

<style>
	.editor {
		display: grid;
		gap: 1rem;
		padding: 1.2rem 1.4rem;
		border: 1px solid var(--linha);
		border-radius: var(--raio);
		background: var(--superficie);
	}

	header,
	footer {
		display: flex;
		flex-wrap: wrap;
		gap: 0.8rem;
		justify-content: space-between;
		align-items: baseline;
	}

	footer {
		justify-content: flex-start;
		align-items: center;
	}

	h2 {
		margin: 0;
		font-size: 1.3rem;
		font-weight: 450;
	}

	.fechar {
		padding: 0.3rem 0.7rem;
		border: 1px solid var(--linha);
		border-radius: var(--raio);
		background: none;
		color: var(--texto);
		font: inherit;
		cursor: pointer;
	}

	.macro {
		display: grid;
		gap: 0.8rem;
		margin: 0;
		padding: 0.8rem 1rem;
		border: 1px solid var(--linha);
		border-left: 4px solid var(--cor);
		border-radius: var(--raio);
	}

	legend {
		padding: 0 0.3rem;
		font-weight: 500;
	}

	.topicos {
		display: grid;
		gap: 0.8rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.campo {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 0.3rem 0.6rem;
		align-items: center;
	}

	.campo label:first-child,
	.campo textarea,
	.campo .detalhe,
	.campo .voltar {
		grid-column: 1 / -1;
	}

	.campo label:first-child {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		align-items: center;
		font-size: 0.85rem;
	}

	.cor {
		display: inline-block;
		width: 0.7rem;
		height: 0.7rem;
		border-radius: 50%;
		background: var(--cor);
	}

	.selo {
		padding: 0 0.4rem;
		border: 1px solid var(--linha);
		border-radius: 0.6rem;
		color: var(--texto-suave);
		font-size: 0.75rem;
	}

	input[type='text'],
	textarea {
		width: 100%;
		box-sizing: border-box;
		padding: 0.35rem 0.5rem;
		border: 1px solid var(--linha);
		border-radius: 0.4rem;
		background: var(--fundo);
		color: var(--texto);
		font: inherit;
	}

	textarea {
		font-size: 0.88rem;
		resize: vertical;
	}

	.contador {
		font-size: 0.75rem;
	}

	.detalhe {
		margin: 0;
		font-size: 0.8rem;
	}

	.voltar {
		display: inline-flex;
		gap: 0.4rem;
		align-items: center;
		font-size: 0.85rem;
	}

	.suave {
		color: var(--texto-suave);
	}

	.aviso {
		margin: 0;
		color: var(--acento);
	}
</style>
