import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import type { Afiliacoes, Agregados, Citacoes, Documentos, Redes, Topicos } from '$lib/contrato/tipos';
import { decodificarAfiliacoes } from '$lib/dados/afiliacoes';
import { Cubo } from '$lib/dados/cubo';
import { decodificar } from '$lib/dados/documentos';
import { agrupar, decodificarCitacoes, decodificarRedes } from '$lib/dados/redes';
import { normalizarFiltros } from '$lib/estado/url';
import {
	arestasCoautoria,
	arestasInstituicoes,
	arestasLugares,
	canoneNoRecorte,
	citacoesInternas,
	colaboracaoPorAno,
	contarNoRecorte,
	documentosPorInstituicao,
	faixaDoPeso,
	faixasNoRecorte,
	forcaDe,
	grauDe,
	macroDoDoc,
	maisCitadas,
	nomeDoLugar,
	paresPonderados,
	parceiros,
	renumerar,
	type Passa
} from './calculo';

const pasta = join(import.meta.dirname, '../../../../contrato/exemplo/dados');
const ler = <T>(nome: string): T => JSON.parse(readFileSync(join(pasta, nome), 'utf8'));
const documentos = ler<Documentos>('documentos.json');
const topicos = ler<Topicos>('topicos.json');
const agregados = ler<Agregados>('agregados.json');
const brutoRedes = ler<Redes>('redes.json');
const brutoCitacoes = ler<Citacoes>('citacoes.json');
const t = decodificar(documentos);
const af = decodificarAfiliacoes(ler<Afiliacoes>('afiliacoes.json'), t.n);
const r = decodificarRedes(brutoRedes, t.n);
const c = decodificarCitacoes(brutoCitacoes);
const macro = macroDoDoc(t.topico, topicos);
const nMacros = topicos.macrotemas.length;

/** Os pares de coautores do recorte, contados de novo à moda ingênua, a partir das listas cruas do JSON. */
function paresIngenuos(passa: (d: number) => boolean): Map<string, [number, number]> {
	const porDoc = new Map<number, Set<number>>();
	brutoRedes.autorias.doc.forEach((d, k) => {
		if (!passa(d)) return;
		if (!porDoc.has(d)) porDoc.set(d, new Set());
		porDoc.get(d)!.add(brutoRedes.autorias.pessoa[k]);
	});
	const saida = new Map<string, [number, number]>();
	for (const pessoas of porDoc.values()) {
		const lista = [...pessoas].sort((a, b) => a - b);
		for (let i = 0; i < lista.length; i += 1) {
			for (let j = i + 1; j < lista.length; j += 1) {
				const chave = `${lista[i]}-${lista[j]}`;
				const [p, n] = saida.get(chave) ?? [0, 0];
				saida.set(chave, [p + 1 / (lista.length - 1), n + 1]);
			}
		}
	}
	return saida;
}

describe('decodificação', () => {
	it('agrupa por linha sem repetir itens, em ordem', () => {
		const csr = agrupar(3, [2, 0, 2, 0, 2, 5, -1], [7, 1, 3, 1, 7, 9, 4]);
		expect(Array.from(csr.inicio)).toEqual([0, 1, 1, 3]);
		expect(Array.from(csr.itens)).toEqual([1, 3, 7]);
	});

	it('guarda as pessoas sem posição como NaN e os documentos de cada uma', () => {
		const semPosicao = brutoRedes.pessoas.x.filter((x) => x === null).length;
		expect(Array.from(r.pessoas.x).filter(Number.isNaN)).toHaveLength(semPosicao);
		expect(Array.from(contarNoRecorte(r.docsDaPessoa, null))).toEqual(brutoRedes.pessoas.documentos);
	});
});

describe('as redes do corpus inteiro batem com o Python', () => {
	it('coautoria: o número de pares é o do gabarito, e o grau é o de cada pessoa', () => {
		const ar = arestasCoautoria(r, null);
		expect(ar.n).toBe(agregados.arestas_coautoria);
		expect(ar.n).toBe(brutoRedes.metricas!.coautoria.arestas);
		expect(Array.from(grauDe(ar, r.pessoas.n))).toEqual(brutoRedes.pessoas.grau);
		// cada documento distribui no máximo 1 por pessoa: a força de uma pessoa não passa dos documentos dela
		const forca = forcaDe(ar, r.pessoas.n);
		for (let p = 0; p < r.pessoas.n; p += 1) expect(forca[p]).toBeLessThanOrEqual(r.pessoas.documentos[p] + 1e-9);
	});

	it('instituições: os pares e o grau da rede desenhada', () => {
		const inst = r.instituicoes!;
		const mapa = Int32Array.from(af.instituicoes, (i) => inst.indice.get(i.id) ?? -1);
		const bruto = arestasInstituicoes(af, null);
		const ar = renumerar(bruto, mapa);
		expect(ar.n).toBe(bruto.n); // nenhuma instituição com parceira fica fora do desenho
		expect(ar.n).toBe(brutoRedes.metricas!.instituicoes.arestas);
		expect(Array.from(grauDe(ar, inst.n))).toEqual(brutoRedes.instituicoes!.grau);
	});

	it('estados: os pares de UFs (com o exterior) são os do gabarito', () => {
		const ar = arestasLugares(af, null);
		const par = (x: string, y: string) => [x, y].sort().join('|');
		const nossos = new Map<string, [number, number]>();
		for (let k = 0; k < ar.n; k += 1) {
			nossos.set(par(nomeDoLugar(af, ar.a[k]), nomeDoLugar(af, ar.b[k])), [ar.peso[k], ar.documentos[k]]);
		}
		expect(nossos.size).toBe(agregados.uf_pares!.length);
		for (const [a, b, peso, docs] of agregados.uf_pares!) {
			const [p, n] = nossos.get(par(a, b))!;
			expect(p).toBeCloseTo(peso, 6);
			expect(n).toBe(docs);
		}
	});

	it('colaboração por ano: as mesmas frações da série do Python', () => {
		const serie = colaboracaoPorAno(t.ano, r, af, null);
		expect(serie.map((s) => s.ano)).toEqual(brutoRedes.colaboracao!.map((s) => s.ano));
		serie.forEach((s, i) => {
			const py = brutoRedes.colaboracao![i];
			expect(s.documentos).toBe(py.documentos);
			expect(s.comCoautoria).toBeCloseTo(py.com_coautoria, 4);
			expect(s.autoresMedio).toBeCloseTo(py.autores_medio, 3);
			expect(s.comInstituicoes).toBeCloseTo(py.com_instituicoes!, 4);
			expect(s.entreUfs).toBeCloseTo(py.entre_ufs!, 4);
			expect(s.comExterior).toBeCloseTo(py.com_exterior!, 4);
		});
		expect(colaboracaoPorAno(t.ano, r, null, null)[0].comInstituicoes).toBeNull();
	});

	it('cânone: o número de citantes de cada obra é o do gabarito, e as fatias por macrotema somam o total', () => {
		const lista = canoneNoRecorte(c, null, macro, nMacros);
		expect(lista.map((o) => o.n)).toEqual(agregados.canone_n);
		for (const o of lista) expect(o.porMacro.reduce((a, b) => a + b, 0)).toBe(o.n);
		expect(maisCitadas(lista, 3).map((o) => o.obra)).toEqual([0, 1, 2]);
	});

	it('citações internas: todas no corpus inteiro, e a matriz dos macrotemas é a do Python', () => {
		const { n, matriz } = citacoesInternas(c, null, macro, nMacros);
		expect(n).toBe(brutoCitacoes.internas.de.length);
		expect(n).toBe(brutoCitacoes.cobertura!.internas);
		expect(matriz).toEqual(brutoCitacoes.fluxo_macrotemas);
	});
});

describe('no recorte', () => {
	const cubo = new Cubo(t, topicos, af);
	const passaDe = (parcial: Parameters<typeof normalizarFiltros>[0]): ((d: number) => boolean) => {
		const falhas = cubo.falhas(normalizarFiltros(parcial));
		return (d) => falhas[d] === 0;
	};

	it('a coautoria de um período bate com a contagem ingênua', () => {
		for (const anos of [[2015, 2018], [2010, 2010], [2020, 2025]] as [number, number][]) {
			const passa = passaDe({ anos });
			const ar = arestasCoautoria(r, passa);
			const esperado = paresIngenuos(passa);
			expect(ar.n).toBe(esperado.size);
			for (let k = 0; k < ar.n; k += 1) {
				const [p, n] = esperado.get(`${ar.a[k]}-${ar.b[k]}`)!;
				expect(ar.peso[k]).toBeCloseTo(p, 9);
				expect(ar.documentos[k]).toBe(n);
			}
			expect(ar.n).toBeLessThan(agregados.arestas_coautoria!);
		}
	});

	it('com uma UF no recorte, só entram documentos com afiliação nela', () => {
		const passa = passaDe({ uf: ['SP'] });
		const ar = arestasLugares(af, passa);
		const sp = af.ufs.indexOf('SP');
		const total = arestasLugares(af, null);
		expect(ar.n).toBeGreaterThan(0);
		expect(ar.n).toBeLessThanOrEqual(total.n);
		// os pares com SP no recorte são os mesmos do corpus inteiro: todo documento com SP passa
		const comSp = (x: typeof ar) => Array.from({ length: x.n }, (_, k) => k).filter((k) => x.a[k] === sp || x.b[k] === sp).length;
		expect(comSp(ar)).toBe(comSp(total));
	});

	it('as citações internas precisam das duas pontas no recorte', () => {
		const passa = passaDe({ anos: [2018, 2025] });
		const esperado = brutoCitacoes.internas.de.filter((de, k) => passa(de) && passa(brutoCitacoes.internas.para[k])).length;
		expect(citacoesInternas(c, passa, macro, nMacros).n).toBe(esperado);
		const lista = canoneNoRecorte(c, passa, macro, nMacros);
		lista.forEach((o, k) => expect(o.n).toBeLessThanOrEqual(agregados.canone_n![k]));
	});

	it('documentos por pessoa e por instituição', () => {
		const passa: Passa = passaDe({ anos: [2012, 2016] });
		const porPessoa = contarNoRecorte(r.docsDaPessoa, passa);
		for (let p = 0; p < 5; p += 1) {
			const docs = new Set(brutoRedes.autorias.doc.filter((d, k) => brutoRedes.autorias.pessoa[k] === p && passa!(d)));
			expect(porPessoa[p]).toBe(docs.size);
		}
		expect(Array.from(documentosPorInstituicao(af, null))).toEqual(
			af.instituicoes.map((i) => agregados.instituicao_inteiro?.[i.id] ?? 0)
		);
	});
});

describe('peças pequenas', () => {
	it('pares ponderados: um artigo de três autores dá 1/2 a cada par', () => {
		const grupos = [[0, 1, 2], [0, 1], [3], [1, 1, 0]];
		const ar = paresPonderados(4, 4, (d, s) => s.push(...grupos[d]), null);
		expect(Array.from(ar.a)).toEqual([0, 0, 1]);
		expect(Array.from(ar.b)).toEqual([1, 2, 2]);
		expect(Array.from(ar.peso)).toEqual([2.5, 0.5, 0.5]);
		expect(Array.from(ar.documentos)).toEqual([3, 1, 1]);
		expect(parceiros(ar, 0)).toEqual([[1, 2.5, 3], [2, 0.5, 1]]);
	});

	it('as faixas crescem com o peso e aceitam somas imprecisas', () => {
		expect([0.2, 0.5, 1 / 3 + 1 / 3 + 1 / 3, 1.5, 3, 7].map(faixaDoPeso)).toEqual([1, 1, 2, 3, 3, 4]);
	});

	it('as arestas fora do recorte ficam na faixa 0', () => {
		const corpus = paresPonderados(2, 3, (d, s) => s.push(...[[0, 1], [1, 2]][d]), null);
		const recorte = paresPonderados(2, 3, (d, s) => s.push(...[[0, 1], [1, 2]][d]), (d) => d === 1);
		expect(Array.from(faixasNoRecorte(corpus, recorte, 3))).toEqual([0, 2]);
	});
});
