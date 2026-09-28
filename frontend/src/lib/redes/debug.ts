/**
 * O gancho de depuração da vista Redes (`window.__redesDebug`): os testes e2e leem daqui o que foi desenhado e
 * quantas arestas o recorte deixou, e o console mostra o mesmo a quem estiver depurando.
 */
export function debugRedes(): RedesDebug {
	window.__redesDebug ??= {
		modo: '',
		nos: 0,
		arestas: 0,
		arestasNoRecorte: 0,
		desenhado: false,
		msAtePrimeiroDesenho: null,
		selecionado: null
	};
	return window.__redesDebug;
}

/** Recomeça o estado para um modo novo (antes de os filhos desenharem). */
export function recomecarDebug(modo: string): RedesDebug {
	return Object.assign(debugRedes(), {
		modo,
		nos: 0,
		arestas: 0,
		arestasNoRecorte: 0,
		desenhado: false,
		msAtePrimeiroDesenho: null,
		selecionado: null,
		posicaoNaTela: undefined
	});
}
