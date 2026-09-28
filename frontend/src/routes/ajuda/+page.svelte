<script lang="ts">
	import Icone from '$lib/componentes/Icone.svelte';
	import { usarProjeto } from '$lib/dados/contexto';
	import { rota } from '$lib/estado/url';
	import { NOMES_TEMA } from '$lib/estado/tema.svelte';
	import { secoesDoTrilho } from '$lib/secoes';

	const { manifesto } = usarProjeto();
	const secoes = secoesDoTrilho(manifesto).filter((s) => s.id !== 'inicio');
</script>

<svelte:head>
	<title>Ajuda · mapa da ciência</title>
</svelte:head>

<div class="pagina surgir">
	<header class="cabecalho">
		<p class="rotulo-miudo sobre"><Icone nome="ajuda" tamanho={16} /> <span>Ajuda</span></p>
		<h1>Como ler este observatório</h1>
		<p class="resumo">
			O mapa da ciência mostra um corpus de artigos científicos: sobre o que falam, como foram
			classificados e de onde vêm. Tudo o que aparece aqui sai dos arquivos gerados pelo
			pipeline{manifesto.api ? ', no seu computador' : ' e publicados neste site'}.
		</p>
	</header>

	<section aria-labelledby="ajuda-secoes">
		<h2 id="ajuda-secoes">As seções</h2>
		<dl class="secoes">
			{#each secoes as s (s.id)}
				<div>
					<dt>
						<Icone nome={s.icone} tamanho={18} />
						{#if s.selo}
							<span>{s.rotulo}</span>
						{:else}
							<a href={rota(s.caminho)}>{s.rotulo}</a>
						{/if}
						<!-- só as seções que ainda não existem dizem quando chegam; as outras já estão aqui -->
						{#if s.selo}<span class="chegada">chega {s.chegada}</span>{/if}
					</dt>
					<dd>{s.resumo}</dd>
				</div>
			{/each}
		</dl>
	</section>

	<section aria-labelledby="ajuda-recorte" data-testid="ajuda-recorte">
		<h2 id="ajuda-recorte">O recorte</h2>
		<p>
			A barra logo abaixo do título guarda o <strong>recorte</strong>: os documentos que as vistas de análise
			(Mapa, Tópicos e Geografia) mostram. O contador à direita diz quantos passam em tudo. Entram no recorte:
		</p>
		<ul>
			<li>o <strong>período</strong>, na linha do tempo (o <strong>Play</strong> anima ano a ano);</li>
			<li>as <strong>revistas</strong>, no botão ao lado;</li>
			<li>os <strong>tópicos</strong>, a <strong>busca</strong> e o <strong>laço</strong>, escolhidos no Mapa e nos Tópicos;</li>
			<li>
				<strong>UFs</strong>, <strong>países</strong> e <strong>instituições</strong>, escolhidos na Geografia: um
				documento passa se tiver ao menos uma afiliação no lugar escolhido.
			</li>
		</ul>
		<p>
			Cada escolha vira um chip na barra; o × tira. O recorte vai junto quando você troca de vista pelo trilho, e o
			que é só de uma vista (a câmera do mapa, o modo do fluxo, o documento ou o tópico aberto) fica para trás.
			Cada gráfico ignora o próprio filtro: com São Paulo escolhido, o mapa das UFs continua mostrando as outras,
			para você comparar e escolher mais.
		</p>
	</section>

	<div class="colunas">
		<section aria-labelledby="ajuda-topicos">
			<h2 id="ajuda-topicos">Como ler os tópicos</h2>
			<p>
				O <strong>fluxo</strong> mostra os macrotemas (ou, clicando num deles, os tópicos dele) ano a ano. Em
				<em>Fluxo</em>, a espessura é o número de documentos; em <em>Absoluto</em>, as faixas partem do zero; em
				<em>100%</em>, cada ano soma 100%, e a altura é a participação.
			</p>
			<p>
				<strong>Em alta</strong> e <strong>em queda</strong> são os tópicos cuja participação muda de forma
				distinguível do acaso (regressão logística com intervalo de 95%, corrigida pela dispersão). Com dezenas de
				tópicos testados, cerca de 1 em 20 aparece por acaso: leia a lista como pistas, não como conclusões.
				Um pico no primeiro ou no último ano do período escolhido, como um dossiê temático, também pode puxar a
				tendência, e algumas marcações são marginais (no piloto, três das 13 somem quando se tira um só ano da série).
			</p>
		</section>

		<section aria-labelledby="ajuda-geografia">
			<h2 id="ajuda-geografia">Como ler a geografia</h2>
			<p>
				Cada documento vale 1, dividido entre os autores e, para cada autor, entre as afiliações dele: um artigo de
				dois autores, um da USP e um da UnB, dá 0,5 a cada uma. Assim, artigos com muitos autores não pesam mais.
			</p>
			<p>
				No mapa-múndi, o Brasil fica <strong>fora da escala</strong> (hachurado), senão ele achataria os outros
				países. Afiliações que não casaram com nenhuma instituição contam no país e na UF que a fonte informou; as de
				autores sem afiliação não contam em lugar nenhum. A cobertura por ano mostra quanto do peso está em cada
				caso: nos anos mais antigos, falta mais afiliação.
			</p>
		</section>

		<section aria-labelledby="ajuda-classificacao">
			<h2 id="ajuda-classificacao">Como ler a classificação</h2>
			<p>
				O modelo leu o título e o resumo de cada documento e respondeu às perguntas do codebook, copiando do resumo um
				trecho que justifica cada resposta. As proporções contam só os documentos classificados; os sem resumo ficam
				de fora.
			</p>
			<p>
				O <strong>selo κ</strong> ao lado de cada variável é a concordância do modelo com a codificação da amostra
				de validação. Com hachura, ela está abaixo de 0,6: leia aquela variável com cuidado. Com borda tracejada, a
				comparação é com um codificador de referência, que não é uma pessoa. Escolha uma célula para ler os
				documentos e o trecho marcado no resumo.
			</p>
		</section>

		<section aria-labelledby="ajuda-links">
			<h2 id="ajuda-links">Links que guardam a vista</h2>
			<p>
				O endereço guarda a seção e os filtros depois do <code>#</code>, como em
				<code>#/mapa?anos=2012-2020</code>. Copie o endereço para compartilhar exatamente o que você está
				vendo.
			</p>
		</section>

		<section aria-labelledby="ajuda-temas">
			<h2 id="ajuda-temas">Dois temas</h2>
			<p>
				<strong>{NOMES_TEMA.observatorio}</strong> é o escuro, como um céu noturno.
				<strong>{NOMES_TEMA.prancha}</strong> é o claro, como o papel de um atlas. O tema segue a configuração
				do sistema até você escolher um no botão da barra superior; a escolha fica guardada neste
				navegador.
			</p>
		</section>

		<section aria-labelledby="ajuda-modo">
			<h2 id="ajuda-modo">Site ou painel</h2>
			<p>
				{#if manifesto.api}
					Você está no <strong>painel local</strong> (<code>mapa painel</code>), que roda só nesta máquina e
					poderá editar o projeto.
				{:else}
					Você está no <strong>site estático</strong>: os dados são somente leitura. Para editar um projeto,
					use o painel local, com <code>mapa painel</code>.
				{/if}
			</p>
		</section>

		<section aria-labelledby="ajuda-teclado">
			<h2 id="ajuda-teclado">Pelo teclado</h2>
			<p>
				<kbd>Tab</kbd> percorre os controles, e o primeiro deles é “Pular para o conteúdo”. O foco fica sempre
				visível, e as animações somem se o sistema pedir menos movimento.
			</p>
			<h3 id="atalhos-todas">Em todas as vistas</h3>
			<dl class="atalhos" data-testid="atalhos-todas">
				<dt><kbd>P</kbd></dt>
				<dd>modo apresentação: esconde o trilho e as barras e aumenta a letra, para projetar (<kbd>Esc</kbd> sai)</dd>
			</dl>

			<h3 id="atalhos-mapa">No mapa</h3>
			<dl class="atalhos" data-testid="atalhos-mapa">
				<dt><kbd>/</kbd></dt>
				<dd>busca por título ou autor</dd>
				<dt><kbd>L</kbd></dt>
				<dd>liga o laço: arraste em volta dos pontos para ficar só com eles</dd>
				<dt><kbd>Esc</kbd></dt>
				<dd>fecha o cartão do documento ou desliga o laço</dd>
				<dt><kbd>?</kbd></dt>
				<dd>abre esta página</dd>
				<dt>roda do mouse, arrastar</dt>
				<dd>aproxima e move o mapa; de perto, os rótulos passam dos macrotemas para os tópicos</dd>
			</dl>
			<p>
				Tudo o que você faz no mapa (filtros, busca, laço, documento aberto e a posição da câmera) fica no endereço
				da página: copie o link para mostrar exatamente a mesma coisa a outra pessoa.
			</p>
		</section>
	</div>
</div>

<style>
	.atalhos {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 0.4rem 1rem;
		margin: 0.5rem 0 1rem;
	}

	.atalhos dd {
		margin: 0;
	}

	.pagina {
		display: grid;
		gap: 2.5rem;
	}

	.cabecalho {
		display: grid;
		gap: 0.75rem;
		max-width: 50rem;
	}

	.sobre {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		color: var(--acento);
	}

	h1 {
		font-size: clamp(2.2rem, 4.5vw, 3.3rem);
		font-weight: 380;
	}

	h2 {
		font-size: 1.35rem;
		margin-bottom: 0.75rem;
	}

	.resumo {
		font-size: 1.1rem;
		color: var(--texto-suave);
	}

	.secoes {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(19rem, 1fr));
		gap: 0;
		margin: 0;
		border-top: 1px solid var(--linha);
	}

	.secoes div {
		display: grid;
		gap: 0.35rem;
		padding: 1rem 1.25rem 1.1rem 0;
		border-bottom: 1px solid var(--linha);
	}

	.secoes dt {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.5rem;
		font-weight: 600;
	}

	.secoes dt :global(.icone) {
		color: var(--acento);
	}

	.secoes a {
		text-decoration-color: var(--linha-forte);
		text-underline-offset: 3px;
	}

	.chegada {
		font-family: var(--fonte-mono);
		font-size: 0.7rem;
		font-weight: 400;
		color: var(--texto-suave);
	}

	.secoes dd {
		margin: 0;
		font-size: 0.9rem;
		color: var(--texto-suave);
	}

	.colunas {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
		gap: 2rem 2.5rem;
	}

	.colunas p {
		color: var(--texto-suave);
	}

	.colunas strong {
		color: var(--texto);
	}

	kbd {
		font-family: var(--fonte-mono);
		font-size: 0.8em;
		padding: 0.05em 0.4em;
		border: 1px solid var(--linha-forte);
		border-bottom-width: 2px;
		border-radius: var(--raio-pequeno);
		color: var(--texto);
	}
</style>
