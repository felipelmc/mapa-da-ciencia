import { describe, expect, it } from 'vitest';
import { formatarDecimal, formatarPorcentagemDecimal, formatarPp } from './formato';

describe('formato', () => {
	it('decimais, porcentagens e pontos percentuais em pt-BR', () => {
		expect(formatarDecimal(400.7499)).toBe('400,7');
		expect(formatarDecimal(1234.5, 2)).toBe('1.234,50');
		expect(formatarPorcentagemDecimal(0.0421)).toBe('4,2%');
		expect(formatarPp(0.31)).toBe('+0,31 p.p.');
		expect(formatarPp(-1.2)).toBe('−1,20 p.p.');
		expect(formatarPp(0)).toBe('0,00 p.p.');
	});
});
