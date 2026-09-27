import { describe, expect, it } from 'vitest';
import type { Evidencia } from '$lib/contrato/tipos';
import { segmentar } from './ResumoComEvidencias.svelte';

const ev = (inicio: number | null, fim: number | null, extra: Partial<Evidencia> = {}): Evidencia => ({
	valor: 'x',
	evidencia: '',
	status: 'literal',
	inicio,
	fim,
	campo: 'resumo',
	...extra
});

describe('segmentar', () => {
	const resumo = 'Um estudo quantitativo sobre eleições no Brasil.';
	it('parte nos limites e junta as variáveis que se sobrepõem', () => {
		const s = segmentar(resumo, { a: ev(3, 22), b: ev(10, 32), c: ev(null, null, { status: 'dispensada' }) });
		expect(s.map((x) => x.texto).join('')).toBe(resumo);
		expect(s.filter((x) => x.variaveis.length).map((x) => [x.texto, x.variaveis])).toEqual([
			['estudo ', ['a']],
			['quantitativo', ['a', 'b']],
			[' sobre ele', ['b']]
		]);
	});

	it('ignora as do título, as ausentes e posições fora do texto', () => {
		const s = segmentar(resumo, {
			t: ev(0, 5, { campo: 'titulo' }),
			z: ev(0, 5, { status: 'ausente' }),
			f: ev(10, 999)
		});
		expect(s).toEqual([{ texto: resumo, variaveis: [] }]);
	});
});
