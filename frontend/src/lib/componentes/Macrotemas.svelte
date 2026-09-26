<script lang="ts">
	import type { Topicos } from '$lib/contrato/tipos';
	import { contar, formatarPorcentagem } from '$lib/formato';

	/** Legenda dos macrotemas: cor, número de tópicos e peso no corpus. */
	let { topicos, totalDocumentos }: { topicos: Topicos; totalDocumentos: number } = $props();

	const linhas = $derived.by(() => {
		const docs = new Map<number, number>();
		for (const t of topicos.topicos) docs.set(t.macro_id, (docs.get(t.macro_id) ?? 0) + t.n);
		const maior = Math.max(...docs.values(), 1);
		return topicos.macrotemas.map((m) => {
			const n = docs.get(m.id) ?? 0;
			return {
				...m,
				n,
				fracao: totalDocumentos > 0 ? n / totalDocumentos : 0,
				largura: (n / maior) * 100
			};
		});
	});
</script>

<section class="macrotemas" aria-labelledby="titulo-macrotemas">
	<header>
		<h2 id="titulo-macrotemas">
			{contar(topicos.macrotemas.length, 'macrotema')}
		</h2>
		<p>
			Os {topicos.topicos.length} tópicos agrupados por afinidade. A cor de cada macrotema é a mesma no mapa
			e nos gráficos.
		</p>
	</header>

	<ol data-testid="lista-macrotemas">
		{#each linhas as m (m.id)}
			<li style:--cor={m.cor}>
				<span class="astro" aria-hidden="true"></span>
				<span class="nome">{m.rotulo}</span>
				<span class="topicos numero">{contar(m.topicos.length, 'tópico')}</span>
				<span class="barra" aria-hidden="true"><span style:width="{m.largura}%"></span></span>
				<span class="docs numero">
					{contar(m.n, 'documento')}
					<span class="fracao">{formatarPorcentagem(m.fracao)}</span>
				</span>
			</li>
		{/each}
	</ol>
</section>

<style>
	.macrotemas {
		display: grid;
		gap: 1.25rem;
	}

	header {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.5rem 2rem;
	}

	h2 {
		font-size: clamp(1.6rem, 2.6vw, 2.1rem);
		font-weight: 380;
	}

	header p {
		color: var(--texto-suave);
		max-width: 34rem;
		font-size: 0.92rem;
	}

	ol {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		border-top: 1px solid var(--linha);
	}

	li {
		display: grid;
		grid-template-columns: 1.25rem minmax(12rem, 1.4fr) 6.5rem minmax(6rem, 1fr) 12.5rem;
		align-items: center;
		gap: 1rem;
		padding: 0.75rem 0;
		border-bottom: 1px solid var(--linha);
	}

	.astro {
		width: 0.85rem;
		height: 0.85rem;
		border-radius: 50%;
		background: var(--cor);
		box-shadow: 0 0 0 3px color-mix(in srgb, var(--cor) 22%, transparent),
			0 0 14px color-mix(in srgb, var(--cor) 55%, transparent);
	}

	:global([data-tema='prancha']) .astro {
		box-shadow: 0 0 0 1px var(--texto), 0 0 0 4px color-mix(in srgb, var(--cor) 25%, transparent);
	}

	.nome {
		font-weight: 500;
	}

	.topicos,
	.docs {
		font-size: 0.8rem;
		color: var(--texto-suave);
	}

	.docs {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
	}

	.fracao {
		min-width: 2.6rem;
		text-align: right;
		color: var(--texto);
	}

	.barra {
		height: 4px;
		border-radius: 2px;
		background: var(--linha);
		overflow: hidden;
	}

	.barra span {
		display: block;
		height: 100%;
		border-radius: 2px;
		background: var(--cor);
	}

	@media (max-width: 820px) {
		li {
			grid-template-columns: 1.25rem minmax(0, 1fr) auto;
			gap: 0.35rem 0.75rem;
		}

		.barra {
			grid-column: 2 / -1;
		}

		.docs {
			grid-column: 2 / -1;
			justify-content: flex-start;
		}
	}
</style>
