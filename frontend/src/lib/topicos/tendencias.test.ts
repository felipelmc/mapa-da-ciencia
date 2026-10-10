import { describe, expect, it } from 'vitest';
import { separar, textoFragil, type TendenciaTopico } from './tendencias';

const base = { observado: [], ajuste: null, inclinacao: 0.1, erro_padrao: 0.01, ic95: [0.05, 0.15] as [number, number] };

function t(id: number, direcao: TendenciaTopico['direcao'], pp: number, decisivos: number[] = []): TendenciaTopico {
	return {
		...base,
		id,
		direcao,
		dispersao: 1,
		prop_inicio: 0.01,
		prop_fim: 0.02,
		pp_periodo: pp,
		pp_por_ano: pp / 15,
		anos: [2010, 2025],
		motivo: null,
		fragil: direcao === 'alta' || direcao === 'queda' ? decisivos.length > 0 : null,
		anos_decisivos: decisivos
	};
}

describe('tendências frágeis', () => {
	it('dizem de que anos dependem', () => {
		expect(textoFragil(t(1, 'alta', 2, [2011]), 16)).toBe('a marcação some sem 2011');
		expect(textoFragil(t(1, 'alta', 2, [2010, 2012]), 16)).toBe('a marcação some sem 2010 ou sem 2012');
		expect(textoFragil(t(1, 'alta', 2, [2010, 2012, 2014]), 16)).toBe('a marcação some sem 2010, sem 2012 ou sem 2014');
		expect(textoFragil(t(1, 'alta', 2, [2010, 2011, 2012, 2014]), 16)).toBe('a marcação some sem qualquer um de 4 dos 16 anos');
		expect(textoFragil(t(1, 'alta', 2), 16)).toBeNull();
		expect(textoFragil(t(1, 'estavel', 0), 16)).toBeNull();
	});

	it('são contadas entre as marcadas', () => {
		const g = separar([t(1, 'alta', 2, [2011]), t(2, 'alta', 3), t(3, 'queda', -1, [2025]), t(4, 'estavel', 0)]);
		expect(g.frageis).toBe(2);
		expect(g.alta.map((x) => x.id)).toEqual([2, 1]);
	});
});
