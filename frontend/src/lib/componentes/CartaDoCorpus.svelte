<script lang="ts">
	import type { Topicos } from '$lib/contrato/tipos';
	import { contar } from '$lib/formato';

	/**
	 * Carta celeste dos tópicos, na capa. Cada tópico é uma estrela no centróide dele no
	 * mapa, com o tamanho pelo número de documentos. As linhas ligam os tópicos de um
	 * mesmo macrotema pela árvore geradora mínima, como numa constelação.
	 *
	 * É SVG puro e pequeno (algumas dezenas de pontos). O mapa de documentos, com
	 * regl-scatterplot, chega no M3.
	 */
	let { topicos }: { topicos: Topicos } = $props();

	const uid = $props.id();
	const MARGEM = 12;

	const carta = $derived.by(() => {
		const lista = topicos.topicos;
		const xs = lista.map((t) => t.centroide[0]);
		const ys = lista.map((t) => t.centroide[1]);
		const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
		// Escala única nos dois eixos (sem distorcer as distâncias), centrada no quadro 100×100.
		const escala = (100 - 2 * MARGEM) / Math.max(x1 - x0, y1 - y0, 1e-9);
		const dx = (100 - (x1 - x0) * escala) / 2;
		const dy = (100 - (y1 - y0) * escala) / 2;
		const nMax = Math.max(...lista.map((t) => t.n), 1);
		const cores = new Map(topicos.macrotemas.map((m) => [m.id, m.cor]));
		const nomes = new Map(topicos.macrotemas.map((m) => [m.id, m.rotulo]));

		const estrelas = lista.map((t) => ({
			id: t.id,
			x: dx + (t.centroide[0] - x0) * escala,
			// No SVG o y cresce para baixo; invertido, a carta fica com a mesma orientação do mapa.
			y: 100 - (dy + (t.centroide[1] - y0) * escala),
			r: 0.9 + 2.3 * Math.sqrt(t.n / nMax),
			cor: t.cor,
			macro: t.macro_id,
			titulo: `${t.rotulo} · ${contar(t.n, 'documento')} · ${nomes.get(t.macro_id) ?? ''}`
		}));

		const linhas = topicos.macrotemas.flatMap((m) =>
			arvoreMinima(estrelas.filter((e) => e.macro === m.id)).map(([a, b]) => ({
				a,
				b,
				cor: cores.get(m.id) ?? 'currentColor'
			}))
		);
		return { estrelas, linhas };
	});

	/** Árvore geradora mínima (Prim): liga todos os pontos com o menor comprimento total. */
	function arvoreMinima<T extends { x: number; y: number }>(pontos: T[]): [T, T][] {
		if (pontos.length < 2) return [];
		const dentro = [pontos[0]];
		const fora = pontos.slice(1);
		const arestas: [T, T][] = [];
		while (fora.length) {
			let melhor: [number, number, number] = [Infinity, 0, 0];
			dentro.forEach((a, i) =>
				fora.forEach((b, j) => {
					const d = (a.x - b.x) ** 2 + (a.y - b.y) ** 2;
					if (d < melhor[0]) melhor = [d, i, j];
				})
			);
			const [b] = fora.splice(melhor[2], 1);
			arestas.push([dentro[melhor[1]], b]);
			dentro.push(b);
		}
		return arestas;
	}

	// Estrelas de fundo, fixas (gerador determinístico). Só aparecem no tema Observatório.
	let s = 7;
	const aleatorio = () => (s = (s * 1664525 + 1013904223) % 2 ** 32) / 2 ** 32;
	const fundo = Array.from({ length: 90 }, () => ({
		x: aleatorio() * 100,
		y: aleatorio() * 100,
		r: 0.12 + aleatorio() * 0.22
	}));
</script>

<figure class="carta transicao-tema" aria-labelledby="{uid}-legenda">
	<svg viewBox="0 0 100 100" role="img" aria-labelledby="{uid}-legenda">
		<defs>
			<filter id="{uid}-brilho" x="-50%" y="-50%" width="200%" height="200%">
				<feGaussianBlur stdDeviation="0.9" result="borrado" />
				<feMerge>
					<feMergeNode in="borrado" />
					<feMergeNode in="SourceGraphic" />
				</feMerge>
			</filter>
		</defs>

		<g class="fundo">
			{#each fundo as f, i (i)}
				<circle cx={f.x} cy={f.y} r={f.r} />
			{/each}
		</g>

		<g class="grade">
			<circle cx="50" cy="50" r="16" />
			<circle cx="50" cy="50" r="32" />
			<circle cx="50" cy="50" r="47" />
			{#each [0, 30, 60, 90, 120, 150] as grau (grau)}
				<line x1="50" y1="3" x2="50" y2="97" transform="rotate({grau} 50 50)" />
			{/each}
			{#each Array.from({ length: 72 }, (_, i) => i * 5) as grau (grau)}
				<line class="marca" x1="50" y1="3" x2="50" y2={grau % 30 === 0 ? 5.2 : 4} transform="rotate({grau} 50 50)" />
			{/each}
		</g>

		<g class="constelacoes">
			{#each carta.linhas as l, i (i)}
				<line x1={l.a.x} y1={l.a.y} x2={l.b.x} y2={l.b.y} stroke={l.cor} />
			{/each}
		</g>

		<g class="estrelas" filter="url(#{uid}-brilho)">
			{#each carta.estrelas as e (e.id)}
				<circle cx={e.x} cy={e.y} r={e.r} fill={e.cor}>
					<title>{e.titulo}</title>
				</circle>
			{/each}
		</g>
	</svg>
	<figcaption id="{uid}-legenda">
		<span class="rotulo-miudo">Carta I</span>
		Os {topicos.topicos.length} tópicos do corpus: cada estrela fica no centróide do tópico no mapa, com
		tamanho pelo número de documentos. As linhas unem os tópicos de um mesmo macrotema.
	</figcaption>
</figure>

<style>
	.carta {
		margin: 0;
		display: grid;
		gap: 0.75rem;
		padding: 0.9rem;
		border: 1px solid var(--linha);
		border-radius: var(--raio);
		background: var(--superficie);
		box-shadow: var(--sombra);
		/* Moldura dupla, como a borda gravada de uma prancha de atlas. */
		outline: 1px solid var(--linha);
		outline-offset: 5px;
	}

	svg {
		display: block;
		width: 100%;
		height: auto;
		aspect-ratio: 1;
		border-radius: 50%;
		background: radial-gradient(circle, var(--brilho-frio), transparent 70%);
	}

	.fundo circle {
		fill: var(--estrela);
	}

	.grade circle,
	.grade line {
		fill: none;
		stroke: var(--linha);
		stroke-width: 0.25;
	}

	.grade .marca {
		stroke: var(--linha-forte);
	}

	.constelacoes line {
		stroke-width: 0.35;
		stroke-opacity: 0.6;
		stroke-linecap: round;
	}

	.estrelas circle {
		stroke: var(--fundo);
		stroke-width: 0.3;
	}

	/* No papel, sem brilho: estrelas com contorno de tinta, como numa carta impressa. */
	:global([data-tema='prancha']) .estrelas {
		filter: none;
	}

	:global([data-tema='prancha']) .estrelas circle {
		stroke: var(--texto);
		stroke-width: 0.25;
	}

	:global([data-tema='prancha']) .constelacoes line {
		stroke-opacity: 0.85;
		stroke-dasharray: 1 0.8;
	}

	figcaption {
		font-size: 0.8rem;
		line-height: 1.45;
		color: var(--texto-suave);
	}

	figcaption .rotulo-miudo {
		margin-right: 0.35rem;
		color: var(--acento);
	}
</style>
