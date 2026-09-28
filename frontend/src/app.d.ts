// Tipos globais do app. Ver https://svelte.dev/docs/kit/types#app.d.ts
declare global {
	/** Estado do mapa exposto para os testes (Playwright) e para depuração no console. */
	interface MapaDebug {
		pontos: number;
		desenhado: boolean;
		msAtePrimeiroDesenho: number | null;
		visiveis: number;
		selecionados: number[];
		destaque: number | null;
		modoLaco: boolean;
		renderer: string | null;
		erro: string | null;
		/** Posição de um ponto na tela (px, relativa ao canvas), para os testes clicarem nele. */
		posicaoNaTela?: (i: number) => [number, number] | undefined;
		/** Laços terminados (evento lassoEnd do gráfico). */
		lacos?: number;
		/** Zoom atual da câmera (1 = inicial). */
		zoom?: number;
		/** Contornos desenhados (anéis). */
		anotacoes?: number;
		/** Tempo acumulado até cada etapa do primeiro desenho, em ms. */
		etapasMs?: Record<string, number>;
		/** Seleciona por um polígono em coordenadas NDC, como se fosse um laço desenhado. */
		laco?: (vertices: [number, number][]) => void;
	}

	/** Estado da vista Redes exposto para os testes e para depuração no console. */
	interface RedesDebug {
		/** A rede na tela (`coautoria`, `instituicoes`, `estados` ou `citacoes`). */
		modo: string;
		/** Nós desenhados: pessoas ou instituições com posição, lugares, obras do cânone. */
		nos: number;
		/** Arestas do corpus inteiro (pares, ou citações internas). */
		arestas: number;
		/** Arestas com ao menos um documento no recorte (nas citações, com as duas pontas nele). */
		arestasNoRecorte: number;
		desenhado: boolean;
		msAtePrimeiroDesenho: number | null;
		/** Id do nó aberto no cartão. */
		selecionado: string | null;
		/** Posição de um nó na tela (px, relativa ao canvas), pelo id, para os testes clicarem nele. */
		posicaoNaTela?: (id: string) => [number, number] | undefined;
	}

	interface Window {
		__mapaDebug?: MapaDebug;
		__redesDebug?: RedesDebug;
	}

	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
