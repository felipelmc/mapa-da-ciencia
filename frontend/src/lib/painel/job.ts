/**
 * O estado de um job ao vivo, montado a partir dos eventos do fluxo SSE (`GET /api/jobs/{id}/eventos`).
 *
 * Cada evento tem um número de sequência. Ao reconectar, o navegador pede os eventos depois do último que viu
 * (`Last-Event-ID`); `aplicar` ainda ignora qualquer evento repetido, então o estado nunca conta duas vezes.
 */

export type EstadoJob = 'na_fila' | 'rodando' | 'concluido' | 'falhou' | 'cancelado';

export interface Job {
	id: string;
	etapa: string;
	opcoes: Record<string, unknown>;
	estado: EstadoJob;
	criado: string;
	inicio: string | null;
	fim: string | null;
	resumo: ({ frase: string } & Record<string, unknown>) | null;
	erro: string | null;
}

export interface EventoJob {
	seq: number;
	tipo: string;
	dados: Record<string, unknown>;
}

export interface JobAoVivo {
	id: string;
	etapa: string;
	estado: EstadoJob;
	/** A parte da etapa em andamento ("Embeddings", "Classificando"...). */
	passo: string | null;
	feito: number;
	total: number | null;
	/** As últimas mensagens, da mais antiga à mais nova. */
	mensagens: string[];
	erro: string | null;
	resumo: string | null;
	ultimoSeq: number;
	terminado: boolean;
}

export const MENSAGENS_GUARDADAS = 50;

export function inicial(job: Pick<Job, 'id' | 'etapa' | 'estado'>): JobAoVivo {
	return {
		id: job.id,
		etapa: job.etapa,
		estado: job.estado,
		passo: null,
		feito: 0,
		total: null,
		mensagens: [],
		erro: null,
		resumo: null,
		ultimoSeq: 0,
		terminado: ['concluido', 'falhou', 'cancelado'].includes(job.estado)
	};
}

/** O estado depois de um evento (um evento já visto não muda nada). */
export function aplicar(e: JobAoVivo, ev: EventoJob): JobAoVivo {
	if (ev.seq <= e.ultimoSeq) return e;
	const d = ev.dados;
	const novo = { ...e, ultimoSeq: ev.seq };
	switch (ev.tipo) {
		case 'estado':
			novo.estado = d.estado as EstadoJob;
			break;
		case 'etapa':
			novo.passo = String(d.nome);
			novo.total = (d.total as number | null) ?? null;
			novo.feito = 0;
			break;
		case 'avanco':
			novo.passo = String(d.etapa);
			novo.feito = Number(d.feito);
			novo.total = (d.total as number | null) ?? null;
			break;
		case 'mensagem':
			novo.mensagens = [...e.mensagens, String(d.texto)].slice(-MENSAGENS_GUARDADAS);
			break;
		case 'erro':
			novo.erro = String(d.mensagem);
			break;
		case 'resumo':
			novo.resumo = typeof d.frase === 'string' ? d.frase : null;
			break;
		case 'fim':
			novo.estado = d.estado as EstadoJob;
			novo.terminado = true;
			break;
	}
	return novo;
}

/** A fração feita (0 a 1), ou `null` quando a etapa não sabe o total. */
export function fracao(e: Pick<JobAoVivo, 'feito' | 'total'>): number | null {
	return e.total ? Math.min(1, e.feito / e.total) : null;
}
