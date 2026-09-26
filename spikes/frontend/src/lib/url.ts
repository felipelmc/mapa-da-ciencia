/**
 * Lê os parâmetros que vêm depois do `?` dentro do hash.
 * Ex.: `#/mapa?anos=2012-2020&cor=topico` -> { anos: '2012-2020', cor: 'topico' }.
 */
export function parametrosDoHash(url: URL): URLSearchParams {
	const i = url.hash.indexOf('?');
	return new URLSearchParams(i >= 0 ? url.hash.slice(i + 1) : '');
}
