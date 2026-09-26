/**
 * Camada de dados: de onde a interface lê o contrato.
 *
 * Toda vista fala com uma `FonteDeDados`, nunca com `fetch` direto. Hoje há duas:
 *
 * - `FonteEstatica`: lê `./dados/*.json` relativo à página. É o modo do site publicado e,
 *   por enquanto, também do painel local.
 * - `FonteApi`: a do painel local (`mapa painel`), onde `manifesto.api` é verdadeiro. Por
 *   enquanto só herda a estática e declara `escrita: true`; os métodos de escrita chegam
 *   com a API.
 *
 * O manifesto é sempre lido primeiro. Os outros arquivos só são pedidos se estiverem em
 * `manifesto.arquivos`; os ausentes dão `null` sem requisição. Um projeto recém-criado
 * (`mapa novo`) tem só o manifesto, e a interface precisa funcionar assim.
 */
import type {
	Afiliacoes,
	Classificacoes,
	CodebookContrato,
	Detalhe,
	Documentos,
	Manifesto,
	Revistas,
	Topicos,
	Validacao
} from '$lib/contrato/tipos';

/** O que a fonte permite além de ler. A interface esconde o que não houver. */
export interface Capacidades {
	/** Pode gravar (codebook, codificação humana, configuração). Só no painel local. */
	escrita: boolean;
	/** Recebe atualizações enquanto o pipeline roda. Chega com a API. */
	aoVivo: boolean;
}

/** Nomes dos arquivos do contrato, como aparecem em `manifesto.arquivos`. */
export type NomeArquivo =
	| 'manifesto'
	| 'revistas'
	| 'documentos'
	| 'afiliacoes'
	| 'topicos'
	| 'codebook'
	| 'classificacoes'
	| 'validacao'
	| 'agregados'
	| 'detalhes';

export interface FonteDeDados {
	readonly capacidades: Capacidades;
	manifesto(): Promise<Manifesto>;
	/** `true` se o arquivo está em `manifesto.arquivos`. */
	tem(arquivo: NomeArquivo): Promise<boolean>;
	revistas(): Promise<Revistas | null>;
	documentos(): Promise<Documentos | null>;
	afiliacoes(): Promise<Afiliacoes | null>;
	topicos(): Promise<Topicos | null>;
	codebook(): Promise<CodebookContrato | null>;
	classificacoes(): Promise<Classificacoes | null>;
	validacao(): Promise<Validacao | null>;
	/** Resumo, autores, licença e evidências de um documento, ou `null` se não houver. */
	detalhe(id: string): Promise<Detalhe | null>;
}

/** Versão maior do contrato que esta interface entende. */
export const VERSAO_MAIOR_CONTRATO = '1';

export class ErroDeDados extends Error {
	readonly url: string;
	readonly status: number | null;

	constructor(mensagem: string, url: string, status: number | null = null) {
		super(mensagem);
		this.name = 'ErroDeDados';
		this.url = url;
		this.status = status;
	}
}
