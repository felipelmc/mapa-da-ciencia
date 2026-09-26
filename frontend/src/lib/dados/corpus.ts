/**
 * O corpus decodificado, uma vez por fonte de dados: a tabela de documentos, os tópicos, as afiliações e o cubo
 * do filtro cruzado. A barra de recorte e as vistas pedem daqui e nunca decodificam (nem baixam) duas vezes.
 */
import type { Manifesto, Topicos } from '$lib/contrato/tipos';
import { decodificarAfiliacoes, type TabelaAfiliacoes } from './afiliacoes';
import { Cubo } from './cubo';
import { decodificar, type TabelaDocumentos } from './documentos';
import type { FonteDeDados } from './fonte';

export interface Corpus {
	tabela: TabelaDocumentos;
	topicos: Topicos;
}

/** O corpus, as afiliações (se houver) e o cubo: tudo o que as vistas de análise precisam. */
export interface Aberto extends Corpus {
	afiliacoes: TabelaAfiliacoes | null;
	cubo: Cubo;
}

const corpos = new WeakMap<FonteDeDados, Promise<Corpus | null>>();
const afiliacoes = new WeakMap<FonteDeDados, Promise<TabelaAfiliacoes | null>>();
const cubos = new WeakMap<FonteDeDados, Promise<Aberto | null>>();

/** Documentos e tópicos (só existem depois de `mapa topicos`; sem eles, `null` e nenhum pedido). */
export function abrirCorpus(fonte: FonteDeDados): Promise<Corpus | null> {
	let p = corpos.get(fonte);
	if (!p) {
		p = Promise.all([fonte.documentos(), fonte.topicos()]).then(([documentos, topicos]) =>
			documentos && topicos ? { tabela: decodificar(documentos), topicos } : null
		);
		corpos.set(fonte, p);
	}
	return p;
}

/** A tabela de afiliações (só existe depois de `mapa geografia`). */
export function abrirAfiliacoes(fonte: FonteDeDados, tabela: TabelaDocumentos): Promise<TabelaAfiliacoes | null> {
	let p = afiliacoes.get(fonte);
	if (!p) {
		p = fonte.afiliacoes().then((a) => (a ? decodificarAfiliacoes(a, tabela.n) : null));
		afiliacoes.set(fonte, p);
	}
	return p;
}

/**
 * O cubo do projeto, com as afiliações quando o projeto já tem geografia. Todas as vistas e a barra de recorte
 * usam este mesmo cubo, para as contagens baterem entre si.
 */
export function abrirCubo(fonte: FonteDeDados): Promise<Aberto | null> {
	let p = cubos.get(fonte);
	if (!p) {
		p = abrirCorpus(fonte).then(async (corpus) => {
			if (!corpus) return null;
			const a = (await fonte.tem('afiliacoes')) ? await abrirAfiliacoes(fonte, corpus.tabela) : null;
			return { ...corpus, afiliacoes: a, cubo: new Cubo(corpus.tabela, corpus.topicos, a) };
		});
		cubos.set(fonte, p);
	}
	return p;
}

/** Versão do mapa: muda quando os tópicos são regenerados. Um laço de um link antigo abre com aviso. */
export function versaoDoMapa(manifesto: Manifesto): string {
	const texto = `${manifesto.gerado_em}|${manifesto.contagens.topicos}`;
	let h = 0x811c9dc5;
	for (let i = 0; i < texto.length; i += 1) h = Math.imul(h ^ texto.charCodeAt(i), 0x01000193) >>> 0;
	return h.toString(36).slice(0, 6);
}
