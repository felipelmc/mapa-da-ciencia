import { describe, expect, it } from 'vitest';
import { geoArea } from 'd3-geo';
import { caminhos, malhaMundo, malhaUF, projecaoBrasil, projecaoMundo } from './malhas';

const SIGLAS = 'AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO'.split(' ');

describe('malhas', () => {
	it('as 27 UFs do IBGE, com a sigla', async () => {
		const ufs = await malhaUF();
		expect(ufs.map((u) => u.properties.sigla).sort()).toEqual(SIGLAS);
		// o Amazonas é a maior UF, e o DF, a menor
		const area = new Map(ufs.map((u) => [u.properties.sigla, geoArea(u)]));
		const ordem = [...area.entries()].sort((a, b) => b[1] - a[1]).map(([s]) => s);
		expect(ordem[0]).toBe('AM');
		expect(ordem.at(-1)).toBe('DF');
	});

	it('os países, com o ISO-2 único', async () => {
		const paises = await malhaMundo();
		const iso = paises.map((p) => p.properties.iso).filter((x): x is string => x !== null);
		expect(new Set(iso).size).toBe(iso.length);
		expect(iso).toEqual(expect.arrayContaining(['BR', 'AR', 'US', 'PT', 'XK']));
	});

	it('as projeções cabem na área de desenho', async () => {
		const ufs = await malhaUF();
		const p = projecaoBrasil(400, 400, ufs);
		const [x, y] = p([-47.9, -15.8])!; // Brasília
		expect(x).toBeGreaterThan(150);
		expect(x).toBeLessThan(350);
		expect(y).toBeGreaterThan(100);
		expect(y).toBeLessThan(300);
		expect(caminhos(ufs, p).every((d) => d.startsWith('M'))).toBe(true);
		const paises = await malhaMundo();
		const m = projecaoMundo(800, 400, paises);
		const [bx, by] = m([-47.9, -15.8])!;
		expect(bx).toBeGreaterThan(0);
		expect(bx).toBeLessThan(400);
		expect(by).toBeGreaterThan(200);
	});
});
