<script lang="ts" module>
	export interface ItemRanking {
		id: string;
		nome: string;
		sigla: string | null;
		lugar: string;
		peso: number;
		documentos: number;
	}
</script>

<script lang="ts">
	/**
	 * As instituições do recorte, da de maior peso fracionário à de menor, em barras. Cada linha é um botão que põe
	 * ou tira a instituição do recorte; "Mostrar mais" acrescenta outras 20.
	 */
	import { formatarDecimal, formatarInteiro } from '$lib/formato';

	let {
		itens,
		selecionados,
		aoEscolher,
		passo = 20
	}: { itens: ItemRanking[]; selecionados: Set<string>; aoEscolher: (id: string) => void; passo?: number } = $props();

	let mostrar = $state(20);
	const visiveis = $derived(itens.slice(0, Math.max(mostrar, passo)));
	const maior = $derived(Math.max(1e-9, ...itens.map((i) => i.peso)));
</script>

<div class="contem">
	<ol class="ranking" data-testid="ranking">
		{#each visiveis as item, k (item.id)}
			<li>
				<button
					type="button"
					class="linha"
					class:selecionada={selecionados.has(item.id)}
					aria-pressed={selecionados.has(item.id)}
					data-testid="instituicao"
					data-id={item.id}
					data-valor={item.peso.toFixed(4)}
					onclick={() => aoEscolher(item.id)}
				>
					<span class="posicao">{k + 1}</span>
					<span class="nome" title="{item.nome}{item.sigla ? ` (${item.sigla})` : ''}, {item.lugar}">
						{#if item.sigla}<strong>{item.sigla}</strong> <span class="extenso">{item.nome}</span>{:else}{item.nome}{/if}
					</span>
					<span class="lugar">{item.lugar}</span>
					<span class="barra" aria-hidden="true"><span style:width="{(100 * item.peso) / maior}%"></span></span>
					<span class="numero">{formatarDecimal(item.peso)}</span>
					<span class="numero documentos">{formatarInteiro(item.documentos)}</span>
				</button>
			</li>
		{/each}
	</ol>
	<div class="rodape">
		<span>Peso fracionário · documentos</span>
		{#if itens.length > visiveis.length}
			<button type="button" class="botao" data-testid="mostrar-mais" onclick={() => (mostrar = visiveis.length + passo)}>
				Mostrar mais ({formatarInteiro(itens.length - visiveis.length)} restantes)
			</button>
		{/if}
	</div>
</div>

<style>
	.contem {
		container-type: inline-size;
	}

	.ranking {
		display: grid;
		gap: 0.15rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.linha {
		display: grid;
		grid-template-columns: 1.6rem minmax(0, 1fr) 5.5rem minmax(3rem, 7rem) 3.4rem 2.8rem;
		align-items: center;
		gap: 0.6rem;
		width: 100%;
		padding: 0.22rem 0.4rem;
		border: 1px solid transparent;
		border-radius: var(--raio-pequeno);
		background: none;
		color: var(--texto);
		font: inherit;
		font-size: 0.86rem;
		text-align: left;
		cursor: pointer;
	}

	.linha:hover {
		background: var(--acento-suave);
	}

	.selecionada {
		border-color: var(--acento);
	}

	.posicao,
	.numero {
		font-family: var(--fonte-mono);
		font-size: 0.78rem;
		color: var(--texto-suave);
		text-align: right;
	}

	.nome {
		min-width: 0;
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
	}

	.nome strong {
		font-weight: 600;
	}

	.extenso,
	.lugar {
		color: var(--texto-suave);
	}

	.lugar {
		overflow: hidden;
		font-size: 0.75rem;
		white-space: nowrap;
		text-overflow: ellipsis;
	}

	.barra {
		height: 0.55rem;
		background: var(--linha);
		border-radius: 0.2rem;
		overflow: hidden;
	}

	.barra span {
		display: block;
		height: 100%;
		background: var(--seq-5);
	}

	.rodape {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.6rem;
		font-size: 0.78rem;
		color: var(--texto-suave);
	}

	/* estreito (a coluna ao lado do mapa das UFs numa tela de notebook): sem o lugar, que aparece na dica */
	@container (max-width: 34rem) {
		.linha {
			grid-template-columns: 1.4rem minmax(0, 1fr) minmax(2.5rem, 4.5rem) 3.2rem 2.6rem;
		}

		.lugar {
			display: none;
		}
	}

	@container (max-width: 22rem) {
		.linha {
			grid-template-columns: 1.4rem minmax(0, 1fr) 3.2rem;
		}

		.barra,
		.documentos {
			display: none;
		}
	}
</style>
