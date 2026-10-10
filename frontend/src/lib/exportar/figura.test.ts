import { describe, expect, it } from 'vitest';
import { caberNaLargura, fonteDoCanvas, larguraPx, legendaEmSvg, nomeDeArquivo, numeroCru, paraCsv, PRESETS, type ItemLegenda } from './figura';

describe('exportar', () => {
	it('CSV com BOM, aspas quando precisa e CRLF', () => {
		const csv = paraCsv(['Nome', 'n'], [['Dados, Rio', 3], ['Diz "oi"', 4]]);
		expect(csv).toBe('﻿Nome,n\r\n"Dados, Rio",3\r\n"Diz ""oi""",4\r\n');
	});

	it('CSV com números crus: ponto decimal, sem separador de milhar, vazio onde não há valor', () => {
		const csv = paraCsv(['UF', 'Peso', 'Documentos', 'IC'], [['São Paulo', numeroCru(929.5912000000001), 1095, null]]);
		expect(csv).toBe('﻿UF,Peso,Documentos,IC\r\nSão Paulo,929.5912,1095,\r\n');
		expect(numeroCru(-1.5512345, 3)).toBe(-1.551);
	});

	it('larguras dos presets em pixels', () => {
		const px = Object.fromEntries(PRESETS.map((p) => [p.id, larguraPx(p)]));
		expect(px).toEqual({ 'artigo-1': 1004, 'artigo-2': 2055, 'artigo-2-600': 4110, slide: 1920, telao: 3840 });
		expect(PRESETS.filter((p) => p.id.startsWith('artigo')).every((p) => p.tema === 'prancha')).toBe(true);
	});

	it('nome de arquivo sem acentos nem espaços', () => {
		expect(nomeDeArquivo('Por ano')).toBe('por-ano');
		expect(nomeDeArquivo('Concordância × referência')).toBe('concordancia-referencia');
		expect(nomeDeArquivo('?!')).toBe('figura');
	});
});

describe('legenda em SVG', () => {
	// uma medida fixa (cada caractere vale 0,6 do tamanho), para o teste não depender das fontes
	const medir = (texto: string, tamanho: number) => texto.length * tamanho * 0.6;
	const opcoes = { x: 10, y: 100, largura: 300, k: 1, fonte: 'Inter', cor: '#333', medir };
	const item = (texto: string, forma?: 'circulo' | 'quadrado' | 'linha' | 'hachura'): ItemLegenda => ({
		texto,
		titulo: false,
		amostra: forma ? { forma, cor: '#c00', opacidade: 1, largura: 2, fundo: '#fff' } : null
	});
	const textos = (svg: string) => [...svg.matchAll(/<text x="([\d.]+)" y="([\d.]+)"[^>]*>([^<]*)<\/text>/g)];

	it('nada passa da largura, e um texto longo quebra em mais de uma linha', () => {
		const longo = 'Federalismo, capacidades estatais e implementação de políticas sociais nos municípios brasileiros';
		const { svg } = legendaEmSvg([item('Um', 'circulo'), item(longo, 'quadrado'), item('Dois', 'linha')], opcoes);
		for (const [, x, , texto] of textos(svg)) expect(Number(x) + medir(texto, 11)).toBeLessThanOrEqual(10 + 300 + 1e-9);
		const doLongo = textos(svg).filter(([, , , t]) => longo.includes(t) && t !== 'Um' && t !== 'Dois');
		expect(doLongo.length).toBeGreaterThanOrEqual(2);
		expect(new Set(doLongo.map(([, , y]) => y)).size).toBe(doLongo.length); // uma linha embaixo da outra
	});

	it('o título abre uma linha; as formas, a hachura nos defs e o texto escapado', () => {
		const titulo: ItemLegenda = { texto: 'Peso fracionário:', titulo: true, amostra: null };
		const r = legendaEmSvg([item('A & B', 'quadrado'), titulo, item('fora da escala', 'hachura')], opcoes);
		const [primeiro, segundo] = textos(r.svg);
		expect(Number(segundo[2])).toBeGreaterThan(Number(primeiro[2]));
		expect(r.svg).toContain('A &amp; B');
		expect(r.svg).toMatch(/<rect [^>]*fill="#c00"/);
		expect(r.defs).toMatch(/<pattern id="leg-hachura-2"/);
		expect(r.svg).toContain('fill="url(#leg-hachura-2)"');
		expect(r.altura).toBeGreaterThan(0);
	});

	it('sem itens, nada', () => {
		expect(legendaEmSvg([], opcoes)).toEqual({ svg: '', defs: '', altura: 0 });
	});
});

describe('caberNaLargura', () => {
	const medir = (t: string) => t.length * 10; // 10 px por caractere
	it('deixa o texto que cabe e corta o que não cabe, mantendo o número entre parênteses', () => {
		expect(caberNaLargura('Dados (412)', 200, medir)).toBe('Dados (412)');
		const cortado = caberNaLargura('Revista Brasileira de Política Internacional (403)', 200, medir);
		expect(cortado.endsWith('… (403)')).toBe(true);
		expect(medir(cortado)).toBeLessThanOrEqual(200);
		expect(caberNaLargura('Um nome comprido sem número', 100, medir)).toMatch(/…$/);
	});
});

describe('fonteDoCanvas', () => {
	it('põe o peso antes do tamanho, como pede o atalho font do CSS', () => {
		// "13.6px 600 Família" não é um font válido, e o canvas mediria com a fonte padrão (o nome não era cortado)
		expect(fonteDoCanvas(13.6, '"Instrument Sans", sans-serif', '600')).toBe('600 13.6px "Instrument Sans", sans-serif');
		expect(fonteDoCanvas(12, 'serif', '400')).toBe('12px serif');
		expect(fonteDoCanvas(12, 'serif')).toBe('12px serif');
	});
});
