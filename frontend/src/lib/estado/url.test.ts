import { describe, expect, it } from 'vitest';
import {
	CORES_POR,
	escreverFiltros,
	FILTROS_PADRAO,
	lerFiltros,
	lerHash,
	normalizarFiltros,
	parametrosDoHash,
	rota,
	temFiltros,
	type Filtros
} from './url';

describe('rota', () => {
	it('gera sempre um hash relativo #/caminho', () => {
		expect(rota('/')).toBe('#/');
		expect(rota('')).toBe('#/');
		expect(rota('/mapa')).toBe('#/mapa');
		expect(rota('mapa')).toBe('#/mapa');
		expect(rota('#/mapa/')).toBe('#/mapa');
	});

	it('acrescenta os parâmetros e ignora os vazios', () => {
		expect(rota('/mapa', { anos: '2012-2020', cor: 'topico' })).toBe('#/mapa?anos=2012-2020&cor=topico');
		expect(rota('/mapa', { topicos: [3, 7], busca: '', doc: null, x: undefined, y: false })).toBe(
			'#/mapa?topicos=3%2C7'
		);
		expect(rota('/mapa', new URLSearchParams('a=1'))).toBe('#/mapa?a=1');
	});
});

describe('lerHash', () => {
	it('separa caminho e parâmetros', () => {
		const { caminho, params } = lerHash('#/mapa?anos=2012-2020&cor=topico');
		expect(caminho).toBe('/mapa');
		expect(Object.fromEntries(params)).toEqual({ anos: '2012-2020', cor: 'topico' });
	});

	it('trata hash vazio como a Início', () => {
		expect(lerHash('').caminho).toBe('/');
		expect(lerHash('#').caminho).toBe('/');
		expect(lerHash('#/').caminho).toBe('/');
	});

	it('lê o hash de uma URL servida num subcaminho', () => {
		const url = new URL('http://127.0.0.1:4173/mapa-da-ciencia/demo/#/topicos?topicos=1,2');
		expect(parametrosDoHash(url).get('topicos')).toBe('1,2');
		// É o caso que o page.url.searchParams do SvelteKit não enxerga.
		expect(url.searchParams.size).toBe(0);
	});
});

describe('filtros: ida e volta pela URL', () => {
	const casos: Partial<Filtros>[] = [
		{},
		{ anos: [2012, 2020] },
		{ anos: [2015, 2015] },
		{ revistas: ['op', 'dados'] },
		{ topicos: [12, 3, -1] },
		{ cor: 'macrotema' },
		{ busca: 'coalizão & "presidencialismo"' },
		{ doc: 'doi:10.1590/1807-019120243011' },
		{ laco: { versao: 'a1b2c3', pontos: [[0.1, -2.25], [3, 4.5], [-1.125, 0]] } },
		{ vista: { x: -0.25, y: 0.5, zoom: 3.2 } },
		{
			anos: [2010, 2025],
			revistas: ['rbcpol'],
			topicos: [0, 27],
			cor: 'ano',
			busca: 'São Paulo',
			doc: 'exemplo:00042'
		}
	];

	it.each(casos)('filtros → URL → filtros preserva %j', (parcial) => {
		const f = normalizarFiltros(parcial);
		const link = rota('/mapa', escreverFiltros(f));
		const { caminho, params } = lerHash(link);
		expect(caminho).toBe('/mapa');
		expect(lerFiltros(params)).toEqual(f);
	});

	it('URL canônica → filtros → mesma URL', () => {
		const canonicas = [
			'',
			'anos=2012-2020',
			'anos=2015',
			'revistas=dados%2Cop',
			'topicos=-1%2C3%2C12',
			'cor=macrotema',
			'anos=2010-2025&revistas=rbcpol&topicos=0%2C27&cor=ano&busca=S%C3%A3o+Paulo&doc=exemplo%3A00042'
		];
		for (const texto of canonicas) {
			expect(escreverFiltros(lerFiltros(new URLSearchParams(texto))).toString()).toBe(texto);
		}
	});

	it('ida e volta com filtros aleatórios', () => {
		// Gerador determinístico (LCG), para o teste ser reprodutível.
		let s = 42;
		const aleatorio = () => (s = (s * 1664525 + 1013904223) % 2 ** 32) / 2 ** 32;
		const inteiro = (a: number, b: number) => a + Math.floor(aleatorio() * (b - a + 1));
		const revistas = ['dados', 'op', 'ln', 'rsocp', 'bpsr'];
		for (let i = 0; i < 300; i += 1) {
			const f = normalizarFiltros({
				anos: aleatorio() < 0.5 ? null : [inteiro(1990, 2025), inteiro(1990, 2025)],
				revistas: revistas.filter(() => aleatorio() < 0.3),
				topicos: Array.from({ length: inteiro(0, 4) }, () => inteiro(-1, 40)),
				cor: CORES_POR[inteiro(0, CORES_POR.length - 1)],
				busca: aleatorio() < 0.3 ? `termo ${inteiro(0, 99)}, ç&=?#` : '',
				doc: aleatorio() < 0.2 ? `exemplo:${inteiro(0, 1499)}` : null,
				laco:
					aleatorio() < 0.3
						? {
								versao: `v${inteiro(0, 999)}`,
								pontos: Array.from({ length: inteiro(3, 8) }, () => [aleatorio() * 20 - 10, aleatorio() * 20 - 10])
							}
						: null,
				vista: aleatorio() < 0.3 ? { x: aleatorio() * 2 - 1, y: aleatorio() * 2 - 1, zoom: 0.5 + aleatorio() * 8 } : null
			});
			expect(lerFiltros(lerHash(rota('/mapa', escreverFiltros(f))).params)).toEqual(f);
		}
	});

	it('omite os valores padrão', () => {
		expect(escreverFiltros(FILTROS_PADRAO).toString()).toBe('');
		expect(temFiltros(normalizarFiltros())).toBe(false);
		expect(temFiltros(normalizarFiltros({ cor: 'revista' }))).toBe(true);
	});

	it('ignora valores inválidos sem quebrar', () => {
		const f = lerFiltros(new URLSearchParams('anos=abc&topicos=1,x,2.5,3&cor=arco-iris&revistas=,,op'));
		expect(f).toEqual({ ...FILTROS_PADRAO, topicos: [1, 3], revistas: ['op'] });
	});

	it('põe anos invertidos em ordem', () => {
		expect(lerFiltros(new URLSearchParams('anos=2020-2012')).anos).toEqual([2012, 2020]);
	});
});

describe('laço e vista', () => {
	it('arredondam para 3 casas e descartam o que não serve', () => {
		const f = normalizarFiltros({
			laco: { versao: 'v1', pontos: [[0.12345, 1], [2, NaN], [3, 3], [1, 2.00049]] },
			vista: { x: -0.0001, y: 0.4, zoom: 2 }
		});
		expect(f.laco).toEqual({ versao: 'v1', pontos: [[0.123, 1], [3, 3], [1, 2]] });
		expect(f.vista).toEqual({ x: 0, y: 0.4, zoom: 2 });
		expect(normalizarFiltros({ laco: { versao: 'v1', pontos: [[0, 0], [1, 1]] } }).laco).toBeNull();
		expect(normalizarFiltros({ vista: { x: 0, y: 0, zoom: 0 } }).vista).toBeNull();
		expect(normalizarFiltros({ laco: { versao: 'não vale!', pontos: [[0, 0], [1, 0], [0, 1]] } }).laco?.versao).toBe('');
	});

	it('vão para a URL numa forma curta e legível', () => {
		const texto = escreverFiltros({
			laco: { versao: 'v1', pontos: [[0, 0], [1, 0], [0, 1]] },
			vista: { x: 0.5, y: -0.5, zoom: 2 }
		}).toString();
		expect(texto).toBe('laco=v1%7E0%2C0%7E1%2C0%7E0%2C1&vista=0.5%2C-0.5%2C2');
		expect(lerFiltros(new URLSearchParams('laco=v1~0,0~1,0&vista=1,2')).laco).toBeNull();
	});
});
