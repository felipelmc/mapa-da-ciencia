import type { Capacidades } from './fonte';
import { FonteEstatica } from './estatica';

/**
 * Fonte do painel local (`mapa painel`), usada quando `manifesto.api` é verdadeiro.
 *
 * O servidor Python serve o app em `/`, os dados em `/dados/` e a API em `/api/`. Por
 * enquanto a leitura é a mesma da `FonteEstatica` (o `./dados/` relativo já aponta para
 * `/dados/`); os métodos de escrita e as atualizações ao vivo chegam com a API.
 */
export class FonteApi extends FonteEstatica {
	override readonly capacidades: Capacidades = { escrita: true, aoVivo: false };
}
