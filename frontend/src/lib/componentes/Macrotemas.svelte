<script lang="ts">
	import type { Topicos } from '$lib/contrato/tipos';
	import { escreverFiltros, FILTROS_PADRAO, rota } from '$lib/estado/url';
	import { contar, formatarDecimal, formatarPorcentagem } from '$lib/formato';
	import Sparkline from '$lib/graficos/Sparkline.svelte';

	/**
	 * Legenda dos macrotemas: cor, participação ano a ano (a mini-série), tendência, número de tópicos e peso no
	 * corpus. O nome leva à vista Tópicos com o macrotema aberto.
	 */
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
				<a class="nome" href={rota('/topicos', escreverFiltros({ ...FILTROS_PADRAO, macro: m.id }))}>{m.rotulo}</a>
				<span class="serie">
					{#if m.serie}
						<Sparkline
							observado={m.serie.prop}
							largura={96}
							altura={24}
							cor={m.cor}
							rotulo="Participação de {m.rotulo} por ano, de {topicos.anos[0]} a {topicos.anos[topicos.anos.length - 1]}"
						/>
					{/if}
					{#if m.tendencia && (m.tendencia.direcao === 'alta' || m.tendencia.direcao === 'queda') && m.tendencia.pp_periodo != null}
						<span class="tendencia" data-testid="tendencia-macro" title="Variação da participação no período, pela tendência ajustada">
							{m.tendencia.direcao === 'alta' ? '↑' : '↓'} {formatarDecimal(Math.abs(m.tendencia.pp_periodo), 1)} p.p.
						</span>
					{/if}
				</span>
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
		/* a linha quebra pela largura da seção, não da janela: com o trilho ao lado, a janela engana */
		container-type: inline-size;
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
		grid-template-columns: 1.25rem minmax(12rem, 1.4fr) 11.5rem 6.5rem minmax(6rem, 1fr) 12.5rem;
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
		color: var(--texto);
		text-decoration: none;
	}

	.nome:hover {
		text-decoration: underline;
		text-underline-offset: 0.2em;
	}

	.serie {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.tendencia {
		font-family: var(--fonte-mono);
		font-size: 0.72rem;
		color: var(--texto-suave);
		white-space: nowrap;
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

	/* a linha inteira pede ~55rem (as colunas fixas e os espaços); abaixo disso, a série e os números descem */
	@container (max-width: 56rem) {
		li {
			grid-template-columns: 1.25rem minmax(0, 1fr) auto;
			gap: 0.35rem 0.75rem;
		}

		.barra,
		.serie {
			grid-column: 2 / -1;
		}

		/* o número de tópicos fica ao lado do nome, na coluna estreita da direita */
		.topicos {
			grid-column: 3;
			grid-row: 1;
			text-align: right;
		}

		.docs {
			grid-column: 2 / -1;
			justify-content: flex-start;
		}
	}
</style>
