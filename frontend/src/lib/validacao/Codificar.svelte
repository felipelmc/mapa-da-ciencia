<script lang="ts">
	/**
	 * A codificação da amostra, uma ficha por vez, feita para o teclado. É cega: a ficha mostra só o título, o
	 * resumo e o codebook, nunca a resposta de um modelo.
	 *
	 * Teclas (fora de um campo de texto): 1–9 escolhe a opção da variável atual (e passa para a próxima; na múltipla,
	 * liga ou desliga); ↓ e ↑ trocam de variável; Enter confirma a ficha; ← e → trocam de ficha; S marca a
	 * resposta como incerta; N abre a nota; E usa o trecho selecionado no resumo como evidência; D mostra as
	 * definições; ? mostra a ajuda. Numa variável de texto, a resposta é digitada, e Enter passa adiante.
	 *
	 * Cada mudança é gravada sozinha (ver `Gravador`): primeiro no navegador, depois no painel.
	 */
	import { onMount, tick } from 'svelte';
	import { usarProjeto } from '$lib/dados/contexto';
	import { formatarInteiro } from '$lib/formato';
	import { Gravador, type Fila, type RespostaVariavel } from './api';
	import { escolher, faltando, ondeRetomar, opcoesDe, paraGravar, respondida, RESPOSTA_VAZIA } from './ficha';

	let { fila, aoTrocar }: { fila: Fila; aoTrocar: () => void } = $props();

	const codebook = $derived(fila.codebook);
	const vars = $derived(codebook.variaveis);
	let pendentes = $state(0);
	let erro = $state<string | null>(null);
	const { manifesto } = usarProjeto();
	const gravador = $derived(
		new Gravador(manifesto.projeto.nome, fila.codificador, (n, e) => ((pendentes = n), (erro = e)))
	);

	// respostas de cada ficha: as do painel, com o que ficou pendente neste navegador por cima
	function inicial() {
		const pend = new Gravador(manifesto.projeto.nome, fila.codificador).pendencias();
		const respostas: Record<string, Record<string, RespostaVariavel>> = {};
		const completas = new Set<string>();
		for (const f of fila.fila) {
			respostas[f.doc] = { ...f.respostas, ...(pend[f.doc]?.respostas ?? {}) };
			if (f.completa || pend[f.doc]?.completa) completas.add(f.doc);
		}
		const inicio = ondeRetomar(fila.fila.map((f) => ({ completa: completas.has(f.doc) })));
		return { respostas, completas, inicio };
	}
	// o estado parte da fila recebida; outro codificador remonta o componente (ver a página)
	const comeco = inicial();
	let respostas = $state(comeco.respostas);
	let completas = $state(comeco.completas);
	let idx = $state(comeco.inicio);
	let varIdx = $state(0);
	let definicoes = $state(false);
	let ajuda = $state(false);
	let notaAberta = $state(false);
	let aviso = $state<string | null>(null);
	let cartao = $state<HTMLElement | null>(null);

	const ficha = $derived(fila.fila[idx]);
	const v = $derived(vars[varIdx]);
	const atual = $derived(respostas[ficha.doc] ?? {});
	const nCompletas = $derived(completas.size);
	const terminou = $derived(nCompletas === fila.fila.length);

	onMount(() => {
		void gravador.enviar(); // reenvia o que ficou pendente numa sessão anterior
		const falta = faltando(codebook, respostas[ficha.doc] ?? {});
		void focarVariavel(falta.length ? vars.findIndex((x) => x.id === falta[0]) : 0);
	});
	$effect(() => {
		const voltar = () => gravador.enviar();
		window.addEventListener('online', voltar);
		return () => window.removeEventListener('online', voltar);
	});
	$effect(() => {
		// um reload ou uma aba fechada logo depois de uma mudança: grava já o que estava esperando o atraso
		const sair = () => descarregar();
		window.addEventListener('pagehide', sair);
		return () => window.removeEventListener('pagehide', sair);
	});

	// ---- gravação (com um pequeno atraso, e na hora ao trocar de ficha ou confirmar)
	let espera: ReturnType<typeof setTimeout> | null = null;
	let aGravar: string | null = null;
	function gravar(doc: string, completa: boolean) {
		if (espera) clearTimeout(espera);
		espera = null;
		aGravar = null;
		void gravador.gravar(doc, paraGravar(codebook, respostas[doc] ?? {}), completa);
	}
	function agendar(doc: string) {
		if (espera) clearTimeout(espera);
		aGravar = doc;
		espera = setTimeout(() => gravar(doc, false), 300);
	}
	function descarregar() {
		if (aGravar) gravar(aGravar, false);
	}

	function mudar(id: string, r: RespostaVariavel) {
		respostas[ficha.doc] = { ...atual, [id]: r };
		aviso = null;
		agendar(ficha.doc);
	}

	// ---- navegação
	async function focarVariavel(i: number) {
		varIdx = Math.max(0, Math.min(vars.length - 1, i));
		notaAberta = false;
		await tick();
		if (vars[varIdx].tipo === 'texto') document.getElementById(`texto-${vars[varIdx].id}`)?.focus();
		else cartao?.focus();
		document.getElementById(`variavel-${vars[varIdx].id}`)?.scrollIntoView({ block: 'nearest' });
	}
	async function irPara(i: number) {
		if (i < 0 || i >= fila.fila.length) return;
		descarregar();
		idx = i;
		aviso = null;
		const falta = faltando(codebook, respostas[fila.fila[i].doc] ?? {});
		await focarVariavel(falta.length ? vars.findIndex((x) => x.id === falta[0]) : 0);
		cartao?.scrollIntoView({ block: 'start' });
	}
	function confirmar() {
		const falta = faltando(codebook, atual);
		if (falta.length) {
			aviso = `Falta responder: ${falta.map((id) => vars.find((x) => x.id === id)?.rotulo).join(', ')}.`;
			void focarVariavel(vars.findIndex((x) => x.id === falta[0]));
			return;
		}
		gravar(ficha.doc, true);
		completas = new Set([...completas, ficha.doc]);
		if (idx < fila.fila.length - 1) void irPara(idx + 1);
		else aviso = 'Última ficha confirmada.';
	}

	function escolherOpcao(n: number) {
		if (v.tipo === 'texto') return void focarVariavel(varIdx);
		if (!opcoesDe(v)[n]) return;
		mudar(v.id, escolher(v, atual[v.id], n));
		if (v.tipo !== 'multipla') void focarVariavel(varIdx + 1);
	}

	function evidenciaSelecionada() {
		const trecho = window.getSelection()?.toString().replace(/\s+/g, ' ').trim() ?? '';
		if (!trecho) {
			aviso = 'Selecione um trecho do resumo com o mouse e aperte E.';
			return;
		}
		mudar(v.id, { ...(atual[v.id] ?? RESPOSTA_VAZIA), evidencia: trecho.slice(0, 200) });
	}

	function tecla(e: KeyboardEvent) {
		const alvo = e.target as HTMLElement;
		if (alvo.closest('input, textarea')) {
			if (e.key === 'Escape') {
				e.preventDefault();
				notaAberta = false;
				cartao?.focus();
			} else if (e.key === 'Enter' && alvo.dataset.papel) {
				e.preventDefault();
				// no texto, Enter passa adiante; na última variável, confirma a ficha
				if (alvo.dataset.papel === 'texto') varIdx === vars.length - 1 ? confirmar() : void focarVariavel(varIdx + 1);
				else (notaAberta = false), cartao?.focus();
			}
			return;
		}
		if (e.metaKey || e.ctrlKey || e.altKey || !cartao) return;
		if (alvo !== document.body && !cartao.contains(alvo) && e.key !== '?') return;
		// num botão (chegou-se a ele pelo Tab), Enter e espaço acionam o botão, e não "confirmar a ficha"
		if ((e.key === 'Enter' || e.key === ' ') && alvo.closest('button, a')) return;
		// Tab fica com o navegador: percorre os botões da ficha e sai dela (para o rodapé e o trilho), senão o
		// teclado nunca deixaria a ficha
		const acoes: Record<string, () => void> = {
			ArrowDown: () => void focarVariavel(varIdx + 1),
			ArrowUp: () => void focarVariavel(varIdx - 1),
			ArrowRight: () => void irPara(idx + 1),
			ArrowLeft: () => void irPara(idx - 1),
			Enter: confirmar,
			s: () => mudar(v.id, { ...(atual[v.id] ?? RESPOSTA_VAZIA), incerto: !atual[v.id]?.incerto }),
			n: () => {
				notaAberta = true;
				void tick().then(() => document.getElementById(`nota-${v.id}`)?.focus());
			},
			e: evidenciaSelecionada,
			d: () => (definicoes = !definicoes),
			'?': () => (ajuda = !ajuda),
			Escape: () => (ajuda = false)
		};
		const acao = /^[1-9]$/.test(e.key) ? () => escolherOpcao(Number(e.key) - 1) : acoes[e.key.length === 1 ? e.key.toLowerCase() : e.key];
		if (!acao) return;
		e.preventDefault();
		acao();
	}

	const rotuloValor = (id: string) => {
		const x = vars.find((y) => y.id === id)!;
		const r = atual[id];
		if (!respondida(x, r)) return '';
		if (x.tipo === 'booleana') return r.valor ? 'Sim' : 'Não';
		if (x.tipo === 'texto') return String(r.valor);
		const nomes = new Map(opcoesDe(x).map((o) => [o.valor, o.rotulo]));
		return Array.isArray(r.valor) ? r.valor.map((c) => nomes.get(c)).join(' + ') || 'nenhuma' : (nomes.get(r.valor as string) ?? '');
	};
</script>

<svelte:window onkeydown={tecla} />

<div class="codificar">
	<header class="topo">
		<div>
			<p class="rotulo-miudo">Codificação cega · {fila.codificador}</p>
			<h1>Codificar a amostra</h1>
		</div>
		<div class="progresso" data-testid="progresso">
			<p>
				<strong>{formatarInteiro(nCompletas)}</strong> de {formatarInteiro(fila.fila.length)} fichas completas · ficha
				{formatarInteiro(idx + 1)}
			</p>
			<progress max={fila.fila.length} value={nCompletas}></progress>
			<p class="estado" aria-live="polite" data-testid="estado-gravacao">
				{#if erro}{erro}{:else if pendentes}Gravando…{:else}Tudo gravado.{/if}
			</p>
		</div>
	</header>

	{#if terminou}
		<p class="parabens" role="status">
			Todas as fichas estão completas. As métricas estão na vista Validação; você ainda pode revisar qualquer ficha.
		</p>
	{/if}

	<article class="ficha" tabindex="-1" bind:this={cartao} aria-label="Ficha {idx + 1}" data-testid="ficha" data-doc={ficha.doc}>
		<section class="texto" aria-label="Documento">
			<h2>{ficha.titulo ?? '(sem título)'}</h2>
			<p class="resumo" lang={ficha.idioma}>{ficha.resumo}</p>
			<p class="dica">Selecione um trecho e aperte <kbd>E</kbd> para usá-lo como evidência da variável atual.</p>
		</section>

		<section class="variaveis" aria-label="Variáveis do codebook">
			{#each vars as x, i (x.id)}
				{@const r = atual[x.id]}
				<div
					class="variavel"
					class:atual={i === varIdx}
					class:respondida={respondida(x, r)}
					id="variavel-{x.id}"
					data-testid="variavel-ficha"
					data-respondida={respondida(x, r) ? 'sim' : 'nao'}
				>
					<button type="button" class="cabeca" onclick={() => focarVariavel(i)}>
						<span class="nome">{x.rotulo}</span>
						<span class="valor" data-testid="valor-ficha">{rotuloValor(x.id)}</span>
						{#if r?.incerto}<span class="incerto">incerto</span>{/if}
					</button>
					{#if i === varIdx}
						<p class="pergunta">{x.pergunta}</p>
						{#if x.tipo === 'texto'}
							<input
								id="texto-{x.id}"
								data-papel="texto"
								type="text"
								value={typeof r?.valor === 'string' ? r.valor : ''}
								oninput={(e) => mudar(x.id, { ...(r ?? RESPOSTA_VAZIA), valor: e.currentTarget.value })}
								placeholder="Digite e aperte Enter"
								aria-label={x.pergunta}
							/>
						{:else}
							<ol class="opcoes">
								{#each opcoesDe(x) as o, n (String(o.valor))}
									{@const marcada = Array.isArray(r?.valor) ? r.valor.includes(o.valor as string) : r?.valor === o.valor}
									<li>
										<!-- com o mouse, o foco volta à ficha: o Enter seguinte confirma (e não desmarca a opção);
										     quem chegou ao botão pelo Tab continua com o Enter do botão -->
										<button
											type="button"
											aria-pressed={marcada}
											onclick={(ev) => {
												varIdx = i;
												escolherOpcao(n);
												if (ev.detail > 0) cartao?.focus();
											}}
										>
											<kbd>{n + 1}</kbd>{o.rotulo}
										</button>
										{#if definicoes && o.definicao}<p class="definicao">{o.definicao}</p>{/if}
									</li>
								{/each}
							</ol>
						{/if}
						{#if r?.evidencia}
							<p class="evidencia">
								Evidência: «{r.evidencia}»
								<button type="button" class="limpar" onclick={() => mudar(x.id, { ...r, evidencia: '' })} aria-label="Tirar a evidência">×</button>
							</p>
						{/if}
						{#if notaAberta || r?.nota}
							<input
								id="nota-{x.id}"
								data-papel="nota"
								class="nota"
								type="text"
								value={r?.nota ?? ''}
								maxlength="2000"
								oninput={(e) => mudar(x.id, { ...(r ?? RESPOSTA_VAZIA), nota: e.currentTarget.value })}
								placeholder="Nota (Enter para voltar)"
								aria-label="Nota sobre {x.rotulo}"
							/>
						{/if}
					{/if}
				</div>
			{/each}
			{#if aviso}<p class="aviso" role="alert">{aviso}</p>{/if}
			<div class="acoes">
				<button type="button" onclick={() => irPara(idx - 1)} disabled={idx === 0}>← Anterior</button>
				<button type="button" class="confirmar" onclick={confirmar}>Confirmar a ficha <kbd>Enter</kbd></button>
				<button type="button" onclick={() => irPara(idx + 1)} disabled={idx === fila.fila.length - 1}>Próxima →</button>
			</div>
		</section>
	</article>

	<footer class="rodape">
		<p>
			<kbd>1</kbd>–<kbd>9</kbd> escolhe · <kbd>↓</kbd> próxima variável · <kbd>Enter</kbd> confirma ·
			<kbd>←</kbd> <kbd>→</kbd> fichas · <kbd>S</kbd> incerto · <kbd>N</kbd> nota · <kbd>E</kbd> evidência ·
			<kbd>D</kbd> definições · <kbd>?</kbd> ajuda
		</p>
		<button type="button" class="trocar" onclick={aoTrocar}>Trocar de codificador</button>
	</footer>

	{#if ajuda}
		<div class="ajuda" role="dialog" aria-modal="false" aria-labelledby="titulo-ajuda" data-testid="ajuda-codificar">
			<h2 id="titulo-ajuda">Como codificar</h2>
			<dl>
				<dt><kbd>1</kbd>–<kbd>9</kbd></dt><dd>Escolhe a opção da variável atual e passa para a próxima. Na múltipla escolha, liga ou desliga a opção.</dd>
				<dt><kbd>↓</kbd> <kbd>↑</kbd></dt><dd>Troca de variável.</dd>
				<dt><kbd>Enter</kbd></dt><dd>Confirma a ficha (todas as variáveis respondidas) e abre a próxima.</dd>
				<dt><kbd>←</kbd> <kbd>→</kbd></dt><dd>Ficha anterior e próxima, sem confirmar.</dd>
				<dt><kbd>S</kbd></dt><dd>Marca a resposta como incerta (ou desmarca).</dd>
				<dt><kbd>N</kbd></dt><dd>Escreve uma nota sobre a resposta.</dd>
				<dt><kbd>E</kbd></dt><dd>Usa o trecho selecionado no resumo como evidência.</dd>
				<dt><kbd>D</kbd></dt><dd>Mostra ou esconde as definições das categorias.</dd>
				<dt><kbd>Esc</kbd></dt><dd>Sai de um campo de texto ou fecha esta ajuda.</dd>
				<dt><kbd>Tab</kbd></dt><dd>Percorre os botões da ficha e sai dela, para “Trocar de codificador” e o menu das seções.</dd>
			</dl>
			<p>
				Tudo é gravado sozinho, primeiro neste navegador e depois no painel. Você pode fechar a página e voltar:
				a fila continua da primeira ficha incompleta.
			</p>
			<button type="button" onclick={() => (ajuda = false)}>Fechar</button>
		</div>
	{/if}
</div>

<style>
	.codificar {
		display: grid;
		gap: 1.2rem;
		max-width: 76rem;
	}

	.topo {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: end;
		gap: 1rem;
	}

	h1 {
		margin: 0;
		font-size: clamp(1.8rem, 3.5vw, 2.6rem);
		font-weight: 380;
	}

	.progresso {
		display: grid;
		gap: 0.25rem;
		min-width: 16rem;
		font-size: 0.85rem;
	}

	.progresso p {
		margin: 0;
	}

	progress {
		width: 100%;
		accent-color: var(--acento);
	}

	.estado {
		color: var(--texto-suave);
	}

	.parabens {
		margin: 0;
		color: var(--texto);
	}

	.ficha {
		display: grid;
		grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
		gap: 1.5rem;
		padding: 1.2rem;
		border: 1px solid var(--linha);
		border-radius: var(--raio);
		background: var(--superficie);
		outline: none;
	}

	.ficha:focus-visible {
		box-shadow: 0 0 0 2px var(--foco);
	}

	.texto h2 {
		margin: 0 0 0.8rem;
		font-size: 1.25rem;
		font-weight: 500;
		line-height: 1.35;
	}

	.resumo {
		margin: 0;
		line-height: 1.65;
		color: var(--texto);
	}

	.dica {
		margin: 0.8rem 0 0;
		font-size: 0.78rem;
		color: var(--texto-suave);
	}

	.variaveis {
		display: grid;
		gap: 0.4rem;
		align-content: start;
	}

	.variavel {
		border-left: 3px solid transparent;
		padding: 0.2rem 0 0.2rem 0.6rem;
	}

	.variavel.atual {
		border-left-color: var(--acento);
		background: var(--superficie-alta);
		border-radius: 0 var(--raio-pequeno) var(--raio-pequeno) 0;
		padding-bottom: 0.6rem;
	}

	.cabeca {
		display: flex;
		gap: 0.5rem;
		align-items: baseline;
		width: 100%;
		padding: 0.2rem 0;
		border: 0;
		background: none;
		color: var(--texto-suave);
		font: inherit;
		text-align: left;
		cursor: pointer;
	}

	.atual .cabeca .nome {
		color: var(--texto);
		font-weight: 600;
	}

	.valor {
		margin-left: auto;
		color: var(--texto);
		font-size: 0.85rem;
	}

	.incerto {
		padding: 0 0.35rem;
		border: 1px dashed var(--linha-forte);
		border-radius: 999px;
		font-size: 0.7rem;
		color: var(--texto-suave);
	}

	.pergunta {
		margin: 0.1rem 0 0.4rem;
		font-size: 0.85rem;
		color: var(--texto-suave);
	}

	.opcoes {
		display: grid;
		gap: 0.2rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.opcoes button {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		width: 100%;
		padding: 0.25rem 0.4rem;
		border: 1px solid var(--linha);
		border-radius: var(--raio-pequeno);
		background: var(--fundo);
		color: var(--texto);
		font: inherit;
		font-size: 0.88rem;
		text-align: left;
		cursor: pointer;
	}

	.opcoes button[aria-pressed='true'] {
		border-color: var(--acento);
		background: var(--acento-suave);
	}

	.definicao {
		margin: 0.1rem 0 0.3rem 2rem;
		font-size: 0.78rem;
		color: var(--texto-suave);
	}

	kbd {
		display: inline-block;
		min-width: 1.2em;
		padding: 0 0.3em;
		border: 1px solid var(--linha-forte);
		border-radius: 3px;
		font-family: var(--fonte-mono);
		font-size: 0.75em;
		text-align: center;
		color: var(--texto-suave);
	}

	input {
		width: 100%;
		padding: 0.35rem 0.5rem;
		border: 1px solid var(--linha-forte);
		border-radius: var(--raio-pequeno);
		background: var(--fundo);
		color: var(--texto);
		font: inherit;
	}

	.nota {
		margin-top: 0.4rem;
		font-size: 0.85rem;
	}

	.evidencia {
		margin: 0.4rem 0 0;
		font-size: 0.82rem;
		color: var(--texto-suave);
	}

	.limpar {
		border: 0;
		background: none;
		color: var(--texto-suave);
		cursor: pointer;
	}

	.aviso {
		margin: 0.3rem 0 0;
		color: var(--acento);
		font-size: 0.88rem;
	}

	.acoes {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-top: 0.6rem;
	}

	.acoes button,
	.trocar,
	.ajuda button {
		padding: 0.35rem 0.8rem;
		border: 1px solid var(--linha-forte);
		border-radius: var(--raio-pequeno);
		background: none;
		color: var(--texto);
		font: inherit;
		font-size: 0.88rem;
		cursor: pointer;
	}

	.acoes .confirmar {
		border-color: var(--acento);
		background: var(--acento);
		color: var(--sobre-acento);
	}

	.acoes .confirmar kbd {
		border-color: currentColor;
		color: inherit;
	}

	button:disabled {
		opacity: 0.4;
		cursor: default;
	}

	.rodape {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 0.6rem;
		font-size: 0.8rem;
		color: var(--texto-suave);
	}

	.rodape p {
		margin: 0;
	}

	.ajuda {
		position: fixed;
		right: 1.5rem;
		bottom: 1.5rem;
		z-index: 30;
		max-width: 28rem;
		padding: 1rem 1.2rem;
		border: 1px solid var(--linha-forte);
		border-radius: var(--raio);
		background: var(--superficie-alta);
		box-shadow: var(--sombra);
		font-size: 0.86rem;
	}

	.ajuda h2 {
		margin: 0 0 0.6rem;
		font-size: 1.05rem;
	}

	.ajuda dl {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.3rem 0.8rem;
		margin: 0 0 0.6rem;
	}

	.ajuda dd {
		margin: 0;
		color: var(--texto-suave);
	}

	@media (max-width: 900px) {
		.ficha {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
