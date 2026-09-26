/**
 * Leitura e escrita dos filtros no hash, que é a única fonte da verdade (ADR 0002): as vistas leem daqui e
 * mudam o estado mudando a URL. Um link copiado reproduz exatamente o que estava na tela.
 */
import { goto } from '$app/navigation';
import { page } from '$app/state';
import { escreverFiltros, lerFiltros, lerHash, normalizarFiltros, rota, type Filtros } from './url';

/** Os filtros da página atual. Chame dentro de um `$derived` para acompanhar a URL. */
export function filtrosDaPagina(): Filtros {
	return lerFiltros(lerHash(page.url.hash).params);
}

/**
 * Muda parte dos filtros e grava no hash. `substituir` troca a entrada atual do histórico em vez de criar
 * outra: é o que se quer para a câmera e o play da linha do tempo, que mudam muitas vezes por segundo.
 *
 * Com `em`, só age se a página ainda for aquela rota: um aviso atrasado (a câmera parou de mexer) que chegue
 * durante a navegação para outra seção não pode puxar a pessoa de volta. Sem mudança, não navega.
 */
export async function mudarFiltros(
	parcial: Partial<Filtros>,
	{ substituir = false, em }: { substituir?: boolean; em?: string } = {}
): Promise<void> {
	const { caminho, params } = lerHash(page.url.hash);
	if (em && caminho !== em) return;
	const novos = escreverFiltros(normalizarFiltros({ ...lerFiltros(params), ...parcial }));
	if (novos.toString() === escreverFiltros(lerFiltros(params)).toString()) return;
	await goto(rota(caminho, novos), { replaceState: substituir, noScroll: true, keepFocus: true });
}
