import { describe, expect, it } from 'vitest';
import { adjacencia, enquadrar, nomesNoZoom, paraDesenho, semColisao, vizinhanca } from './interacao';

const arestas = (pares: [number, number][]) => ({
	n: pares.length,
	a: Int32Array.from(pares, (p) => p[0]),
	b: Int32Array.from(pares, (p) => p[1])
});

describe('vizinhança', () => {
	it('lista os vizinhos de cada nó, nos dois sentidos, e o nó sem aresta fica sozinho', () => {
		const adj = adjacencia(5, arestas([[0, 1], [1, 2], [0, 2], [3, 1]]));
		expect([...vizinhanca(adj, 1)].sort()).toEqual([0, 1, 2, 3]);
		expect([...vizinhanca(adj, 3)].sort()).toEqual([1, 3]);
		expect([...vizinhanca(adj, 4)]).toEqual([4]);
	});
});

describe('enquadrar', () => {
	it('põe a caixa dos nós no centro da tela, com a margem, na mesma escala nos dois eixos', () => {
		const bx = [100, 300, 200, NaN];
		const by = [50, 50, 150, 0];
		const v = enquadrar([0, 1, 2, 3], bx, by, 800, 600, { margem: 50 })!;
		// a caixa tem 200 × 100: cabe em 700 × 500 com k = 3,5 (a largura manda)
		expect(v.k).toBeCloseTo(3.5);
		expect(200 * v.k + v.dx).toBeCloseTo(400); // o centro da caixa vai para o centro da tela
		expect(100 * v.k + v.dy).toBeCloseTo(300);
	});

	it('respeita os limites do zoom, e um nó só não vira zoom infinito', () => {
		expect(enquadrar([0], [10], [10], 800, 600, { kMax: 8 })!.k).toBeLessThanOrEqual(8);
		expect(enquadrar([0, 1], [0, 1e6], [0, 0], 800, 600, { kMin: 0.5 })!.k).toBe(0.5);
		expect(enquadrar([0], [NaN], [NaN], 800, 600)).toBeNull();
	});
});

describe('rótulos sem colisão', () => {
	it('entram por prioridade, sem se cobrir, empurrados para dentro da tela', () => {
		const postos = semColisao(
			[
				{ id: 'a', texto: 'Ciência política', px: 100, py: 100, prioridade: 1 },
				{ id: 'b', texto: 'Sociologia', px: 110, py: 104, prioridade: 5 },
				{ id: 'c', texto: 'Borda', px: 2, py: 300, prioridade: 2 },
				{ id: 'd', texto: 'Fora', px: -20, py: 300, prioridade: 9 }
			],
			400,
			400
		);
		expect(postos.map((p) => p.id)).toEqual(['b', 'c']);
		const c = postos.find((p) => p.id === 'c')!;
		expect(c.caixa.x0).toBeGreaterThanOrEqual(0);
	});

	it('respeita as áreas já ocupadas e o máximo', () => {
		const candidatos = [0, 1, 2, 3].map((k) => ({ id: `n${k}`, texto: 'x', px: 50 + 100 * k, py: 50, prioridade: k }));
		expect(semColisao(candidatos, 500, 100, { maximo: 2 }).map((p) => p.id)).toEqual(['n3', 'n2']);
		const ocupadas = [{ x0: 0, x1: 500, y0: 0, y1: 100 }];
		expect(semColisao(candidatos, 500, 100, { ocupadas })).toEqual([]);
	});
});

describe('nomes pelo zoom', () => {
	it('nenhum na vista inteira, e mais à medida que o zoom aumenta, até um teto', () => {
		expect(nomesNoZoom(1)).toBe(0);
		expect(nomesNoZoom(1.7)).toBe(0);
		expect(nomesNoZoom(3)).toBeGreaterThan(nomesNoZoom(2));
		expect(nomesNoZoom(40)).toBe(80);
	});
});

describe('paraDesenho', () => {
	it('é o inverso da base em pixels (y do desenho para cima, da tela para baixo)', () => {
		const ajuste = { s: 100, cx: 0.2, cy: -0.1 };
		const [largura, altura] = [800, 600];
		const [x, y] = [0.5, 0.3];
		const bpx = largura / 2 + (x - ajuste.cx) * ajuste.s;
		const bpy = altura / 2 - (y - ajuste.cy) * ajuste.s;
		const [vx, vy] = paraDesenho(bpx, bpy, ajuste, largura, altura);
		expect(vx).toBeCloseTo(x);
		expect(vy).toBeCloseTo(y);
	});
});
