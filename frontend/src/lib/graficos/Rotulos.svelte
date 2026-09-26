<script lang="ts" module>
	export type Caixa = { x0: number; y0: number; x1: number; y1: number };

	export interface ItemRotulo {
		id: string;
		texto: string;
		/** Posição em NDC (a mesma dos pontos). */
		x: number;
		y: number;
		cor: string;
		/** Os de maior peso são posicionados primeiro e vencem as colisões. */
		peso: number;
		ativo?: boolean;
		aoClicar?: () => void;
	}
</script>

<script lang="ts">
	/**
	 * Rótulos sobre o mapa, em HTML (texto nítido, clicável e legível por leitores de tela). A posição vem de
	 * `projetar`, que acompanha a câmera; `versao` muda a cada movimento para recalcular. Rótulos que colidiriam
	 * com um de peso maior ficam escondidos.
	 */
	let {
		itens,
		projetar,
		versao,
		largura,
		altura,
		aoRoda,
		inertes = false,
		bloqueios = () => []
	}: {
		itens: ItemRotulo[];
		projetar: ((x: number, y: number) => [number, number]) | null;
		versao: number;
		largura: number;
		altura: number;
		/** A roda do mouse sobre um rótulo continua aproximando o mapa. */
		aoRoda?: (evento: WheelEvent) => void;
		/** Deixam o mouse passar (durante o laço, para desenhar por cima deles). */
		inertes?: boolean;
		/** Áreas cobertas por painéis (px, relativas ao mapa), onde nenhum rótulo fica. */
		bloqueios?: () => Caixa[];
	} = $props();
	const colide = (a: Caixa, b: Caixa) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;

	const posicionados = $derived.by(() => {
		void versao;
		if (!projetar) return [];
		const ocupadas: Caixa[] = [...bloqueios()];
		const saida: { item: ItemRotulo; px: number; py: number }[] = [];
		for (const item of [...itens].sort((a, b) => b.peso - a.peso)) {
			const [px, py] = projetar(item.x, item.y);
			const meia = Math.min(item.texto.length, 34) * 3.6 + 10;
			const caixa = { x0: px - meia, y0: py - 12, x1: px + meia, y1: py + 12 };
			if (caixa.x1 < 0 || caixa.x0 > largura || caixa.y1 < 0 || caixa.y0 > altura) continue;
			if (ocupadas.some((o) => colide(o, caixa))) continue;
			ocupadas.push(caixa);
			saida.push({ item, px, py });
		}
		return saida;
	});
</script>

<div class="rotulos" class:inertes>
	{#each posicionados as { item, px, py } (item.id)}
		<button
			type="button"
			class="rotulo"
			data-testid="rotulo-mapa"
			class:ativo={item.ativo}
			style:transform="translate({px}px, {py}px) translate(-50%, -50%)"
			style:--cor={item.cor}
			title={item.texto}
			onclick={item.aoClicar}
			onwheel={aoRoda}
		>
			{item.texto}
		</button>
	{/each}
</div>

<style>
	.rotulos {
		position: absolute;
		inset: 0;
		pointer-events: none;
		overflow: hidden;
	}

	.rotulo {
		position: absolute;
		top: 0;
		left: 0;
		max-width: 16rem;
		padding: 0.15rem 0.5rem;
		overflow: hidden;
		font: 500 0.78rem/1.3 var(--fonte-texto);
		color: var(--texto);
		text-overflow: ellipsis;
		white-space: nowrap;
		background: color-mix(in oklab, var(--fundo) 72%, transparent);
		border: 1px solid color-mix(in oklab, var(--cor) 70%, transparent);
		border-radius: 999px;
		pointer-events: auto;
		cursor: pointer;
	}

	.inertes .rotulo {
		pointer-events: none;
		opacity: 0.6;
	}

	.rotulo:hover,
	.rotulo.ativo {
		background: color-mix(in oklab, var(--cor) 28%, var(--fundo));
	}

	@media (prefers-reduced-motion: no-preference) {
		.rotulo {
			transition: background 0.15s;
		}
	}
</style>
