<script lang="ts" module>
	export interface CoberturaAno {
		ano: number;
		identificada: number;
		naoIdentificada: number;
		semAfiliacao: number;
	}

	export const LIMIAR_AVISO = 0.2; // fração do peso sem afiliação a partir da qual o ano entra no aviso

	/** Os trechos de anos seguidos em que mais de `LIMIAR_AVISO` do peso fica sem afiliação. */
	export function anosFracos(anos: CoberturaAno[]): [number, number][] {
		const trechos: [number, number][] = [];
		for (const a of anos) {
			const total = a.identificada + a.naoIdentificada + a.semAfiliacao;
			if (!total || a.semAfiliacao / total <= LIMIAR_AVISO) continue;
			const ultimo = trechos.at(-1);
			if (ultimo && ultimo[1] === a.ano - 1) ultimo[1] = a.ano;
			else trechos.push([a.ano, a.ano]);
		}
		return trechos;
	}
</script>

<script lang="ts">
	/**
	 * A cobertura da geografia ano a ano: de cada ano, quanto do peso está numa instituição identificada, numa
	 * afiliação que não casou e em autores sem afiliação informada. Nos artigos antigos, a ArticleMeta quase não
	 * traz afiliação normalizada, e muitos autores ficam sem afiliação: comparar anos exige cuidado.
	 */
	import { formatarPorcentagem } from '$lib/formato';
	import Eixo from '$lib/graficos/Eixo.svelte';
	import Dica from '$lib/graficos/Dica.svelte';

	let { anos }: { anos: CoberturaAno[] } = $props();

	const CATEGORIAS = [
		{ chave: 'identificada', rotulo: 'instituição identificada', cor: 'var(--seq-5)' },
		{ chave: 'naoIdentificada', rotulo: 'afiliação não identificada', cor: 'var(--seq-2)' },
		{ chave: 'semAfiliacao', rotulo: 'sem afiliação informada', cor: 'var(--linha-forte)' }
	] as const;

	let largura = $state(700);
	const altura = 170;
	const margem = { esq: 44, dir: 8, topo: 8, base: 26 };
	const n = $derived(anos.length);
	// sem largura medida ainda (0, num instante do celular), nenhuma barra de largura negativa
	const passo = $derived(Math.max(0, largura - margem.esq - margem.dir) / Math.max(1, n));
	const x = $derived((j: number) => margem.esq + j * passo + passo / 2);
	const y = (v: number) => altura - margem.base - v * (altura - margem.topo - margem.base);

	const barras = $derived(
		anos.map((a) => {
			const total = a.identificada + a.naoIdentificada + a.semAfiliacao;
			let base = 0;
			return CATEGORIAS.map((c) => {
				const f = total ? a[c.chave] / total : 0;
				const r = { cor: c.cor, y0: base, y1: base + f, f };
				base += f;
				return r;
			});
		})
	);

	let dica = $state<{ x: number; y: number; j: number } | null>(null);
	const linhasDica = $derived(
		dica
			? [
					String(anos[dica.j].ano),
					...CATEGORIAS.map((c, k) => `${formatarPorcentagem(barras[dica!.j][k].f)} ${c.rotulo}`)
				]
			: []
	);
</script>

<div class="cobertura" bind:clientWidth={largura}>
	<svg width={largura} height={altura} role="img" aria-label="Cobertura das afiliações por ano">
		{#each barras as pilha, j (anos[j].ano)}
			<g
				role="presentation"
				onpointermove={(e) => {
					const caixa = (e.currentTarget as SVGElement).ownerSVGElement!.getBoundingClientRect();
					dica = { x: e.clientX - caixa.left, y: e.clientY - caixa.top, j };
				}}
				onpointerleave={() => (dica = null)}
			>
				{#each pilha as parte, k (k)}
					<rect
						x={x(j) - passo * 0.38}
						width={passo * 0.76}
						y={y(parte.y1)}
						height={Math.max(0, y(parte.y0) - y(parte.y1))}
						style:fill={parte.cor}
					/>
				{/each}
			</g>
		{/each}
		<Eixo orientacao="x" anos={anos.map((a) => a.ano)} posicao={altura - margem.base} escala={x} comprimento={largura} />
		<Eixo
			orientacao="y"
			posicao={margem.esq - 4}
			escala={y}
			dominio={[0, 1]}
			comprimento={altura - margem.topo - margem.base}
			porcentagem
		/>
	</svg>
	{#if dica}
		<Dica x={dica.x} y={dica.y} linhas={linhasDica} />
	{/if}
	<ul class="legenda">
		{#each CATEGORIAS as c (c.chave)}
			<li><span class="caixa" style:background={c.cor}></span>{c.rotulo}</li>
		{/each}
	</ul>
</div>

<style>
	.cobertura {
		position: relative;
		width: 100%;
	}

	svg {
		display: block;
		overflow: visible;
	}

	.legenda {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem 1rem;
		margin: 0.5rem 0 0;
		padding: 0;
		list-style: none;
		font-size: 0.78rem;
		color: var(--texto-suave);
	}

	.legenda li {
		display: flex;
		align-items: center;
		gap: 0.35rem;
	}

	.caixa {
		width: 14px;
		height: 14px;
		border-radius: 2px;
	}
</style>
