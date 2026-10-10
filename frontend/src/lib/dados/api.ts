import type { CodebookContrato } from '$lib/contrato/tipos';
import { aplicar, inicial, type EventoJob, type Job, type JobAoVivo } from '$lib/painel/job';
import type { Capacidades } from './fonte';
import { FonteEstatica } from './estatica';
import { pedirApi, urlDaApi } from './pedir';

/** As etapas que o painel roda como jobs. */
export type NomeEtapa = 'coleta' | 'topicos' | 'geografia' | 'redes' | 'classificacao';
export type EstadoEtapa = 'pendente' | 'em_dia' | 'incompleta' | 'desatualizada';

export interface EtapaDoProjeto {
	estado: EstadoEtapa;
	ultima: { fim: string; duracao_s: number; contagens: Record<string, number> } | null;
	amostra?: { n: number; codificados: number };
	/** Nas redes desatualizadas, o que mudou desde a última execução ("o pessoas.yaml", "a geografia"…). */
	mudou?: string[];
	/** No júri, o comando do próximo passo (o júri roda pela linha de comando, não como job). */
	proximo?: string;
	/** Nos tópicos em dia, os rótulos do `rotulos.yaml` (ou do editor) ainda não aplicados. */
	rotulos_pendentes?: number;
}
/** Uma etapa que roda fora deste painel (no terminal ou num notebook), que trava o projeto (`trava_etapas.py`). */
export interface EtapaEmAndamento {
	etapa: string;
	origem: 'painel' | 'terminal';
	pid: number;
	inicio: string;
	/** A frase do servidor: qual etapa, onde e desde quando. */
	mensagem: string;
}
/** O júri só vem quando o projeto tem `juri.membros` no `mapa.yaml`; `em_andamento`, quando uma etapa roda fora
 * do painel. */
export type EtapasDoProjeto = Record<NomeEtapa | 'validacao', EtapaDoProjeto> & {
	juri?: EtapaDoProjeto;
	em_andamento?: EtapaEmAndamento;
};

export interface Perfil {
	nome: string;
	descricao: string;
	ram_minima_gb: number;
	embeddings: string;
	classificacao: string;
	rotulos: string;
	download_gb: number;
}

export interface InfoModelos {
	ram_gb: number;
	perfil_sugerido: string;
	perfis: Perfil[];
	tamanhos_gb: Record<string, number>;
	ollama: { no_ar: boolean; erro: string | null };
	instalados: { nome: string; tamanho_gb: number }[];
	projeto: Record<'embeddings' | 'classificacao' | 'rotulos', { modelo: string; instalado: boolean; download_gb: number | null }>;
}

export interface Estimativa {
	modelo: string;
	documentos: number;
	classificados: number;
	pendentes: number;
	segundos_por_documento: number | null;
	estimativa_s: number | null;
}

export type Configuracao = Record<string, unknown> & {
	titulo: string;
	fontes: { scielo: { colecao: string; revistas: string[]; tipos: string[] } | null } & Record<string, unknown>;
	recorte: { anos: [number, number]; idioma_analise: string; idioma_exibicao: string };
	modelos: Record<'embeddings' | 'classificacao' | 'rotulos', { modelo: string } & Record<string, unknown>>;
};

export interface RevistaDoRetrato {
	issn: string;
	acronimo: string;
	titulo: string;
	areas: string[];
}

export type CodebookEditavel = Omit<CodebookContrato, 'versao_contrato' | 'hash'>;

/** Um rótulo escrito à mão, como vai para o `rotulos.yaml`. */
export interface RotuloManual {
	rotulo: string;
	descricao: string;
}
interface RotuloAtual {
	id: number;
	cor: string;
	rotulo: string;
	descricao: string;
	fonte: 'llm' | 'palavras' | 'manual';
	/** A entrada do `rotulos.yaml`, se houver. */
	manual: RotuloManual | null;
}
/** `GET /api/rotulos`: os rótulos dos tópicos e dos macrotemas, e quantas entradas do arquivo faltam aplicar. */
export interface RotulosDoProjeto {
	topicos: (RotuloAtual & { macro: number; palavras: string[]; n_nucleo: number })[];
	macrotemas: (RotuloAtual & { topicos: number[] })[];
	pendentes: number;
	/** No `PATCH`, os acentos que parecem perdidos (a gravação não é recusada por isso). */
	avisos?: string[];
}
/** O que muda no `rotulos.yaml`: por número, o rótulo novo, ou `null` para voltar ao do modelo. */
export interface MudancaDeRotulos {
	topicos?: Record<string, RotuloManual | null>;
	macrotemas?: Record<string, RotuloManual | null>;
}

const EVENTOS = ['estado', 'etapa', 'avanco', 'mensagem', 'resumo', 'erro', 'fim'] as const;

/**
 * Fonte do painel local (`mapa painel`), usada quando `manifesto.api` é verdadeiro.
 *
 * Lê o contrato como a `FonteEstatica` (o `./dados/` relativo aponta para `/dados/`) e, além disso, fala com a API
 * do painel: o estado das etapas, rodar uma etapa como job e acompanhá-la ao vivo, os modelos do Ollama, a
 * estimativa da classificação e a configuração e o codebook do projeto (com escrita).
 */
export class FonteApi extends FonteEstatica {
	override readonly capacidades: Capacidades = { escrita: true, aoVivo: true };

	etapas(): Promise<EtapasDoProjeto> {
		return pedirApi('api/projeto/etapas');
	}

	/** Só a etapa que roda fora do painel, sem o estado das etapas: a consulta leve que a vista Projeto repete. */
	emAndamento(): Promise<{ em_andamento: EtapaEmAndamento | null }> {
		return pedirApi('api/projeto/em-andamento');
	}

	iniciarEtapa(etapa: NomeEtapa, opcoes: Record<string, unknown> = {}): Promise<Job> {
		return pedirApi(`api/etapas/${etapa}`, { method: 'POST', body: JSON.stringify(opcoes) });
	}

	jobs(): Promise<Job[]> {
		return pedirApi('api/jobs');
	}

	job(id: string): Promise<Job> {
		return pedirApi(`api/jobs/${encodeURIComponent(id)}`);
	}

	cancelarJob(id: string): Promise<Job> {
		return pedirApi(`api/jobs/${encodeURIComponent(id)}`, { method: 'DELETE' });
	}

	/**
	 * Acompanha um job pelos eventos do servidor. O `EventSource` reconecta sozinho depois de uma queda e pede
	 * só o que perdeu (`Last-Event-ID`); o estado ignora eventos repetidos. Devolve a função que para de acompanhar.
	 */
	acompanhar(job: Job, aoMudar: (estado: JobAoVivo) => void): () => void {
		let estado = inicial(job);
		aoMudar(estado);
		const fonte = new EventSource(urlDaApi(`api/jobs/${encodeURIComponent(job.id)}/eventos`));
		const receber = (tipo: string) => (m: MessageEvent) => {
			const evento: EventoJob = { seq: Number(m.lastEventId), tipo, dados: JSON.parse(m.data) };
			estado = aplicar(estado, evento);
			aoMudar(estado);
			if (tipo === 'fim') fonte.close();
		};
		for (const tipo of EVENTOS) fonte.addEventListener(tipo, receber(tipo));
		return () => fonte.close();
	}

	modelos(): Promise<InfoModelos> {
		return pedirApi('api/modelos');
	}

	baixarModelo(modelo: string): Promise<Job> {
		return pedirApi('api/modelos/baixar', { method: 'POST', body: JSON.stringify({ modelo }) });
	}

	estimativaClassificacao(): Promise<Estimativa> {
		return pedirApi('api/estimativa/classificacao');
	}

	/** As revistas correntes do SciELO Brasil que casam com a busca, ou as dos ISSNs pedidos. */
	buscarRevistas(busca: string, issns: string[] = []): Promise<RevistaDoRetrato[]> {
		const q = issns.length ? `issn=${encodeURIComponent(issns.join(','))}` : `busca=${encodeURIComponent(busca)}`;
		return pedirApi(`api/revistas?${q}`);
	}

	/** Sorteia a amostra de validação (como `mapa validar amostra`). */
	sortearAmostra(n?: number, refazer = false): Promise<{ n: number; estratificar_por: string; estratos: number }> {
		return pedirApi('api/validacao/amostra', { method: 'POST', body: JSON.stringify({ n, refazer }) });
	}

	configuracao(): Promise<Configuracao> {
		return pedirApi('api/configuracao');
	}

	mudarConfiguracao(parcial: Record<string, unknown>): Promise<Configuracao> {
		return pedirApi('api/configuracao', { method: 'PATCH', body: JSON.stringify(parcial) });
	}

	codebookEditavel(): Promise<CodebookEditavel & { hash: string }> {
		return pedirApi('api/codebook');
	}

	salvarCodebook(codebook: CodebookEditavel): Promise<CodebookEditavel & { hash: string }> {
		return pedirApi('api/codebook', { method: 'PUT', body: JSON.stringify(codebook) });
	}

	rotulos(): Promise<RotulosDoProjeto> {
		return pedirApi('api/rotulos');
	}

	/** Grava as mudanças no `rotulos.yaml`; a etapa de tópicos (`aplicar_rotulos`) as aplica. */
	mudarRotulos(mudanca: MudancaDeRotulos): Promise<RotulosDoProjeto> {
		return pedirApi('api/rotulos', { method: 'PATCH', body: JSON.stringify(mudanca) });
	}
}
