/**
 * Pontos mock para o spike: `n` pontos em `nClusters` nuvens gaussianas,
 * já em coordenadas normalizadas [-1, 1], como o regl-scatterplot espera.
 * O gerador é determinístico (semente fixa) para o screenshot ser reprodutível.
 */

export interface PontosMock {
	/** Linhas `[x, y, cluster]`; `cluster` é inteiro, logo categórico para o regl-scatterplot. */
	linhas: [number, number, number][];
	clusterDoPonto: number[];
	nClusters: number;
}

// mulberry32: PRNG pequeno e suficiente para dados de teste.
function mulberry32(semente: number): () => number {
	let a = semente >>> 0;
	return () => {
		a = (a + 0x6d2b79f5) >>> 0;
		let t = a;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

function gaussiana(aleatorio: () => number): number {
	// Box-Muller
	const u = 1 - aleatorio();
	const v = aleatorio();
	return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

const limitar = (v: number) => Math.max(-0.99, Math.min(0.99, v));

export function gerarPontos(n = 10_000, nClusters = 40, semente = 20240): PontosMock {
	const aleatorio = mulberry32(semente);
	const centros = Array.from({ length: nClusters }, () => ({
		x: -0.85 + 1.7 * aleatorio(),
		y: -0.85 + 1.7 * aleatorio(),
		desvio: 0.015 + 0.045 * aleatorio()
	}));

	const linhas: [number, number, number][] = [];
	const clusterDoPonto: number[] = [];
	for (let i = 0; i < n; i++) {
		const c = i % nClusters;
		const { x, y, desvio } = centros[c];
		linhas.push([
			limitar(x + desvio * gaussiana(aleatorio)),
			limitar(y + desvio * gaussiana(aleatorio)),
			c
		]);
		clusterDoPonto.push(c);
	}
	return { linhas, clusterDoPonto, nClusters };
}

function hslParaHex(h: number, s: number, l: number): string {
	const a = s * Math.min(l, 1 - l);
	const f = (k: number) => {
		const m = (k + h / 30) % 12;
		const cor = l - a * Math.max(-1, Math.min(m - 3, 9 - m, 1));
		return Math.round(255 * cor)
			.toString(16)
			.padStart(2, '0');
	};
	return `#${f(0)}${f(8)}${f(4)}`;
}

/** Paleta categórica simples (ângulo áureo), clara o bastante para fundo escuro. */
export function paletaCategorica(n: number, luminosidade = 0.62): string[] {
	return Array.from({ length: n }, (_, i) =>
		hslParaHex((i * 137.508) % 360, 0.7, i % 2 === 0 ? luminosidade : luminosidade - 0.1)
	);
}
