import { describe, expect, it } from 'vitest';
import { rotularFaixas } from './faixas';
import { empilhar, ordemDentroFora } from './fluxo';

const matriz = [
	[1, 2, 3, 4, 5],
	[10, 9, 8, 7, 6],
	[3, 3, 3, 3, 3],
	[0, 0, 5, 0, 0]
];
const ids = [11, 22, 33, 44];

describe('empilhar', () => {
	it('proporção: cada ano soma 1, e um ano vazio fica vazio', () => {
		const { series, dominio } = empilhar([...matriz, [0, 0, 0, 0, 0]], [...ids, -1], 'proporcao');
		for (let j = 0; j < 5; j += 1) {
			const topo = Math.max(...series.map((s) => s.y1[j]));
			expect(topo).toBeCloseTo(1);
		}
		expect(dominio).toEqual([0, 1]);
		const vazio = empilhar([[0, 0], [0, 0]], [1, 2], 'proporcao');
		expect(Array.from(vazio.series[1].y1)).toEqual([0, 0]);
	});

	it('absoluto: o topo é o total do ano; fluxo preserva as espessuras', () => {
		const abs = empilhar(matriz, ids, 'absoluto');
		const totais = [14, 14, 19, 14, 14];
		for (let j = 0; j < 5; j += 1) expect(Math.max(...abs.series.map((s) => s.y1[j]))).toBe(totais[j]);
		const fluxo = empilhar(matriz, ids, 'fluxo');
		fluxo.series.forEach((s, k) => {
			for (let j = 0; j < 5; j += 1) expect(s.y1[j] - s.y0[j]).toBeCloseTo(matriz[ids.indexOf(s.id)][j]);
			expect(s.id).toBe(abs.series[k].id);
		});
	});

	it('a ordem de dentro para fora é fixa entre os modos, com "sem tópico" no topo', () => {
		const ordem = ordemDentroFora(matriz, [3]);
		expect(ordem[ordem.length - 1]).toBe(3);
		expect(new Set(ordem)).toEqual(new Set([0, 1, 2, 3]));
		const a = empilhar(matriz, ids, 'fluxo', ordem).series.map((s) => s.id);
		const b = empilhar(matriz, ids, 'proporcao', ordem).series.map((s) => s.id);
		expect(a).toEqual(b);
		expect(a[a.length - 1]).toBe(44);
	});
});

describe('rotularFaixas', () => {
	const x = (j: number) => j * 100;
	const y = (v: number) => 300 - v * 20;
	const medir = (texto: string) => texto.length * 7;

	it('rótulo só onde cabe, dentro da faixa', () => {
		const fina = [...matriz.slice(0, 3), [0, 0, 0.5, 0, 0]]; // 10 px no máximo: não cabe um texto de 12 px
		const { series } = empilhar(fina, ids, 'absoluto');
		const textos = new Map(ids.map((id) => [id, `tópico ${id}`]));
		const rotulos = rotularFaixas(series, textos, x, y, medir);
		const porId = new Map(rotulos.map((r) => [r.id, r]));
		expect(porId.has(22)).toBe(true); // a faixa grossa ganha rótulo
		expect(porId.has(44)).toBe(false); // a fina demais, não
		for (const r of rotulos) {
			const s = series.find((z) => z.id === r.id)!;
			const coluna = r.x / 100;
			const i = Math.round(coluna);
			expect(r.y).toBeLessThan(y(s.y0[i]) + 1e-6);
			expect(r.y).toBeGreaterThan(y(s.y1[i]) - 1e-6);
		}
	});
});
