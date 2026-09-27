import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import type { Classificacoes, CodebookContrato, Documentos, Topicos, Validacao } from '$lib/contrato/tipos';
import { Cubo } from '$lib/dados/cubo';
import { decodificar } from '$lib/dados/documentos';
import { FILTROS_PADRAO, normalizarFiltros, type Filtros } from '$lib/estado/url';
import { cruzamento, documentosDaCelula, LINHAS_CRUZAMENTO, porAno, referenciaDe, variaveisDaVista } from './agregar';

const pasta = join(import.meta.dirname, '../../../../contrato/exemplo/dados');
const ler = <T>(nome: string): T => JSON.parse(readFileSync(join(pasta, nome), 'utf8'));
const t = decodificar(ler<Documentos>('documentos.json'));
const topicos = ler<Topicos>('topicos.json');
const codebook = ler<CodebookContrato>('codebook.json');
const classificacoes = ler<Classificacoes>('classificacoes.json');
const validacao = ler<Validacao>('validacao.json');
const cubo = new Cubo(t, topicos);
const f = (parcial: Partial<Filtros> = {}) => normalizarFiltros({ ...FILTROS_PADRAO, ...parcial });
const variaveis = variaveisDaVista(codebook, t);

describe('variáveis da vista', () => {
	it('só as que têm coluna, com rótulos do codebook e "sem informação" marcado', () => {
		expect(variaveis.map((v) => v.id)).toEqual(Object.keys(t.cls));
		expect(variaveis.every((v) => v.tipo !== 'texto')).toBe(true);
		const abordagem = variaveis.find((v) => v.id === 'abordagem')!;
		expect(abordagem.valores).toEqual(codebook.variaveis[0].categorias!.map((c) => c.valor));
		expect(abordagem.semInformacao[abordagem.valores.indexOf('nao_informado')]).toBe(true);
		const bool = variaveis.find((v) => v.tipo === 'booleana')!;
		expect(bool.rotulos).toEqual(['Não', 'Sim']);
	});
});

describe('por ano', () => {
	it('sem recorte, bate com as contagens do classificacoes.json', () => {
		for (const v of variaveis) {
			const r = porAno(cubo, cubo.falhas(f()), v, topicos.anos);
			const soma = v.valores.map((_, x) => r.anos.reduce((s, _a, j) => s + r.n[j * v.valores.length + x], 0));
			const esperado = v.valores.map((valor) => classificacoes.contagens[v.id]?.[valor] ?? 0);
			expect(soma).toEqual(esperado);
			expect(r.classificados.reduce((s, x) => s + x, 0)).toBe(classificacoes.classificados);
		}
	});

	it('ignora o filtro de anos, mas não os outros', () => {
		const v = variaveis[0];
		const revista = t.revistas[0];
		const tudo = porAno(cubo, cubo.falhas(f({ revistas: [revista] })), v, topicos.anos);
		const comAnos = porAno(cubo, cubo.falhas(f({ revistas: [revista], anos: [2015, 2016] })), v, topicos.anos);
		expect(Array.from(comAnos.total)).toEqual(Array.from(tudo.total));
		const daRevista = Array.from(t.revista).filter((r) => t.revistas[r] === revista).length;
		expect(tudo.total.reduce((s, x) => s + x, 0)).toBe(daRevista);
	});
});

describe('cruzamento', () => {
	it.each(LINHAS_CRUZAMENTO)('por %s: soma ao total do recorte e a célula lista os documentos', (por) => {
		const v = variaveis[0];
		const falhas = cubo.falhas(f({ anos: [2014, 2020] }));
		const c = cruzamento(cubo, falhas, v, por);
		const k = v.valores.length;
		expect(c.n.length).toBe(c.linhas.length * k);
		expect(c.classificados.reduce((s, x) => s + x, 0)).toBe(cubo.contar(falhas));
		const [l, x] = [0, 1];
		const docs = documentosDaCelula(cubo, falhas, v, c, l, x);
		expect(docs.length).toBe(c.n[l * k + x]);
		expect(docs.every((i) => t.cls[v.id][i] === x && t.ano[i] >= 2014 && t.ano[i] <= 2020)).toBe(true);
		expect(documentosDaCelula(cubo, falhas, v, c, -1, x).length).toBe(
			c.linhas.reduce((s, _l, li) => s + c.n[li * k + x], 0)
		);
	});

	it('por macrotema: a última linha é "sem tópico"', () => {
		const c = cruzamento(cubo, cubo.falhas(f()), variaveis[0], 'macrotema');
		expect(c.linhas.at(-1)?.rotulo).toBe('Sem tópico');
		expect(c.linhas.length).toBe(topicos.macrotemas.length + 1);
	});
});

describe('referência da validação', () => {
	it('acha a métrica do modelo principal contra o codificador', () => {
		const r = referenciaDe(validacao, 'abordagem')!;
		expect(r.participante.tipo).toBe('referencia');
		expect(r.metrica.comparado).toBe(validacao.modelo_principal);
		expect(referenciaDe(validacao, 'nao_existe')).toBeNull();
		expect(referenciaDe(null, 'abordagem')).toBeNull();
	});

	it('prefere uma pessoa a um codificador de referência', () => {
		const m = validacao.metricas.find((x) => x.variavel === 'abordagem')!;
		const comPessoa: Validacao = {
			...validacao,
			codificadores: [...(validacao.codificadores ?? []), { nome: 'maria', tipo: 'humano', n: 10 }],
			metricas: [...validacao.metricas, { ...m, referencia: 'maria', comparacao: 'maria × exemplo', n: 10 }]
		};
		expect(referenciaDe(comPessoa, 'abordagem')!.participante.nome).toBe('maria');
	});
});
