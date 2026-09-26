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
		/** Zoom atual da câmera (1 = inicial). */
		zoom?: number;
		/** Contornos desenhados (anéis). */
		anotacoes?: number;
		/** Tempo acumulado até cada etapa do primeiro desenho, em ms. */
		etapasMs?: Record<string, number>;
		/** Seleciona por um polígono em coordenadas NDC, como se fosse um laço desenhado. */
		laco?: (vertices: [number, number][]) => void;
	}

	interface Window {
		__mapaDebug?: MapaDebug;
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
