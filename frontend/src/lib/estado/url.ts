/**
 * O endereço do app: rotas e estado dos filtros, tudo dentro do hash (ADR 0002).
 *
 *     https://…/mapa-da-ciencia/demo/#/mapa?anos=2012-2020&cor=macrotema
 *                                    └─┬─┘└──────────┬───────────────┘
 *                                   caminho    filtros (URLSearchParams)
 *
 * Regras:
 * - links internos usam sempre `rota()`, que gera `#/caminho?params`. Nunca `resolve()` de
 *   `$app/paths`: num subcaminho ele gera `/sub#/rota` (sem a barra), o que força uma
 *   recarga completa. Um teste (`sem-resolve.test.ts`) barra o uso;
 * - `page.url.searchParams` não enxerga a parte `?…` do hash e devolve `{}`. Os filtros são
 *   lidos daqui, de `page.url.hash`;
 * - valores padrão não vão para a URL, e a ordem dos parâmetros é fixa. Assim, o mesmo
 *   estado gera sempre o mesmo link.
 */

export type ValorParametro = string | number | boolean | null | undefined | readonly (string | number)[];
export type Parametros = URLSearchParams | Record<string, ValorParametro>;

/** Link interno: `rota('/mapa', { anos: '2012-2020' })` → `#/mapa?anos=2012-2020`. */
export function rota(caminho: string, params?: Parametros): string {
	const limpo = `/${caminho.replace(/^[#/]+/, '').replace(/\/+$/, '')}`;
	const busca = params instanceof URLSearchParams ? params : paraBusca(params ?? {});
	const texto = busca.toString();
	return `#${limpo}${texto ? `?${texto}` : ''}`;
}

function paraBusca(params: Record<string, ValorParametro>): URLSearchParams {
	const busca = new URLSearchParams();
	for (const [chave, valor] of Object.entries(params)) {
		if (valor === undefined || valor === null || valor === '' || valor === false) continue;
		if (Array.isArray(valor)) {
			if (valor.length) busca.set(chave, valor.join(','));
		} else {
			busca.set(chave, String(valor));
		}
	}
	return busca;
}

/** Separa `#/mapa?anos=…` em caminho (`/mapa`) e parâmetros. Hash vazio é a Início (`/`). */
export function lerHash(hash: string): { caminho: string; params: URLSearchParams } {
	const semCerquilha = hash.replace(/^#/, '');
	const i = semCerquilha.indexOf('?');
	const caminho = i >= 0 ? semCerquilha.slice(0, i) : semCerquilha;
	return {
		caminho: `/${caminho.replace(/^\/+/, '')}`,
		params: new URLSearchParams(i >= 0 ? semCerquilha.slice(i + 1) : '')
	};
}

/** Os parâmetros que vêm depois do `?` dentro do hash de uma URL. */
export function parametrosDoHash(url: URL): URLSearchParams {
	return lerHash(url.hash).params;
}

// ---------------------------------------------------------------- filtros

export const CORES_POR = ['topico', 'macrotema', 'revista', 'ano'] as const;
export type CorPor = (typeof CORES_POR)[number];

/** Modos do fluxo dos tópicos: com a linha de base ondulada, empilhado em documentos, ou em proporção do ano. */
export const MODOS = ['fluxo', 'absoluto', 'proporcao'] as const;
export type Modo = (typeof MODOS)[number];

/** Linhas do cruzamento na vista Classificação. */
export const CRUZAR = ['macrotema', 'topico', 'revista'] as const;
export type Cruzar = (typeof CRUZAR)[number];

/** As redes da vista Redes: pessoas, instituições, estados e citações. */
export const REDES = ['coautoria', 'instituicoes', 'estados', 'citacoes'] as const;
export type Rede = (typeof REDES)[number];

/**
 * Laço desenhado no mapa: polígono em coordenadas dos dados (as do UMAP, que não dependem da tela), com a
 * versão do mapa em que foi desenhado. Um link de um mapa já regenerado ainda abre, mas com aviso.
 */
export interface Laco {
	versao: string;
	pontos: [number, number][];
}

/** Câmera do mapa: centro (NDC) e zoom. */
export interface Vista {
	x: number;
	y: number;
	zoom: number;
}

/**
 * O estado das vistas, no hash. Uma parte é o **recorte** (`CHAVES_RECORTE`), que as vistas de análise
 * compartilham e o trilho leva de uma seção a outra; o resto é de cada vista (câmera, cor, documento aberto…).
 */
export interface Filtros {
	/** Intervalo de anos, inclusivo. `null` = todo o período. */
	anos: [number, number] | null;
	/** Ids de revista (`dados`, `op`…). Vazio = todas. */
	revistas: string[];
	/** Ids de tópico. Vazio = todos. `-1` = sem tópico. */
	topicos: number[];
	/** Variável que dá a cor dos pontos no mapa. */
	cor: CorPor;
	/** Texto buscado em título e autores. */
	busca: string;
	/** Documento em destaque (id do contrato). */
	doc: string | null;
	/** Seleção por laço no mapa. */
	laco: Laco | null;
	/** Câmera do mapa. */
	vista: Vista | null;
	/** Siglas de UF: documentos com alguma afiliação nelas. Vazio = todas. */
	uf: string[];
	/** Países (ISO 3166-1 alfa-2): documentos com alguma afiliação neles. */
	pais: string[];
	/** Ids de instituição (`ror:…`, `openalex:I…`, apelido): documentos com alguma afiliação nelas. */
	inst: string[];
	/** Modo do fluxo na vista Tópicos. */
	modo: Modo;
	/** Macrotema aberto na vista Tópicos (mostra os tópicos dele). */
	macro: number | null;
	/** Tópico aberto na gaveta da vista Tópicos. Não confundir com `topicos`, que filtra. */
	topico: number | null;
	/** Variável do codebook aberta na vista Classificação (`null` = a primeira). */
	variavel: string | null;
	/** Com o que a vista Classificação cruza a variável. */
	cruzar: Cruzar;
	/** A rede mostrada na vista Redes. */
	rede: Rede;
	/** Nó aberto no cartão da vista Redes: o id publicado de uma pessoa ou o id de uma instituição. */
	no: string | null;
}

export const FILTROS_PADRAO: Readonly<Filtros> = Object.freeze({
	anos: null,
	revistas: [],
	topicos: [],
	cor: 'topico',
	busca: '',
	doc: null,
	laco: null,
	vista: null,
	uf: [],
	pais: [],
	inst: [],
	modo: 'fluxo',
	macro: null,
	topico: null,
	variavel: null,
	cruzar: 'macrotema',
	rede: 'coautoria',
	no: null
});

/** Ordem fixa dos parâmetros na URL (as chaves novas entram sem mudar a posição das antigas). */
const ORDEM: (keyof Filtros)[] = [
	'anos',
	'revistas',
	'topicos',
	'cor',
	'busca',
	'laco',
	'uf',
	'pais',
	'inst',
	'modo',
	'macro',
	'vista',
	'topico',
	'variavel',
	'cruzar',
	'rede',
	'no',
	'doc'
];

/** O recorte: o que as vistas de análise compartilham e o trilho leva de uma seção a outra. */
export const CHAVES_RECORTE = ['anos', 'revistas', 'topicos', 'busca', 'laco', 'uf', 'pais', 'inst'] as const;
export type ChaveRecorte = (typeof CHAVES_RECORTE)[number];
export type Recorte = Pick<Filtros, ChaveRecorte>;

/** Arredonda para `casas` decimais (e troca −0 por 0, para o texto da URL ser estável). */
function arredondar(v: number, casas = 3): number {
	const f = 10 ** casas;
	return Math.round(v * f) / f || 0;
}

function normalizarLaco(l: Laco | null): Laco | null {
	if (!l) return null;
	const pontos = l.pontos
		.filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y))
		.map(([x, y]) => [arredondar(x), arredondar(y)] as [number, number]);
	if (pontos.length < 3) return null;
	return { versao: /^[\w-]{0,16}$/.test(l.versao) ? l.versao : '', pontos };
}

function normalizarVista(v: Vista | null): Vista | null {
	if (!v || ![v.x, v.y, v.zoom].every(Number.isFinite) || v.zoom <= 0) return null;
	const vista = { x: arredondar(v.x), y: arredondar(v.y), zoom: arredondar(v.zoom) };
	// a câmera inicial (centro, sem zoom) é o padrão e não vai para o link
	return vista.x === 0 && vista.y === 0 && vista.zoom === 1 ? null : vista;
}

function lerLaco(texto: string | null): Laco | null {
	if (!texto) return null;
	const [versao, ...pares] = texto.split('~');
	const pontos = pares.map((p) => p.split(',').map(Number) as [number, number]).filter((p) => p.length === 2);
	return normalizarLaco({ versao, pontos });
}

function lerVista(texto: string | null): Vista | null {
	const partes = texto?.split(',').map(Number) ?? [];
	return partes.length === 3 ? normalizarVista({ x: partes[0], y: partes[1], zoom: partes[2] }) : null;
}

function lista(texto: string | null): string[] {
	return texto ? texto.split(',').map((s) => s.trim()).filter(Boolean) : [];
}

function codigos(valores: string[], padrao: RegExp): string[] {
	return [...new Set(valores.map((v) => v.trim()).filter((v) => padrao.test(v)))].sort();
}

function inteiroOuNulo(v: number | null): number | null {
	return v !== null && Number.isInteger(v) && v >= 0 ? v : null;
}

function lerInteiro(texto: string | null): number | null {
	return texto !== null && /^\d+$/.test(texto) ? Number(texto) : null;
}

function normalizarAnos(anos: [number, number] | null): [number, number] | null {
	if (!anos) return null;
	const [a, b] = anos;
	if (!Number.isInteger(a) || !Number.isInteger(b)) return null;
	return a <= b ? [a, b] : [b, a];
}

/** Põe os filtros na forma canônica: sem repetição, listas ordenadas, anos em ordem. */
export function normalizarFiltros(parcial: Partial<Filtros> = {}): Filtros {
	const f = { ...FILTROS_PADRAO, ...parcial };
	return {
		anos: normalizarAnos(f.anos),
		revistas: [...new Set(f.revistas.filter(Boolean))].sort(),
		topicos: [...new Set(f.topicos.filter((t) => Number.isInteger(t) && t >= -1))].sort((a, b) => a - b),
		cor: (CORES_POR as readonly string[]).includes(f.cor) ? f.cor : FILTROS_PADRAO.cor,
		busca: f.busca.trim(),
		doc: f.doc || null,
		laco: normalizarLaco(f.laco),
		vista: normalizarVista(f.vista),
		uf: codigos(f.uf, /^[A-Z]{2}$/),
		pais: codigos(f.pais, /^[A-Z]{2}$/),
		inst: codigos(f.inst, /^[\w:.-]{1,64}$/),
		modo: (MODOS as readonly string[]).includes(f.modo) ? f.modo : FILTROS_PADRAO.modo,
		macro: inteiroOuNulo(f.macro),
		topico: inteiroOuNulo(f.topico),
		variavel: f.variavel && /^[a-z0-9_]{1,40}$/.test(f.variavel) ? f.variavel : null,
		cruzar: (CRUZAR as readonly string[]).includes(f.cruzar) ? f.cruzar : FILTROS_PADRAO.cruzar,
		rede: (REDES as readonly string[]).includes(f.rede) ? f.rede : FILTROS_PADRAO.rede,
		no: f.no && /^[\w:.-]{1,64}$/.test(f.no) ? f.no : null
	};
}

/** Lê os filtros dos parâmetros do hash. Valores inválidos viram o padrão, sem erro. */
export function lerFiltros(params: URLSearchParams): Filtros {
	const anos = params.get('anos')?.match(/^(\d{4})(?:-(\d{4}))?$/);
	return normalizarFiltros({
		anos: anos ? [Number(anos[1]), Number(anos[2] ?? anos[1])] : null,
		revistas: lista(params.get('revistas')),
		topicos: lista(params.get('topicos'))
			.filter((t) => /^-?\d+$/.test(t))
			.map(Number),
		cor: (params.get('cor') ?? FILTROS_PADRAO.cor) as CorPor,
		busca: params.get('busca') ?? '',
		doc: params.get('doc'),
		laco: lerLaco(params.get('laco')),
		vista: lerVista(params.get('vista')),
		uf: lista(params.get('uf')),
		pais: lista(params.get('pais')),
		inst: lista(params.get('inst')),
		modo: (params.get('modo') ?? FILTROS_PADRAO.modo) as Modo,
		macro: lerInteiro(params.get('macro')),
		topico: lerInteiro(params.get('topico')),
		variavel: params.get('variavel'),
		cruzar: (params.get('cruzar') ?? FILTROS_PADRAO.cruzar) as Cruzar,
		rede: (params.get('rede') ?? FILTROS_PADRAO.rede) as Rede,
		no: params.get('no')
	});
}

/** Escreve os filtros como parâmetros, omitindo os valores padrão, na ordem fixa. */
export function escreverFiltros(parcial: Partial<Filtros>): URLSearchParams {
	const f = normalizarFiltros(parcial);
	const valores: Record<keyof Filtros, string | null> = {
		anos: f.anos ? (f.anos[0] === f.anos[1] ? `${f.anos[0]}` : `${f.anos[0]}-${f.anos[1]}`) : null,
		revistas: f.revistas.length ? f.revistas.join(',') : null,
		topicos: f.topicos.length ? f.topicos.join(',') : null,
		cor: f.cor === FILTROS_PADRAO.cor ? null : f.cor,
		busca: f.busca || null,
		doc: f.doc,
		laco: f.laco ? [f.laco.versao, ...f.laco.pontos.map(([x, y]) => `${x},${y}`)].join('~') : null,
		vista: f.vista ? `${f.vista.x},${f.vista.y},${f.vista.zoom}` : null,
		uf: f.uf.length ? f.uf.join(',') : null,
		pais: f.pais.length ? f.pais.join(',') : null,
		inst: f.inst.length ? f.inst.join(',') : null,
		modo: f.modo === FILTROS_PADRAO.modo ? null : f.modo,
		macro: f.macro === null ? null : String(f.macro),
		topico: f.topico === null ? null : String(f.topico),
		variavel: f.variavel,
		cruzar: f.cruzar === FILTROS_PADRAO.cruzar ? null : f.cruzar,
		rede: f.rede === FILTROS_PADRAO.rede ? null : f.rede,
		no: f.no
	};
	const busca = new URLSearchParams();
	for (const chave of ORDEM) {
		const v = valores[chave];
		if (v !== null) busca.set(chave, v);
	}
	return busca;
}

/** `true` se algum filtro difere do padrão. */
export function temFiltros(f: Filtros): boolean {
	return escreverFiltros(f).size > 0;
}

/** Só as chaves do recorte (o que o trilho leva de uma seção a outra). */
export function recorteDe(f: Partial<Filtros>): Partial<Filtros> {
	const saida: Partial<Filtros> = {};
	for (const chave of CHAVES_RECORTE) {
		if (chave in f) (saida as Record<string, unknown>)[chave] = f[chave];
	}
	return saida;
}

/** `true` se o recorte difere do corpus inteiro. */
export function temRecorte(f: Filtros): boolean {
	return escreverFiltros(recorteDe(f)).size > 0;
}

/** As chaves do recorte nos valores padrão: para "Limpar recorte" com `mudarFiltros`. */
export function limparRecorte(): Partial<Filtros> {
	return recorteDe(FILTROS_PADRAO);
}
