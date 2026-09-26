<script lang="ts">
	/**
	 * A matriz de confusão de uma variável: linhas = a referência do par, colunas = o outro. A diagonal (acordo) fica
	 * na cor de acento; fora dela, a intensidade cresce com a contagem. Linhas e colunas vazias somem.
	 */
	import type { Matriz } from '$lib/contrato/tipos';

	let { matriz, referencia, comparado, rotulo }: { matriz: Matriz; referencia: string; comparado: string; rotulo: (valor: string) => string } =
		$props();

	const usados = $derived(
		matriz.rotulos
			.map((_, i) => i)
			.filter((i) => matriz.valores[i].some((x) => x > 0) || matriz.valores.some((linha) => linha[i] > 0))
	);
	const maior = $derived(Math.max(1, ...matriz.valores.flat()));
</script>

<div class="rolagem">
	<table class="matriz" data-testid="matriz-confusao">
		<caption>Linhas: <strong>{referencia}</strong>; colunas: <strong>{comparado}</strong>.</caption>
		<thead>
			<tr>
				<th scope="col"></th>
				{#each usados as j (j)}<th scope="col">{rotulo(matriz.rotulos[j])}</th>{/each}
			</tr>
		</thead>
		<tbody>
			{#each usados as i (i)}
				<tr>
					<th scope="row">{rotulo(matriz.rotulos[i])}</th>
					{#each usados as j (j)}
						{@const n = matriz.valores[i][j]}
						<td
							class:diagonal={i === j}
							style:--intensidade={n / maior}
							aria-label="{rotulo(matriz.rotulos[i])} × {rotulo(matriz.rotulos[j])}: {n}"
						>
							{n || '·'}
						</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
	.rolagem {
		overflow-x: auto;
	}

	.matriz {
		border-collapse: collapse;
		font-size: 0.8rem;
		font-variant-numeric: tabular-nums;
	}

	caption {
		caption-side: bottom;
		padding-top: 0.4rem;
		text-align: left;
		font-size: 0.78rem;
		color: var(--texto-fraco);
	}

	th {
		padding: 0.2rem 0.4rem;
		font-weight: 400;
		color: var(--texto-suave);
		text-align: left;
	}

	thead th {
		max-width: 7rem;
		vertical-align: bottom;
	}

	td {
		min-width: 2.4rem;
		padding: 0.25rem 0.4rem;
		border: 1px solid var(--linha);
		text-align: center;
		background: color-mix(in oklab, var(--texto-fraco) calc(var(--intensidade) * 45%), transparent);
	}

	td.diagonal {
		background: color-mix(in oklab, var(--acento) calc(var(--intensidade) * 55%), transparent);
		font-weight: 600;
	}
</style>
