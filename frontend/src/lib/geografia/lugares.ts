/** Nomes de UFs e países para a interface. */

export const NOME_UF: Record<string, string> = {
	AC: 'Acre', AL: 'Alagoas', AM: 'Amazonas', AP: 'Amapá', BA: 'Bahia', CE: 'Ceará', DF: 'Distrito Federal',
	ES: 'Espírito Santo', GO: 'Goiás', MA: 'Maranhão', MG: 'Minas Gerais', MS: 'Mato Grosso do Sul',
	MT: 'Mato Grosso', PA: 'Pará', PB: 'Paraíba', PE: 'Pernambuco', PI: 'Piauí', PR: 'Paraná', RJ: 'Rio de Janeiro',
	RN: 'Rio Grande do Norte', RO: 'Rondônia', RR: 'Roraima', RS: 'Rio Grande do Sul', SC: 'Santa Catarina',
	SE: 'Sergipe', SP: 'São Paulo', TO: 'Tocantins'
};

let paises: Intl.DisplayNames | null = null;

/** Nome do país em português a partir do ISO-2 (`BR` → `Brasil`); o próprio código se o navegador não souber. */
export function nomePais(iso: string): string {
	try {
		paises ??= new Intl.DisplayNames(['pt-BR'], { type: 'region' });
		return paises.of(iso) ?? iso;
	} catch {
		return iso;
	}
}
