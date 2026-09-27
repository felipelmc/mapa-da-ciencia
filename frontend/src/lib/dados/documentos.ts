/**
 * O `documentos.json` colunar em arrays tipados, prontos para o mapa.
 *
 * - As coordenadas do UMAP viram NDC (de -1 a 1), como o regl-scatterplot exige, preservando a proporção
 *   (a mesma escala nos dois eixos) e com uma pequena margem. `paraNdc`/`deNdc` convertem nos dois sentidos:
 *   o laço fica na URL em coordenadas dos dados, que não dependem do tamanho da tela.
 * - O enquadramento resiste a ilhas: o UMAP põe longe um grupo de documentos desligado do resto (no piloto,
 *   dez artigos com o mesmo resumo), e alguns pontos distantes achatariam a nuvem inteira num canto da tela.
 *   Quando a extensão total passa de `ESTICAMENTO_MAXIMO` vezes a dos quantis de 0,5% a 99,5%, a escala usa a
 *   destes, com folga; os pontos de fora ficam além de [-1, 1] e aparecem ao afastar o zoom.
 * - Os vizinhos ficam num só array, 5 por documento (−1 onde faltar).
 * - As colunas da classificação (`cls`) viram `Int16Array`, uma por variável, com os valores em `clsValores`.
 */
import type { Documentos } from '$lib/contrato/tipos';

export const VIZINHOS = 5;
const MARGEM = 0.94; // fração de [-1, 1] ocupada pelos pontos
const ESTICAMENTO_MAXIMO = 1.5;
const FOLGA_QUANTIS = 1.2; // a caixa dos quantis ganha 20%, para as pontas próximas continuarem na tela
const QUANTIL = 0.005;

export interface Escala {
	cx: number;
	cy: number;
	s: number;
}

export interface TabelaDocumentos {
	n: number;
	ids: string[];
	titulos: string[];
	dois: (string | null)[];
	autores: string[];
	ano: Uint16Array;
	revista: Uint16Array;
	idioma: Uint8Array;
	/** Coordenadas em NDC. */
	x: Float32Array;
	y: Float32Array;
	/** Id estável do tópico, ou −1. */
	topico: Int32Array;
	/** 0 = núcleo (`cluster`), 1 = reatribuído ou sem tópico (`vizinho`). */
	atribuicao: Uint8Array;
	/** `VIZINHOS` índices por documento, em sequência. */
	vizinhos: Int32Array;
	revistas: string[];
	idiomas: string[];
	/** Classificação: variável → índice em `clsValores[variavel]` por documento (−1 = não classificado). */
	cls: Record<string, Int16Array>;
	clsValores: Record<string, string[]>;
	indice: Map<string, number>;
	escala: Escala;
	anos: [number, number];
}

export function paraNdc(escala: Escala, x: number, y: number): [number, number] {
	return [(x - escala.cx) * escala.s, (y - escala.cy) * escala.s];
}

export function deNdc(escala: Escala, x: number, y: number): [number, number] {
	return [x / escala.s + escala.cx, y / escala.s + escala.cy];
}

/** Mínimo, máximo e os quantis de 0,5% e 99,5% de uma coluna. */
function extensao(v: number[]): { min: number; max: number; baixo: number; alto: number } {
	if (!v.length) return { min: 0, max: 0, baixo: 0, alto: 0 };
	const o = Float64Array.from(v).sort();
	const q = (p: number) => o[Math.round(p * (o.length - 1))];
	return { min: o[0], max: o[o.length - 1], baixo: q(QUANTIL), alto: q(1 - QUANTIL) };
}

/** Escala que leva os dados para NDC: a extensão total, ou a dos quantis quando poucos pontos a esticam. */
export function escalaDe(xs: number[], ys: number[]): Escala {
	const [ex, ey] = [extensao(xs), extensao(ys)];
	const total = Math.max(ex.max - ex.min, ey.max - ey.min);
	const quantis = Math.max(ex.alto - ex.baixo, ey.alto - ey.baixo);
	const ilha = total > ESTICAMENTO_MAXIMO * quantis;
	const [a, b] = ilha ? [ex.baixo, ex.alto] : [ex.min, ex.max];
	const [c, e] = ilha ? [ey.baixo, ey.alto] : [ey.min, ey.max];
	const amplitude = Math.max(b - a, e - c) * (ilha ? FOLGA_QUANTIS : 1) || 1;
	return { cx: (a + b) / 2 || 0, cy: (c + e) / 2 || 0, s: (2 * MARGEM) / amplitude };
}

export function decodificar(d: Documentos): TabelaDocumentos {
	const n = d.n;
	const c = d.colunas;
	const escala = escalaDe(c.x, c.y);
	const x = new Float32Array(n);
	const y = new Float32Array(n);
	const vizinhos = new Int32Array(n * VIZINHOS).fill(-1);
	const indice = new Map<string, number>();
	let [anoMin, anoMax] = [Infinity, -Infinity];
	for (let i = 0; i < n; i += 1) {
		[x[i], y[i]] = paraNdc(escala, c.x[i], c.y[i]);
		c.vizinhos[i].slice(0, VIZINHOS).forEach((j, k) => (vizinhos[i * VIZINHOS + k] = j));
		indice.set(c.id[i], i);
		anoMin = Math.min(anoMin, c.ano[i]);
		anoMax = Math.max(anoMax, c.ano[i]);
	}
	return {
		n,
		ids: c.id,
		titulos: c.titulo,
		dois: c.doi,
		autores: c.autores_curto,
		ano: Uint16Array.from(c.ano),
		revista: Uint16Array.from(c.revista),
		idioma: Uint8Array.from(c.idioma),
		x,
		y,
		topico: Int32Array.from(c.topico),
		atribuicao: Uint8Array.from(c.atribuicao),
		vizinhos,
		revistas: d.dicionarios.revista,
		idiomas: d.dicionarios.idioma,
		cls: Object.fromEntries(Object.entries(c.cls ?? {}).map(([v, col]) => [v, Int16Array.from(col)])),
		clsValores: d.dicionarios.cls ?? {},
		indice,
		escala,
		anos: n ? [anoMin, anoMax] : [0, 0]
	};
}

/** Os vizinhos de um documento (índices na tabela). */
export function vizinhosDe(t: TabelaDocumentos, i: number): number[] {
	return Array.from(t.vizinhos.subarray(i * VIZINHOS, (i + 1) * VIZINHOS)).filter((j) => j >= 0);
}
