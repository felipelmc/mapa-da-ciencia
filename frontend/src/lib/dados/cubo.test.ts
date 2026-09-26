import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import type { Afiliacoes, Agregados, Documentos, Topicos } from '$lib/contrato/tipos';
import { FILTROS_PADRAO, normalizarFiltros, type Filtros } from '$lib/estado/url';
import { decodificarAfiliacoes } from './afiliacoes';
import { buscar, indiceDe } from './busca';
import { Cubo, D } from './cubo';
import { decodificar, paraNdc } from './documentos';
import { dentro, type Ponto } from '$lib/graficos/geometria';

const pasta = join(import.meta.dirname, '../../../../contrato/exemplo/dados');
const ler = <T>(nome: string): T => JSON.parse(readFileSync(join(pasta, nome), 'utf8'));
const documentos = ler<Documentos>('documentos.json');
const topicos = ler<Topicos>('topicos.json');
const agregados = ler<Agregados>('agregados.json');
const af = ler<Afiliacoes>('afiliacoes.json');
const t = decodificar(documentos);
const a = decodificarAfiliacoes(af, t.n);
const cubo = new Cubo(t, topicos, a);
const f = (parcial: Partial<Filtros> = {}) => normalizarFiltros({ ...FILTROS_PADRAO, ...parcial });

/** Tópico × ano × revista a partir do cubo, na forma das linhas do gabarito. */
function trios(falhas: Uint8Array, exceto = 0): Map<string, number> {
	const saida = new Map<string, number>();
	for (let i = 0; i < t.n; i += 1) {
		if ((falhas[i] & ~exceto & 0xff) !== 0) continue;
		const chave = `${t.topico[i]}|${t.ano[i]}|${t.revistas[t.revista[i]]}`;
		saida.set(chave, (saida.get(chave) ?? 0) + 1);
	}
	return saida;
}

function gabarito(filtro: (topico: number, ano: number, revista: string) => boolean): Map<string, number> {
	const saida = new Map<string, number>();
	for (const [topico, ano, revista, n] of agregados.topico_ano_revista) {
		if (filtro(topico, ano, revista)) saida.set(`${topico}|${ano}|${revista}`, n);
	}
	return saida;
}

describe('cubo contra o gabarito do Python (agregados.json)', () => {
	it('sem recorte, tópico × ano × revista é igual ao gabarito', () => {
		expect(trios(cubo.falhas(f()))).toEqual(gabarito(() => true));
	});

	it('com revistas e anos, bate com as linhas do gabarito que atendem ao filtro', () => {
		const revista = t.revistas[0];
		const falhas = cubo.falhas(f({ revistas: [revista], anos: [2015, 2020] }));
		expect(trios(falhas)).toEqual(gabarito((_, ano, r) => r === revista && ano >= 2015 && ano <= 2020));
	});

	it('UFs, países e instituições fracionários batem com o gabarito', () => {
		const falhas = cubo.falhas(f());
		const porUf = cubo.somarAfiliacoesPor(falhas, 0, a.ufs.length, (l) => a.uf[l]);
		const porPais = cubo.somarAfiliacoesPor(falhas, 0, a.paises.length, (l) => a.pais[l]);
		const porInst = cubo.somarAfiliacoesPor(falhas, 0, a.instituicoes.length, (l) => a.inst[l]);
		for (const [uf, v] of Object.entries(agregados.uf)) expect(porUf[a.ufs.indexOf(uf)]).toBeCloseTo(v, 2);
		for (const [pais, v] of Object.entries(agregados.pais)) expect(porPais[a.paises.indexOf(pais)]).toBeCloseTo(v, 2);
		for (const [id, v] of Object.entries(agregados.instituicao ?? {})) {
			expect(porInst[a.indiceInst.get(id)!]).toBeCloseTo(v, 2);
		}
		const inteiros = cubo.documentosPorLugar(falhas, 0, a.ufs.length, (l) => a.uf[l]);
		for (const [uf, v] of Object.entries(agregados.uf_inteiro ?? {})) expect(inteiros[a.ufs.indexOf(uf)]).toBe(v);
	});

	it('cada documento soma peso 1, e a série do cubo é a do topicos.json', () => {
		const soma = new Float64Array(t.n);
		for (let l = 0; l < a.n; l += 1) soma[a.doc[l]] += a.peso[l];
		expect(Math.max(...Array.from(soma, (s) => Math.abs(s - 1)))).toBeLessThan(1e-5);
		const s = cubo.topicoPorAno(cubo.falhas(f()), 0);
		expect(Array.from(s.total)).toEqual(topicos.total_por_ano);
		topicos.topicos.forEach((topico, linha) => {
			expect(Array.from(s.n.subarray(linha * s.anos.length, (linha + 1) * s.anos.length))).toEqual(topico.serie.n);
		});
		const semTopico = Array.from(s.n.subarray(s.ids.length * s.anos.length));
		expect(semTopico).toEqual(topicos.outliers.sem_topico_por_ano);
	});
});

describe('cubo: dimensões e exclusões', () => {
	let semente = 42;
	const aleatorio = () => (semente = (semente * 1664525 + 1013904223) % 2 ** 32) / 2 ** 32;
	const escolher = <T>(lista: T[]) => lista.filter(() => aleatorio() < 0.3);

	function ingenuo(filtro: Filtros, i: number, exceto = 0): boolean {
		if (!(exceto & D.ANO) && filtro.anos && (t.ano[i] < filtro.anos[0] || t.ano[i] > filtro.anos[1])) return false;
		if (!(exceto & D.REVISTA) && filtro.revistas.length && !filtro.revistas.includes(t.revistas[t.revista[i]]))
			return false;
		if (!(exceto & D.TOPICO) && filtro.topicos.length && !filtro.topicos.includes(t.topico[i])) return false;
		const linhas = Array.from(a.linhas.subarray(a.inicio[i], a.inicio[i + 1]));
		if (!(exceto & D.UF) && filtro.uf.length && !linhas.some((l) => filtro.uf.includes(a.ufs[a.uf[l]])))
			return false;
		if (!(exceto & D.PAIS) && filtro.pais.length && !linhas.some((l) => filtro.pais.includes(a.paises[a.pais[l]])))
			return false;
		return true;
	}

	it('contar() é igual à filtragem ingênua em 300 recortes aleatórios, com e sem exclusões', () => {
		const ids = topicos.topicos.map((x) => x.id);
		for (let k = 0; k < 300; k += 1) {
			const de = 2010 + Math.floor(aleatorio() * 16);
			const filtro = f({
				anos: aleatorio() < 0.5 ? [de, Math.min(2025, de + Math.floor(aleatorio() * 8))] : null,
				revistas: escolher(t.revistas),
				topicos: escolher([...ids, -1]),
				uf: aleatorio() < 0.3 ? escolher(a.ufs) : [],
				pais: aleatorio() < 0.2 ? escolher(a.paises) : []
			});
			const falhas = cubo.falhas(filtro);
			const exceto = [0, D.ANO, D.TOPICO, D.UF, D.ANO | D.TOPICO][k % 5];
			let esperado = 0;
			for (let i = 0; i < t.n; i += 1) if (ingenuo(filtro, i, exceto)) esperado += 1;
			expect(cubo.contar(falhas, exceto)).toBe(esperado);
		}
	});

	it('excluir uma dimensão é o mesmo que tirar aquele filtro', () => {
		const com = cubo.falhas(f({ anos: [2012, 2016], revistas: [t.revistas[1]] }));
		const sem = cubo.contar(cubo.falhas(f({ revistas: [t.revistas[1]] })));
		expect(cubo.contar(com, D.ANO)).toBe(sem);
	});

	it('filtro de lugar é por documento: basta uma afiliação; sem afiliação, não passa', () => {
		const falhas = cubo.falhas(f({ uf: ['SP'] }));
		const sp = a.ufs.indexOf('SP');
		for (let d = 0; d < t.n; d += 1) {
			const temSp = Array.from(a.linhas.subarray(a.inicio[d], a.inicio[d + 1])).some((l) => a.uf[l] === sp);
			expect(falhas[d] === 0).toBe(temSp);
		}
		const semAfiliacao = Array.from({ length: t.n }, (_, d) => d).filter((d) => !a.comAfiliacao[d]);
		expect(semAfiliacao.length).toBeGreaterThan(0);
		expect(semAfiliacao.every((d) => falhas[d] !== 0)).toBe(true);
	});

	it('busca e laço são dimensões como as outras', () => {
		const achados = new Set(buscar(indiceDe(t), 'eleições'));
		const falhas = cubo.falhas(f({ busca: 'eleições' }));
		expect(achados.size).toBeGreaterThan(0);
		for (let i = 0; i < t.n; i += 1) expect(falhas[i] === 0).toBe(achados.has(i));
		const pontos: [number, number][] = [
			[-3, -3],
			[3, -3],
			[3, 3],
			[-3, 3]
		];
		const lacoFalhas = cubo.falhas(f({ laco: { versao: 'x', pontos } }));
		const poligono = pontos.map(([x, y]) => paraNdc(t.escala, x, y) as Ponto);
		for (let i = 0; i < t.n; i += 1) expect(lacoFalhas[i] === 0).toBe(dentro(t.x[i], t.y[i], poligono));
		expect(cubo.indices(cubo.falhas(f()))).toBeNull();
	});

	it('ids de tópico esparsos: cada série fica na linha do seu tópico', () => {
		const ids = topicos.topicos.map((x) => x.id);
		expect(Math.max(...ids)).toBeGreaterThan(ids.length); // o exemplo tem ids não contíguos
		const alvo = ids[ids.length - 1];
		const s = cubo.topicoPorAno(cubo.falhas(f({ topicos: [alvo] })), 0);
		const linha = ids.indexOf(alvo);
		const soma = (l: number) => s.n.subarray(l * s.anos.length, (l + 1) * s.anos.length).reduce((x, y) => x + y, 0);
		expect(soma(linha)).toBe(topicos.topicos[linha].n);
		expect(soma(0) + soma(ids.length)).toBe(linha === 0 ? topicos.topicos[0].n : 0);
	});
});
