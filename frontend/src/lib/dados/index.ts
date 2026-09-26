import type { Manifesto } from '$lib/contrato/tipos';
import { FonteApi } from './api';
import { FonteEstatica, type OpcoesFonte } from './estatica';
import type { FonteDeDados } from './fonte';

export { FonteApi } from './api';
export { FonteEstatica, type OpcoesFonte } from './estatica';
export { ErroDeDados, type Capacidades, type FonteDeDados, type NomeArquivo } from './fonte';
export { fragmentoDe, N_FRAGMENTOS } from './fragmentos';

/**
 * Lê o manifesto e escolhe a fonte pelo modo: `manifesto.api` verdadeiro → `FonteApi`
 * (painel local); falso → `FonteEstatica` (site publicado).
 */
export async function abrirFonte(
	opcoes: OpcoesFonte = {}
): Promise<{ fonte: FonteDeDados; manifesto: Manifesto }> {
	const manifesto = await new FonteEstatica(opcoes).manifesto();
	const Classe = manifesto.api ? FonteApi : FonteEstatica;
	return { fonte: new Classe({ ...opcoes, manifesto }), manifesto };
}
