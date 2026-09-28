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
	/**
	 * Por que as afiliações não abriram, quando o projeto tem geografia mas o arquivo falhou (rede instável). Só a
	 * vista Geografia depende delas: as outras seguem com o cubo sem lugares.
	 */
	erroAfiliacoes: Error | null;
	cubo: Cubo;
}

const corpos = new WeakMap<FonteDeDados, Promise<Corpus | null>>();
const afiliacoes = new WeakMap<FonteDeDados, Promise<TabelaAfiliacoes | null>>();
const cubos = new WeakMap<FonteDeDados, Promise<Aberto | null>>();

/**
 * A promessa guardada para a fonte, ou uma nova. Uma falha (de rede, passageira) não fica guardada: a próxima
 * chamada tenta de novo, como na `FonteEstatica`.
 */
function lembrar<T>(guardadas: WeakMap<FonteDeDados, Promise<T>>, fonte: FonteDeDados, criar: () => Promise<T>): Promise<T> {
	let p = guardadas.get(fonte);
	if (!p) {
		const nova = criar();
		guardadas.set(fonte, nova);
		nova.catch(() => {
			if (guardadas.get(fonte) === nova) guardadas.delete(fonte);
		});
		p = nova;
	}
	return p;
}

/** Documentos e tópicos (só existem depois de `mapa topicos`; sem eles, `null` e nenhum pedido). */
export function abrirCorpus(fonte: FonteDeDados): Promise<Corpus | null> {
	return lembrar(corpos, fonte, () =>
		Promise.all([fonte.documentos(), fonte.topicos()]).then(([documentos, topicos]) =>
			documentos && topicos ? { tabela: decodificar(documentos), topicos } : null
		)
	);
}

/** A tabela de afiliações (só existe depois de `mapa geografia`). */
export function abrirAfiliacoes(fonte: FonteDeDados, tabela: TabelaDocumentos): Promise<TabelaAfiliacoes | null> {
	return lembrar(afiliacoes, fonte, () =>
		fonte.afiliacoes().then((a) => (a ? decodificarAfiliacoes(a, tabela.n) : null))
	);
}

/**
 * O cubo do projeto, com as afiliações quando o projeto já tem geografia. Todas as vistas e a barra de recorte
 * usam este mesmo cubo, para as contagens baterem entre si. Se as afiliações falharem, o cubo abre sem elas (e com
 * `erroAfiliacoes`): a falha de um arquivo que só a Geografia usa não derruba o Mapa, os Tópicos e a Classificação.
 */
export function abrirCubo(fonte: FonteDeDados): Promise<Aberto | null> {
	return lembrar(cubos, fonte, () =>
		abrirCorpus(fonte).then(async (corpus) => {
			if (!corpus) return null;
			let a: TabelaAfiliacoes | null = null;
			let erroAfiliacoes: Error | null = null;
			if (await fonte.tem('afiliacoes')) {
				try {
					a = await abrirAfiliacoes(fonte, corpus.tabela);
				} catch (e) {
					erroAfiliacoes = e instanceof Error ? e : new Error(String(e));
				}
			}
			return { ...corpus, afiliacoes: a, erroAfiliacoes, cubo: new Cubo(corpus.tabela, corpus.topicos, a) };
		})
	);
}

const ouvintes = new Set<() => void>();

/** Chama `ouvinte` quando o cubo for reaberto ("Tentar de novo"), para a barra do recorte trocar de cubo. */
export function aoReabrir(ouvinte: () => void): () => void {
	ouvintes.add(ouvinte);
	return () => ouvintes.delete(ouvinte);
}

/** "Tentar de novo": esquece o cubo guardado (que pode ter aberto sem as afiliações) e abre outra vez. */
export function reabrirCubo(fonte: FonteDeDados): Promise<Aberto | null> {
	cubos.delete(fonte);
	const p = abrirCubo(fonte);
	for (const ouvinte of ouvintes) ouvinte();
	return p;
}

function fnv1a(bytes: Uint8Array, h = 0x811c9dc5): number {
	for (let i = 0; i < bytes.length; i += 1) h = Math.imul(h ^ bytes[i], 0x01000193) >>> 0;
	return h;
}

const versoes = new WeakMap<TabelaDocumentos, string>();

/**
 * Versão do mapa: um hash das coordenadas dos documentos, na ordem dos ids. O laço guarda a versão em que foi
 * desenhado, e só um mapa com outras coordenadas (os tópicos refeitos) o abre com aviso. Reexportar sem refazer os
 * tópicos (classificar, geografia, publicar) não muda a versão.
 */
export function versaoDoMapa(tabela: TabelaDocumentos): string {
	let v = versoes.get(tabela);
	if (!v) {
		const bytes = (a: Float32Array) => new Uint8Array(a.buffer, a.byteOffset, a.byteLength);
		v = fnv1a(bytes(tabela.y), fnv1a(bytes(tabela.x))).toString(36).slice(0, 6);
		versoes.set(tabela, v);
	}
	return v;
}

/**
 * A versão que os laços levavam até a 1.0.1: o hash de `gerado_em` do manifesto, que mudava a cada reexportação.
 * Um laço com ela ainda vale se o manifesto for o mesmo em que ele foi desenhado.
 */
function versaoPeloManifesto(manifesto: Manifesto): string {
	const texto = `${manifesto.gerado_em}|${manifesto.contagens.topicos}`;
	let h = 0x811c9dc5;
	for (let i = 0; i < texto.length; i += 1) h = Math.imul(h ^ texto.charCodeAt(i), 0x01000193) >>> 0;
	return h.toString(36).slice(0, 6);
}

/** `true` se um laço desenhado na versão `versao` vale neste mapa (sem o aviso de "versão anterior"). */
export function lacoVale(versao: string, tabela: TabelaDocumentos, manifesto: Manifesto): boolean {
	return versao === versaoDoMapa(tabela) || versao === versaoPeloManifesto(manifesto);
}
