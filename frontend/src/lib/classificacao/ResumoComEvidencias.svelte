<script lang="ts" module>
	import type { Evidencia } from '$lib/contrato/tipos';
	import { posicoesJs } from './posicoes';

	export interface Segmento {
		texto: string;
		/** Variáveis cuja evidência cobre este pedaço do resumo. */
		variaveis: string[];
	}

	/** O resumo partido nos limites das evidências localizadas nele (as do título e as ausentes ficam de fora). */
	export function segmentar(resumo: string, evidencias: Record<string, Evidencia>): Segmento[] {
		const faixas = Object.entries(evidencias)
			.filter(([, e]) => (e.campo ?? 'resumo') === 'resumo' && e.status !== 'ausente')
			.map(([v, e]) => ({ v, ...posicoesJs(resumo, e) }))
			.filter(({ inicio, fim }) => inicio != null && fim != null && inicio >= 0 && fim <= resumo.length && fim > inicio)
			.map(({ v, inicio, fim }) => ({ v, a: inicio!, b: fim! }));
		const cortes = [...new Set([0, resumo.length, ...faixas.flatMap((f) => [f.a, f.b])])].sort((x, y) => x - y);
		const saida: Segmento[] = [];
		for (let k = 0; k < cortes.length - 1; k += 1) {
			const [a, b] = [cortes[k], cortes[k + 1]];
			const variaveis = faixas.filter((f) => f.a <= a && f.b >= b).map((f) => f.v);
			const ultimo = saida.at(-1);
			if (ultimo && ultimo.variaveis.join() === variaveis.join()) ultimo.texto += resumo.slice(a, b);
			else saida.push({ texto: resumo.slice(a, b), variaveis });
		}
		return saida;
	}
</script>

<script lang="ts">
	/**
	 * O resumo com as evidências da classificação marcadas, e a lista das respostas do modelo. Passar o mouse (ou o
	 * foco) numa resposta acende o trecho dela no resumo e apaga os outros; um clique deixa aceso. Respostas cujo trecho não foi achado no
	 * resumo, ou que não precisavam de trecho, dizem isso na lista.
	 */
	import type { CodebookContrato } from '$lib/contrato/tipos';

	let {
		resumo,
		idioma,
		evidencias,
		codebook
	}: {
		resumo: string;
		idioma: string | null;
		evidencias: Record<string, Evidencia>;
		codebook: CodebookContrato | null;
	} = $props();

	// o trecho aceso: o da resposta sob o mouse (ou com foco), senão o da resposta fixada com um clique
	let sobre = $state<string | null>(null);
	let fixa = $state<string | null>(null);
	const ativa = $derived(sobre ?? fixa);
	const segmentos = $derived(segmentar(resumo, evidencias));
	const ordem = $derived(
		codebook ? codebook.variaveis.map((v) => v.id).filter((id) => id in evidencias) : Object.keys(evidencias)
	);

	function nome(id: string): string {
		return codebook?.variaveis.find((v) => v.id === id)?.rotulo ?? id.replaceAll('_', ' ');
	}
	function valor(id: string): string {
		const e = evidencias[id];
		const v = codebook?.variaveis.find((x) => x.id === id);
		const rotulo = (c: string) => v?.categorias?.find((x) => x.valor === c)?.rotulo ?? c.replaceAll('_', ' ');
		if (typeof e.valor === 'boolean') return e.valor ? 'Sim' : 'Não';
		if (Array.isArray(e.valor)) return e.valor.map(rotulo).join(' + ') || 'nenhuma';
		return e.valor === null ? '—' : v?.tipo === 'texto' ? e.valor : rotulo(e.valor);
	}
	const NOTAS: Record<string, string> = {
		ausente: 'trecho não encontrado no resumo',
		dispensada: 'sem trecho',
		aproximada: 'trecho quase igual'
	};
</script>

<p class="resumo" lang={idioma ?? undefined} data-testid="resumo-marcado">
	{#each segmentos as s, k (k)}{#if s.variaveis.length}<mark
				class:acesa={ativa !== null && s.variaveis.includes(ativa)}
				class:apagada={ativa !== null && !s.variaveis.includes(ativa)}
				data-variaveis={s.variaveis.join(' ')}>{s.texto}</mark
			>{:else}{s.texto}{/if}{/each}
</p>

<section class="respostas" aria-label="Classificação pelo codebook" data-testid="respostas-classificacao">
	<h3 class="rotulo-miudo">Classificação</h3>
	<ul>
		{#each ordem as id (id)}
			{@const e = evidencias[id]}
			<li>
				<button
					type="button"
					class="resposta"
					aria-pressed={fixa === id}
					onclick={() => (fixa = fixa === id ? null : id)}
					onpointerenter={() => (sobre = id)}
					onpointerleave={() => (sobre = null)}
					onfocus={() => (sobre = id)}
					onblur={() => (sobre = null)}
					data-testid="resposta"
				>
					<span class="nome">{nome(id)}</span>
					<span class="valor">
						{valor(id)}
						{#if e.campo === 'titulo'}<span class="nota">no título</span>{/if}
						{#if NOTAS[e.status]}<span class="nota">{NOTAS[e.status]}</span>{/if}
					</span>
				</button>
			</li>
		{/each}
	</ul>
</section>

<style>
	.resumo {
		margin: 0;
		font-size: 0.92rem;
		line-height: 1.6;
	}

	mark {
		background: color-mix(in oklab, var(--acento) 16%, transparent);
		color: inherit;
		border-radius: 2px;
		transition:
			background 0.15s,
			opacity 0.15s;
	}

	mark.acesa {
		background: color-mix(in oklab, var(--acento) 42%, transparent);
	}

	mark.apagada {
		background: transparent;
	}

	.respostas h3 {
		margin: 0 0 0.3rem;
	}

	ul {
		display: grid;
		gap: 0.15rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.resposta {
		display: grid;
		grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
		gap: 0.6rem;
		width: 100%;
		padding: 0.15rem 0.3rem;
		border: 0;
		border-radius: var(--raio-pequeno);
		background: none;
		font: inherit;
		font-size: 0.82rem;
		text-align: left;
		cursor: pointer;
	}

	.resposta:hover,
	.resposta:focus-visible,
	.resposta[aria-pressed='true'] {
		background: var(--superficie-alta);
	}

	.nome {
		color: var(--texto-suave);
	}

	.valor {
		color: var(--texto);
	}

	.nota {
		display: block;
		font-size: 0.72rem;
		color: var(--texto-fraco);
	}

	@media (prefers-reduced-motion: reduce) {
		mark {
			transition: none;
		}
	}
</style>
