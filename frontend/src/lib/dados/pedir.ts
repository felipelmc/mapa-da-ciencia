/**
 * Pedidos à API do painel local (`/api/...`), com os caminhos relativos à página (funcionam na raiz e num
 * subcaminho) e os erros da API como `ErroDaApi`, com a mensagem que o servidor escreveu.
 */

export class ErroDaApi extends Error {
	readonly status: number;
	readonly problemas: string[];
	readonly detalhe: unknown;

	constructor(mensagem: string, status: number, problemas: string[] = [], detalhe: unknown = null) {
		super(mensagem);
		this.name = 'ErroDaApi';
		this.status = status;
		this.problemas = problemas;
		this.detalhe = detalhe;
	}
}

export const urlDaApi = (caminho: string) => new URL(caminho, document.baseURI).toString();

export async function pedirApi<T>(caminho: string, init?: RequestInit): Promise<T> {
	const r = await fetch(urlDaApi(caminho), {
		...init,
		headers: { 'Content-Type': 'application/json', ...init?.headers }
	});
	if (!r.ok) {
		const corpo = await r.json().catch(() => null);
		const detalhe = corpo?.detail;
		const problemas: string[] = Array.isArray(detalhe?.problemas) ? detalhe.problemas : [];
		const mensagem =
			typeof detalhe === 'string'
				? detalhe
				: (detalhe?.mensagem ?? (problemas.join('; ') || r.statusText));
		throw new ErroDaApi(mensagem, r.status, problemas, detalhe);
	}
	return r.json();
}
