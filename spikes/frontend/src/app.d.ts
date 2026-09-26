// Tipos globais do spike. Ver https://svelte.dev/docs/kit/types#app.d.ts
import type createScatterplot from 'regl-scatterplot';

type Scatterplot = ReturnType<typeof createScatterplot>;

declare global {
	namespace App {}

	interface RotaDebug {
		href: string;
		pathname: string;
		search: string;
		hash: string;
		routeId: string | null;
		/** `page.url.searchParams`, como o SvelteKit entrega. */
		searchParams: Record<string, string>;
		/** Parâmetros lidos à mão da parte `?...` do hash. */
		hashParams: Record<string, string>;
		hrefInicio: string;
		hrefMapa: string;
		atualizacoes: number;
	}

	interface MapaDebug {
		montagens: number;
		pontos: number;
		clusters: number;
		/** Índice do cluster de cada ponto, na ordem enviada ao `draw()`. */
		clusterDoPonto: number[];
		desenhado: boolean;
		/** Do início do `onMount` até o `draw()` resolver + 2 quadros. */
		msAtePrimeiroDesenho: number | null;
		/** `performance.now()` no mesmo instante (relativo ao início da navegação). */
		msDesdeNavegacao: number | null;
		eventosDraw: number;
		eventosSelect: number;
		eventosFilter: number;
		eventosLassoEnd: number;
		ultimaSelecao: number[];
		renderer: string | null;
		erro: string | null;
		scatterplot: Scatterplot | null;
	}

	interface Window {
		__rotaDebug?: RotaDebug;
		__mapaDebug?: MapaDebug;
	}
}

export {};
