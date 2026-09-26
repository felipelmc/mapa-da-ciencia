/**
 * O `afiliacoes.json` (tabela longa: documento × instituição, UF e país, com o peso fracionário) em arrays
 * tipados, com um índice por documento (CSR) para o filtro cruzado saber, em tempo constante, as linhas de cada
 * documento.
 */
import type { Afiliacoes, Instituicao } from '$lib/contrato/tipos';

export const NAO_IDENTIFICADA = 'nao-identificada';

export interface TabelaAfiliacoes {
	/** Linhas da tabela. */
	n: number;
	doc: Int32Array;
	/** Índice em `instituicoes`, ou -1 (autor sem afiliação). */
	inst: Int32Array;
	/** Índice em `ufs`, ou -1. */
	uf: Int16Array;
	/** Índice em `paises`, ou -1. */
	pais: Int16Array;
	peso: Float64Array;
	/** Linhas de cada documento: `linhas[inicio[d] .. inicio[d+1])`. */
	inicio: Int32Array;
	linhas: Int32Array;
	/** 1 se o documento tem alguma afiliação informada (instituição identificada ou não). */
	comAfiliacao: Uint8Array;
	instituicoes: Instituicao[];
	ufs: string[];
	paises: string[];
	indiceInst: Map<string, number>;
	/** Índice da instituição reservada `nao-identificada`, ou -1. */
	naoIdentificada: number;
}

export function decodificarAfiliacoes(a: Afiliacoes, nDocs: number): TabelaAfiliacoes {
	const n = a.n;
	const c = a.colunas;
	const doc = Int32Array.from(c.doc);
	const inicio = new Int32Array(nDocs + 1);
	for (let i = 0; i < n; i += 1) inicio[doc[i] + 1] += 1;
	for (let d = 0; d < nDocs; d += 1) inicio[d + 1] += inicio[d];
	const posicao = inicio.slice(0, nDocs);
	const linhas = new Int32Array(n);
	for (let i = 0; i < n; i += 1) linhas[posicao[doc[i]]++] = i;
	const inst = Int32Array.from(c.instituicao);
	const comAfiliacao = new Uint8Array(nDocs);
	for (let i = 0; i < n; i += 1) if (inst[i] >= 0) comAfiliacao[doc[i]] = 1;
	const instituicoes = a.dicionarios.instituicao;
	return {
		n,
		doc,
		inst,
		uf: Int16Array.from(c.uf),
		pais: Int16Array.from(c.pais),
		peso: Float64Array.from(c.peso),
		inicio,
		linhas,
		comAfiliacao,
		instituicoes,
		ufs: a.dicionarios.uf,
		paises: a.dicionarios.pais,
		indiceInst: new Map(instituicoes.map((x, i) => [x.id, i])),
		naoIdentificada: instituicoes.findIndex((x) => x.id === NAO_IDENTIFICADA)
	};
}
