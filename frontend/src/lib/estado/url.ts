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

/** O recorte que as vistas compartilham. Cada campo vira um parâmetro do hash. */
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
}

export const FILTROS_PADRAO: Readonly<Filtros> = Object.freeze({
	anos: null,
	revistas: [],
	topicos: [],
	cor: 'topico',
	busca: '',
	doc: null
});

/** Ordem fixa dos parâmetros na URL. */
const ORDEM: (keyof Filtros)[] = ['anos', 'revistas', 'topicos', 'cor', 'busca', 'doc'];

function lista(texto: string | null): string[] {
	return texto ? texto.split(',').map((s) => s.trim()).filter(Boolean) : [];
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
		doc: f.doc || null
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
		doc: params.get('doc')
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
		doc: f.doc
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
