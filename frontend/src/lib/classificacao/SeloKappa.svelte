<script lang="ts">
	/**
	 * O kappa do modelo contra um codificador, ao lado da variável. Com hachura abaixo de `KAPPA_FRACO`
	 * (concordância só moderada): a distribuição da variável pede cuidado. A dica diz contra quem, com que n e o
	 * intervalo; um codificador de referência é sempre identificado como tal (não é uma pessoa).
	 */
	import { formatarDecimal, formatarInteiro } from '$lib/formato';
	import { KAPPA_FRACO, type Referencia } from './agregar';

	/** `nome`: o nome legível do codificador (`validacao/nomes.ts`), no lugar do id interno. */
	let { referencia, nome = null }: { referencia: Referencia; nome?: string | null } = $props();

	const m = $derived(referencia.metrica);
	const p = $derived(referencia.participante);
	const fraco = $derived(m.kappa === null || m.kappa < KAPPA_FRACO);
	const quem = $derived(p.tipo === 'humano' ? p.nome : `${nome ?? p.nome} (referência, não humano)`);
	const dica = $derived(
		m.kappa === null
			? `Kappa indefinido contra ${quem}: sem variação nas respostas (n = ${formatarInteiro(m.n)}).`
			: `Kappa ${formatarDecimal(m.kappa, 2)}` +
					(m.kappa_ic95 ? ` (IC 95%: ${formatarDecimal(m.kappa_ic95[0], 2)} a ${formatarDecimal(m.kappa_ic95[1], 2)})` : '') +
					` contra ${quem}, em ${formatarInteiro(m.n)} documentos da amostra.` +
					(fraco ? ' Concordância abaixo de 0,6: leia a distribuição com cuidado.' : '')
	);
</script>

<span class="selo" class:fraco class:referencia={p.tipo === 'referencia'} title={dica} data-testid="selo-kappa">
	<span aria-hidden="true">κ</span>
	<span class="visualmente-oculto">{dica}</span>
	<span aria-hidden="true">{m.kappa === null ? '—' : formatarDecimal(m.kappa, 2)}</span>
</span>

<style>
	.selo {
		display: inline-flex;
		gap: 0.25em;
		align-items: baseline;
		padding: 0.05rem 0.4rem;
		border: 1px solid var(--linha-forte);
		border-radius: 999px;
		font-family: var(--fonte-mono);
		font-size: 0.72rem;
		color: var(--texto-suave);
		white-space: nowrap;
	}

	.fraco {
		background: repeating-linear-gradient(135deg, transparent 0 3px, var(--linha) 3px 5px);
	}

	.referencia {
		border-style: dashed;
	}
</style>
