/**
 * Tema visual: Observatório (escuro, padrão) ou Prancha (claro, papel de atlas).
 *
 * Sem escolha explícita, o tema segue `prefers-color-scheme` e acompanha mudanças do
 * sistema. Quando a pessoa usa o botão, a escolha fica em localStorage e passa a valer.
 * O script inline de src/app.html aplica o tema antes da primeira pintura, com a mesma
 * regra; este módulo assume dali em diante.
 */

export type Tema = 'observatorio' | 'prancha';

export const NOMES_TEMA: Record<Tema, string> = {
	observatorio: 'Observatório',
	prancha: 'Prancha'
};

const CHAVE = 'mapa-da-ciencia:tema';
const CONSULTA_CLARO = '(prefers-color-scheme: light)';

const ehTema = (v: unknown): v is Tema => v === 'observatorio' || v === 'prancha';

function lerEscolha(): Tema | null {
	try {
		const v = localStorage.getItem(CHAVE);
		return ehTema(v) ? v : null;
	} catch {
		return null; // navegação privada, armazenamento bloqueado etc.
	}
}

function gravarEscolha(tema: Tema) {
	try {
		localStorage.setItem(CHAVE, tema);
	} catch {
		// Sem armazenamento, a escolha vale só até recarregar.
	}
}

function doSistema(): Tema {
	return typeof matchMedia === 'function' && matchMedia(CONSULTA_CLARO).matches ? 'prancha' : 'observatorio';
}

/** O tema que o script do app.html já aplicou, para o botão nascer com o rótulo certo. */
function doDocumento(): Tema {
	const v = typeof document === 'undefined' ? null : document.documentElement.dataset.tema;
	return ehTema(v) ? v : 'observatorio';
}

class EstadoTema {
	atual = $state<Tema>(doDocumento());
	/** `true` se a pessoa escolheu pelo botão; `false` se segue o sistema. */
	escolhido = $state(false);

	/** Sincroniza com o que o app.html aplicou e passa a ouvir o sistema. Devolve a limpeza. */
	iniciar(): () => void {
		const escolha = lerEscolha();
		this.escolhido = escolha !== null;
		this.#aplicar(escolha ?? doSistema());
		if (typeof matchMedia !== 'function') return () => {};
		const consulta = matchMedia(CONSULTA_CLARO);
		const aoMudar = () => {
			if (!this.escolhido) this.#aplicar(doSistema());
		};
		consulta.addEventListener('change', aoMudar);
		return () => consulta.removeEventListener('change', aoMudar);
	}

	alternar() {
		const novo: Tema = this.atual === 'observatorio' ? 'prancha' : 'observatorio';
		this.escolhido = true;
		gravarEscolha(novo);
		this.#aplicar(novo);
	}

	#aplicar(tema: Tema) {
		this.atual = tema;
		document.documentElement.dataset.tema = tema;
	}
}

export const tema = new EstadoTema();
