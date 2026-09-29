import { describe, expect, it } from 'vitest';
import { formatarDecimal, formatarDuracao, formatarPorcentagemDecimal, formatarPp, nomeDaFonte, nomeDaLicenca } from './formato';

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

describe('formatarDuracao', () => {
	it('escolhe a unidade', () => {
		expect(formatarDuracao(12.4)).toBe('12 s');
		expect(formatarDuracao(600)).toBe('10 min');
		expect(formatarDuracao(14080)).toBe('3 h 55 min');
		expect(formatarDuracao(7200)).toBe('2 h');
	});

	it('nomes legíveis das fontes do recorte, e não os códigos internos', () => {
		expect(['scielo:scl', 'scielo:xyz', 'openalex'].map(nomeDaFonte)).toEqual(['SciELO Brasil', 'SciELO (coleção xyz)', 'OpenAlex']);
		expect(nomeDaFonte('exemplo')).toBe('exemplo');
	});
});

describe('nomeDaLicenca', () => {
	it('dá nome às licenças do OpenAlex, e não o código', () => {
		expect(['cc-by', 'cc-by-nc-sa', 'cc0', 'other-oa', 'publisher-specific-oa'].map(nomeDaLicenca)).toEqual([
			'CC BY',
			'CC BY-NC-SA',
			'CC0',
			'acesso aberto, sem licença Creative Commons',
			'licença própria da editora, sem Creative Commons'
		]);
		expect(nomeDaLicenca(null)).toBe('desconhecida');
		expect(nomeDaLicenca('mit')).toBe('mit');
	});
});
