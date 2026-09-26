/**
 * Geometria do laço: simplificação de polígonos (Ramer–Douglas–Peucker) e ponto-no-polígono.
 *
 * A seleção do laço é sempre recalculada aqui, sobre o polígono simplificado que vai para a URL, e não
 * tomada do regl-scatterplot: assim um link abre com exatamente os mesmos documentos selecionados.
 */

export type Ponto = [number, number];

function distanciaAoSegmento([px, py]: Ponto, [ax, ay]: Ponto, [bx, by]: Ponto): number {
	const dx = bx - ax;
	const dy = by - ay;
	const comprimento = dx * dx + dy * dy;
	const t = comprimento ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / comprimento)) : 0;
	return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

function rdp(pontos: Ponto[], tolerancia: number): Ponto[] {
	if (pontos.length < 3) return pontos;
	let [maior, indice] = [0, 0];
	for (let i = 1; i < pontos.length - 1; i += 1) {
		const d = distanciaAoSegmento(pontos[i], pontos[0], pontos[pontos.length - 1]);
		if (d > maior) [maior, indice] = [d, i];
	}
	if (maior <= tolerancia) return [pontos[0], pontos[pontos.length - 1]];
	return [...rdp(pontos.slice(0, indice + 1), tolerancia).slice(0, -1), ...rdp(pontos.slice(indice), tolerancia)];
}

/** Simplifica o contorno até ter no máximo `maximo` vértices, aumentando a tolerância aos poucos. */
export function simplificar(pontos: Ponto[], maximo = 30): Ponto[] {
	if (pontos.length <= maximo) return pontos;
	let largura = 0;
	for (const [x, y] of pontos) largura = Math.max(largura, Math.abs(x), Math.abs(y));
	let tolerancia = (largura || 1) / 1000;
	let saida = rdp(pontos, tolerancia);
	while (saida.length > maximo) {
		tolerancia *= 1.5;
		saida = rdp(pontos, tolerancia);
	}
	return saida;
}

/** Regra par-ímpar: o ponto está dentro do polígono (fechado implicitamente)? */
export function dentro(x: number, y: number, poligono: Ponto[]): boolean {
	let dentroDele = false;
	for (let i = 0, j = poligono.length - 1; i < poligono.length; j = i, i += 1) {
		const [xi, yi] = poligono[i];
		const [xj, yj] = poligono[j];
		if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) dentroDele = !dentroDele;
	}
	return dentroDele;
}

/** Índices dos pontos dentro do polígono. */
export function selecionar(xs: ArrayLike<number>, ys: ArrayLike<number>, poligono: Ponto[]): number[] {
	if (poligono.length < 3) return [];
	let [minX, maxX, minY, maxY] = [Infinity, -Infinity, Infinity, -Infinity];
	for (const [x, y] of poligono) {
		minX = Math.min(minX, x);
		maxX = Math.max(maxX, x);
		minY = Math.min(minY, y);
		maxY = Math.max(maxY, y);
	}
	const saida: number[] = [];
	for (let i = 0; i < xs.length; i += 1) {
		const [x, y] = [xs[i], ys[i]];
		if (x >= minX && x <= maxX && y >= minY && y <= maxY && dentro(x, y, poligono)) saida.push(i);
	}
	return saida;
}
