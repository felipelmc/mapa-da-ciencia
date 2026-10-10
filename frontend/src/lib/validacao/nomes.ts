/**
 * Os nomes dos participantes da validação para quem lê. Os ids reservados do júri (`juri`, `juri-r1`,
 * `juri-supervisor`) e os modelos grandes que codificaram como referência ou supervisionaram o júri (`claude-opus`,
 * `opus-supervisor`) são ids internos: viram um nome legível. Modelos locais e pessoas ficam com o nome deles.
 */
import type { Validacao } from '$lib/contrato/tipos';

const DO_JURI: Record<string, string> = {
	juri: 'Júri de modelos',
	'juri-r1': '1ª votação do júri',
	'juri-supervisor': 'Júri com supervisor'
};

const FAMILIAS: Record<string, string> = { claude: 'Claude', gpt: 'GPT', gemini: 'Gemini', llama: 'Llama' };
const daFamilia = (familia: string | null | undefined) =>
	familia ? (FAMILIAS[familia] ?? familia.charAt(0).toUpperCase() + familia.slice(1)) : null;

/**
 * O nome legível de cada participante, sem o papel ("Claude", e não "Claude (referência)": quem mostra diz o papel).
 * Se duas referências ganhariam o mesmo nome (duas da mesma família), as duas ficam com o id, para não se confundirem.
 */
export function nomesLegiveis(v: Pick<Validacao, 'codificadores' | 'juri'>): Map<string, string> {
	const nomes = new Map<string, string>();
	const referencias = (v.codificadores ?? []).filter((p) => p.tipo === 'referencia' && !DO_JURI[p.nome]);
	const daReferencia = referencias.map((p) => daFamilia(p.familia) ?? p.nome);
	referencias.forEach((p, i) => nomes.set(p.nome, daReferencia.indexOf(daReferencia[i]) === daReferencia.lastIndexOf(daReferencia[i]) ? daReferencia[i] : p.nome));
	// os ids do júri são reservados: valem mesmo quando o participante não está na lista (uma frase que o cita)
	for (const [id, nome] of Object.entries(DO_JURI)) nomes.set(id, nome);
	if (v.juri?.supervisor) nomes.set(v.juri.supervisor, daFamilia(v.juri.familia_supervisor) ?? v.juri.supervisor);
	return nomes;
}
