/**
 * O `documentos.json` colunar em arrays tipados, prontos para o mapa.
 *
 * - As coordenadas do UMAP viram NDC (de -1 a 1), como o regl-scatterplot exige, preservando a proporção
 *   (a mesma escala nos dois eixos) e com uma pequena margem. `paraNdc`/`deNdc` convertem nos dois sentidos:
 *   o laço fica na URL em coordenadas dos dados, que não dependem do tamanho da tela.
 * - Os vizinhos ficam num só array, 5 por documento (−1 onde faltar).
 */
import type { Documentos } from '$lib/contrato/tipos';

export const VIZINHOS = 5;
const MARGEM = 0.94; // fração de [-1, 1] ocupada pelos pontos

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

export function decodificar(d: Documentos): TabelaDocumentos {
	const n = d.n;
	const c = d.colunas;
	let [minX, maxX, minY, maxY] = [Infinity, -Infinity, Infinity, -Infinity];
	for (let i = 0; i < n; i += 1) {
		minX = Math.min(minX, c.x[i]);
		maxX = Math.max(maxX, c.x[i]);
		minY = Math.min(minY, c.y[i]);
		maxY = Math.max(maxY, c.y[i]);
	}
	const amplitude = Math.max(maxX - minX, maxY - minY) || 1;
	const escala: Escala = { cx: (minX + maxX) / 2 || 0, cy: (minY + maxY) / 2 || 0, s: (2 * MARGEM) / amplitude };
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
		indice,
		escala,
		anos: n ? [anoMin, anoMax] : [0, 0]
	};
}

/** Os vizinhos de um documento (índices na tabela). */
export function vizinhosDe(t: TabelaDocumentos, i: number): number[] {
	return Array.from(t.vizinhos.subarray(i * VIZINHOS, (i + 1) * VIZINHOS)).filter((j) => j >= 0);
}
