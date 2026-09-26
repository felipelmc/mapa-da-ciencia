/**
 * Contornos dos tópicos no mapa: a linha que envolve a região mais densa do núcleo de cada tópico.
 *
 * Para cada tópico, uma densidade de núcleo (gaussiana) numa grade só em volta dele, com a banda tirada da
 * distância típica entre vizinhos do próprio tópico: tópicos compactos ganham contornos justos, e tópicos
 * espalhados, contornos mais soltos. O nível do contorno é o que deixa dentro `cobertura` dos documentos do
 * núcleo (80%, por padrão), e não uma fração do pico: assim os contornos têm o mesmo significado em todos os
 * tópicos. Só o núcleo conta (os reatribuídos ficam de fora, ADR 0007), e o cálculo acontece uma vez, ao abrir
 * o mapa: filtros e a linha do tempo não o refazem.
 */
import { contours } from 'd3-contour';
import type { TabelaDocumentos } from '$lib/dados/documentos';

export type Anel = [number, number][];

const LADO_MAXIMO = 128; // células por lado, no máximo, na grade de cada tópico
const K_BANDA = 5; // a banda sai da distância ao 5º vizinho mais próximo dentro do tópico
const AMOSTRA_BANDA = 200; // pontos usados para estimar essa distância em tópicos grandes
const BANDA_MINIMA = 0.006; // em NDC (o mapa vai de −1 a 1)
const BANDA_MAXIMA = 0.08;

/** Mediana, sem alterar a lista. */
function mediana(valores: number[]): number {
	const v = [...valores].sort((a, b) => a - b);
	const m = v.length >> 1;
	return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}

/** Banda da densidade: 1,5 × a distância mediana ao k-ésimo vizinho dentro do tópico, entre limites. */
export function bandaDe(pontos: [number, number][]): number {
	const k = Math.min(K_BANDA, pontos.length - 1);
	if (k < 1) return BANDA_MAXIMA;
	const passo = Math.max(1, Math.floor(pontos.length / AMOSTRA_BANDA));
	const distancias: number[] = [];
	for (let i = 0; i < pontos.length; i += passo) {
		const [xi, yi] = pontos[i];
		const d: number[] = [];
		for (let j = 0; j < pontos.length; j += 1) {
			if (j !== i) d.push(Math.hypot(pontos[j][0] - xi, pontos[j][1] - yi));
		}
		d.sort((a, b) => a - b);
		distancias.push(d[k - 1]);
	}
	return Math.min(BANDA_MAXIMA, Math.max(BANDA_MINIMA, 1.5 * mediana(distancias)));
}

/** Anéis (em NDC) que envolvem `cobertura` dos pontos, pela densidade numa grade local. */
export function contornoDe(pontos: [number, number][], cobertura = 0.8): Anel[] {
	const banda = bandaDe(pontos);
	let [x0, x1, y0, y1] = [Infinity, -Infinity, Infinity, -Infinity];
	for (const [x, y] of pontos) {
		[x0, x1, y0, y1] = [Math.min(x0, x), Math.max(x1, x), Math.min(y0, y), Math.max(y1, y)];
	}
	const margem = 3 * banda;
	[x0, x1, y0, y1] = [x0 - margem, x1 + margem, y0 - margem, y1 + margem];
	const celula = Math.max(banda / 2, Math.max(x1 - x0, y1 - y0) / LADO_MAXIMO);
	const largura = Math.ceil((x1 - x0) / celula);
	const altura = Math.ceil((y1 - y0) / celula);
	const grade = new Float64Array(largura * altura);
	const raio = Math.ceil(margem / celula);
	const fator = (celula * celula) / (2 * banda * banda);
	const celulaDe = (x: number, y: number): [number, number] => [(x - x0) / celula, (y - y0) / celula];

	// a célula (i, j) cobre [i, i+1] × [j, j+1] na grade, como no d3-contour; o centro fica em i + 0,5
	for (const [x, y] of pontos) {
		const [gx, gy] = celulaDe(x, y);
		const [ci, cj] = [Math.floor(gx), Math.floor(gy)];
		for (let j = Math.max(0, cj - raio); j <= Math.min(altura - 1, cj + raio); j += 1) {
			const dy = j + 0.5 - gy;
			for (let i = Math.max(0, ci - raio); i <= Math.min(largura - 1, ci + raio); i += 1) {
				const dx = i + 0.5 - gx;
				grade[i + j * largura] += Math.exp(-(dx * dx + dy * dy) * fator);
			}
		}
	}
	const densidades = pontos
		.map(([x, y]) => {
			const [gx, gy] = celulaDe(x, y);
			return grade[Math.min(largura - 1, Math.floor(gx)) + Math.min(altura - 1, Math.floor(gy)) * largura];
		})
		.sort((a, b) => a - b);
	const nivel = densidades[Math.floor((1 - cobertura) * (densidades.length - 1))];
	const [multipoligono] = contours().size([largura, altura]).thresholds([nivel])(Array.from(grade));
	return multipoligono.coordinates
		.map((poligono) => poligono[0].map(([gx, gy]): [number, number] => [x0 + gx * celula, y0 + gy * celula]))
		.filter((anel) => anel.length >= 4);
}

export function calcularContornos(
	t: TabelaDocumentos,
	ids: number[],
	{ cobertura = 0.8, minimoPontos = 5 } = {}
): Map<number, Anel[]> {
	const porTopico = new Map<number, [number, number][]>();
	for (let i = 0; i < t.n; i += 1) {
		if (t.atribuicao[i] !== 0 || t.topico[i] < 0) continue;
		const lista = porTopico.get(t.topico[i]) ?? [];
		lista.push([t.x[i], t.y[i]]);
		porTopico.set(t.topico[i], lista);
	}
	const saida = new Map<number, Anel[]>();
	for (const id of ids) {
		const pontos = porTopico.get(id);
		if (!pontos || pontos.length < minimoPontos) continue;
		const aneis = contornoDe(pontos, cobertura);
		if (aneis.length) saida.set(id, aneis);
	}
	return saida;
}

/** O centro (NDC) de cada grupo de tópicos, pesado pelo tamanho, para o rótulo do macrotema. */
export function centroDePeso(itens: { x: number; y: number; peso: number }[]): [number, number] {
	const total = itens.reduce((s, i) => s + i.peso, 0) || 1;
	return [itens.reduce((s, i) => s + i.x * i.peso, 0) / total, itens.reduce((s, i) => s + i.y * i.peso, 0) / total];
}
