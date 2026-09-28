/**
 * As contas da interação com o grafo (`Grafo.svelte`), sem DOM: a vizinhança de cada nó, o enquadramento de um
 * grupo de nós na tela e a escolha dos rótulos que cabem sem se cobrir.
 */

/** As arestas por nó, em forma compacta: os vizinhos de `i` são `vizinho[inicio[i]..inicio[i + 1]]`. */
export interface Adjacencia {
	inicio: Int32Array;
	vizinho: Int32Array;
}

export function adjacencia(n: number, arestas: { n: number; a: Int32Array; b: Int32Array }): Adjacencia {
	const grau = new Int32Array(n + 1);
	for (let k = 0; k < arestas.n; k += 1) {
		grau[arestas.a[k] + 1] += 1;
		grau[arestas.b[k] + 1] += 1;
	}
	const inicio = new Int32Array(n + 1);
	for (let i = 0; i < n; i += 1) inicio[i + 1] = inicio[i] + grau[i + 1];
	const vizinho = new Int32Array(inicio[n]);
	const cursor = inicio.slice(0, n);
	for (let k = 0; k < arestas.n; k += 1) {
		const [a, b] = [arestas.a[k], arestas.b[k]];
		vizinho[cursor[a]++] = b;
		vizinho[cursor[b]++] = a;
	}
	return { inicio, vizinho };
}

/** O nó e os vizinhos dele (sem repetição). */
export function vizinhanca(adj: Adjacencia, i: number): Set<number> {
	const saida = new Set([i]);
	for (let k = adj.inicio[i]; k < adj.inicio[i + 1]; k += 1) saida.add(adj.vizinho[k]);
	return saida;
}

/** Zoom e deslocamento da tela: tela = base × k + (dx, dy). */
export interface Vista {
	k: number;
	dx: number;
	dy: number;
}

/**
 * A vista que enquadra os nós `indices` (posições de base em pixels, `bx`/`by`) na tela `largura` × `altura`, com
 * `margem` em volta e o zoom entre `kMin` e `kMax`. Sem nós válidos, `null`.
 */
export function enquadrar(
	indices: Iterable<number>,
	bx: ArrayLike<number>,
	by: ArrayLike<number>,
	largura: number,
	altura: number,
	{ margem = 48, kMin = 0.5, kMax = 40 }: { margem?: number; kMin?: number; kMax?: number } = {}
): Vista | null {
	let [x0, x1, y0, y1] = [Infinity, -Infinity, Infinity, -Infinity];
	for (const i of indices) {
		if (!Number.isFinite(bx[i]) || !Number.isFinite(by[i])) continue;
		x0 = Math.min(x0, bx[i]);
		x1 = Math.max(x1, bx[i]);
		y0 = Math.min(y0, by[i]);
		y1 = Math.max(y1, by[i]);
	}
	if (!Number.isFinite(x0) || largura <= 0 || altura <= 0) return null;
	const util = [Math.max(largura - 2 * margem, 1), Math.max(altura - 2 * margem, 1)];
	// um nó só (ou uma linha reta) não tem largura: o zoom fica no máximo que ainda mostra os vizinhos por perto
	const k = Math.min(kMax, Math.max(kMin, Math.min(util[0] / (x1 - x0 || util[0] / 4), util[1] / (y1 - y0 || util[1] / 4))));
	const [cx, cy] = [(x0 + x1) / 2, (y0 + y1) / 2];
	return { k, dx: largura / 2 - cx * k, dy: altura / 2 - cy * k };
}

/** Um rótulo candidato, já na tela (px): o centro do texto e a prioridade (a maior entra primeiro). */
export interface Candidato {
	id: string;
	texto: string;
	px: number;
	py: number;
	prioridade: number;
}

export interface RotuloPosto extends Candidato {
	caixa: { x0: number; x1: number; y0: number; y1: number };
}

/**
 * Os rótulos que cabem, pela ordem de prioridade: o que passaria da borda é empurrado para dentro; o que cobriria um
 * já posto (ou está fora da tela) fica de fora. `larguraDe` estima a largura do texto em px; `altura` é a do texto.
 * `ocupadas` são áreas já tomadas (outros rótulos).
 */
export function semColisao(
	candidatos: Candidato[],
	largura: number,
	altura: number,
	{
		larguraDe = (t: string) => t.length * 6.8 + 8,
		alturaTexto = 16,
		ocupadas = [] as RotuloPosto['caixa'][],
		maximo = Infinity
	}: { larguraDe?: (t: string) => number; alturaTexto?: number; ocupadas?: RotuloPosto['caixa'][]; maximo?: number } = {}
): RotuloPosto[] {
	const postos: RotuloPosto['caixa'][] = [...ocupadas];
	const saida: RotuloPosto[] = [];
	const ordem = [...candidatos].sort((a, b) => b.prioridade - a.prioridade || a.id.localeCompare(b.id));
	for (const c of ordem) {
		if (saida.length >= maximo) break;
		if (c.px < 0 || c.px > largura || c.py < 0 || c.py > altura) continue;
		const meia = Math.min(larguraDe(c.texto) / 2, largura / 2);
		const px = Math.min(Math.max(c.px, meia), largura - meia);
		const py = Math.min(Math.max(c.py, alturaTexto * 0.7), altura - alturaTexto * 0.3);
		const caixa = { x0: px - meia, x1: px + meia, y0: py - alturaTexto * 0.7, y1: py + alturaTexto * 0.3 };
		if (postos.some((o) => caixa.x0 < o.x1 && o.x0 < caixa.x1 && caixa.y0 < o.y1 && o.y0 < caixa.y1)) continue;
		postos.push(caixa);
		saida.push({ ...c, px, py, caixa });
	}
	return saida;
}

/**
 * Quantos nomes de nós mostrar com o zoom `k`: nenhum na vista inteira (seria uma sopa de letras), e mais à medida que
 * o zoom separa os nós.
 */
export function nomesNoZoom(k: number): number {
	if (k < 1.8) return 0;
	return Math.min(80, Math.round(10 * (k - 1)));
}

/** A posição do desenho (as coordenadas do Python) de um ponto da base em pixels: o inverso de `baseX`/`baseY`. */
export function paraDesenho(
	bpx: number,
	bpy: number,
	ajuste: { s: number; cx: number; cy: number },
	largura: number,
	altura: number
): [number, number] {
	return [ajuste.cx + (bpx - largura / 2) / ajuste.s, ajuste.cy - (bpy - altura / 2) / ajuste.s];
}
