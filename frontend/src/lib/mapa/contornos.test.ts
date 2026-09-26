import { describe, expect, it } from 'vitest';
import type { TabelaDocumentos } from '$lib/dados/documentos';
import { dentro } from '$lib/graficos/geometria';
import { escalaLinear } from '$lib/graficos/escala';
import { calcularContornos, centroDePeso } from './contornos';

function tabela(grupos: { cx: number; cy: number; n: number; topico: number; atribuicao?: number }[]): TabelaDocumentos {
	const xs: number[] = [];
	const ys: number[] = [];
	const topicos: number[] = [];
	const atribuicoes: number[] = [];
	let s = 7;
	const aleatorio = () => (s = (s * 1664525 + 1013904223) % 2 ** 32) / 2 ** 32 - 0.5;
	for (const g of grupos) {
		for (let i = 0; i < g.n; i += 1) {
			xs.push(g.cx + aleatorio() * 0.2);
			ys.push(g.cy + aleatorio() * 0.2);
			topicos.push(g.topico);
			atribuicoes.push(g.atribuicao ?? 0);
		}
	}
	return {
		n: xs.length,
		x: Float32Array.from(xs),
		y: Float32Array.from(ys),
		topico: Int32Array.from(topicos),
		atribuicao: Uint8Array.from(atribuicoes)
	} as TabelaDocumentos;
}

describe('contornos', () => {
	it('envolvem o núcleo de cada tópico e deixam de fora os outros', () => {
		const t = tabela([
			{ cx: -0.5, cy: -0.5, n: 80, topico: 3 },
			{ cx: 0.5, cy: 0.4, n: 60, topico: 9 },
			{ cx: 0.5, cy: 0.4, n: 40, topico: 12, atribuicao: 1 } // só reatribuídos: sem contorno
		]);
		const c = calcularContornos(t, [3, 9, 12]);
		expect([...c.keys()]).toEqual([3, 9]);
		const anel3 = c.get(3)![0];
		expect(dentro(-0.5, -0.5, anel3)).toBe(true);
		expect(dentro(0.5, 0.4, anel3)).toBe(false);
		expect(c.get(9)!.some((anel) => dentro(0.5, 0.4, anel))).toBe(true);
	});

	it('centro pesado pelo tamanho', () => {
		expect(centroDePeso([{ x: 0, y: 0, peso: 3 }, { x: 1, y: 1, peso: 1 }])).toEqual([0.25, 0.25]);
	});
});

describe('escala linear', () => {
	it('converte e aceita domínio e faixa novos, como o regl-scatterplot faz', () => {
		const e = escalaLinear();
		e.range([0, 800]);
		expect(e(-1)).toBe(0);
		expect(e(1)).toBe(800);
		e.domain([0, 0.5]);
		expect(e(0.25)).toBe(400);
		expect(e.domain()).toEqual([0, 0.5]);
	});
});
