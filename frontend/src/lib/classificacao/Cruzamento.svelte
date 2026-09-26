<script lang="ts">
	/**
	 * A variável cruzada com macrotemas, tópicos ou revistas: uma linha por grupo, uma coluna por valor. Cada célula
	 * mostra a participação do valor entre os documentos classificados do grupo, com uma barra da cor do valor, e é
	 * um botão que lista os documentos dela com a evidência. Grupos sem documento classificado no recorte somem.
	 */
	import { formatarInteiro, formatarPorcentagem } from '$lib/formato';
	import type { Cruzamento, VariavelVista } from './agregar';

	let {
		dados,
		variavel,
		cores,
		escolhida,
		aoEscolher
	}: {
		dados: Cruzamento;
		variavel: VariavelVista;
		cores: string[];
		escolhida: { linha: number; valor: number } | null;
		aoEscolher: (linha: number, valor: number) => void;
	} = $props();

	const k = $derived(variavel.valores.length);
	const visiveis = $derived(dados.linhas.map((l, i) => ({ ...l, i })).filter((l) => dados.classificados[l.i] > 0));
</script>

<div class="rolagem">
	<table class="cruzamento" data-testid="cruzamento">
		<thead>
			<tr>
				<th scope="col" class="grupo"><span class="visualmente-oculto">Grupo</span></th>
				<th scope="col" class="n">n</th>
				{#each variavel.rotulos as r, v (v)}
					<th scope="col" title={variavel.definicoes[v] || undefined}>
						<span class="amostra" style:background={cores[v]}></span>{r}
					</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each visiveis as l (l.chave)}
				<tr>
					<th scope="row" class="grupo">
						{#if l.cor}<span class="ponto" style:background={l.cor}></span>{/if}{l.rotulo}
					</th>
					<td class="n">{formatarInteiro(dados.classificados[l.i])}</td>
					{#each variavel.valores as _, v (v)}
						{@const n = dados.n[l.i * k + v]}
						{@const p = n / dados.classificados[l.i]}
						<td>
							<button
								type="button"
								class="celula"
								class:escolhida={escolhida?.linha === l.i && escolhida.valor === v}
								disabled={n === 0}
								aria-pressed={escolhida?.linha === l.i && escolhida.valor === v}
								aria-label="{l.rotulo}, {variavel.rotulos[v]}: {formatarInteiro(n)} documentos, {formatarPorcentagem(p)}. Mostrar os documentos."
								data-testid="celula"
								onclick={() => aoEscolher(l.i, v)}
							>
								<span class="valor">{n ? formatarPorcentagem(p) : '·'}</span>
								<span class="barra" style:width="{p * 100}%" style:background={cores[v]}></span>
							</button>
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

	.cruzamento {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.82rem;
	}

	th,
	td {
		padding: 0.15rem 0.3rem;
		border-bottom: 1px solid var(--linha);
		text-align: left;
		vertical-align: middle;
	}

	thead th {
		font-weight: 500;
		color: var(--texto-suave);
		vertical-align: bottom;
		min-width: 4.5rem;
	}

	.grupo {
		min-width: 12rem;
		max-width: 20rem;
		font-weight: 400;
		color: var(--texto);
	}

	.n {
		min-width: 2.5rem;
		text-align: right;
		font-variant-numeric: tabular-nums;
		color: var(--texto-suave);
	}

	.amostra,
	.ponto {
		display: inline-block;
		width: 0.6rem;
		height: 0.6rem;
		margin-right: 0.35rem;
		border-radius: 2px;
	}

	.ponto {
		border-radius: 50%;
	}

	.celula {
		display: grid;
		gap: 2px;
		width: 100%;
		padding: 0.15rem 0.25rem;
		border: 1px solid transparent;
		border-radius: var(--raio-pequeno);
		background: none;
		color: var(--texto);
		font: inherit;
		font-variant-numeric: tabular-nums;
		text-align: left;
		cursor: pointer;
	}

	.celula:hover:not(:disabled),
	.celula.escolhida {
		border-color: var(--linha-forte);
		background: var(--superficie-alta);
	}

	.celula:disabled {
		color: var(--texto-fraco);
		cursor: default;
	}

	.barra {
		display: block;
		height: 3px;
		border-radius: 2px;
		min-width: 0;
	}
</style>
