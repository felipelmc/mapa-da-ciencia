/**
 * A concordância de um par em partes da amostra (contrato 1.7): por idioma do texto lido e entre respostas
 * informativas. Cada célula traz o kappa (a concordância, numa variável de texto) e o número de documentos; "—"
 * quando o subconjunto tem menos de 20 documentos ou as respostas não variaram. Os dados até a 1.6 não têm
 * subconjuntos, e a figura não aparece.
 */
import type { MetricaSubconjunto, MetricaVariavel } from "$lib/contrato/tipos";
import {
  formatarDecimal,
  formatarInteiro,
  formatarPorcentagem,
} from "$lib/formato";

const IDIOMAS: Record<string, string> = {
  pt: "Português",
  en: "Inglês",
  es: "Espanhol",
  fr: "Francês",
};

export interface ColunaSubconjunto {
  chave: string;
  rotulo: string;
}

const chave = (s: Pick<MetricaSubconjunto, "tipo" | "idioma">) =>
  `${s.tipo}:${s.idioma ?? ""}`;

/** As colunas dos subconjuntos das métricas de um par, na ordem em que aparecem. */
export function colunasSubconjuntos(
  metricas: MetricaVariavel[],
): ColunaSubconjunto[] {
  const colunas = new Map<string, ColunaSubconjunto>();
  for (const m of metricas)
    for (const s of m.subconjuntos ?? [])
      if (!colunas.has(chave(s)))
        colunas.set(chave(s), {
          chave: chave(s),
          rotulo:
            s.tipo === "informativas"
              ? "Respostas informativas"
              : (IDIOMAS[s.idioma ?? ""] ?? s.idioma ?? "?"),
        });
  return [...colunas.values()];
}

/** O texto de uma célula: "0,67 (42)", "— (18)" ou "não se aplica" (o subconjunto não existe na variável). */
export function celulaSubconjunto(
  m: MetricaVariavel,
  coluna: string | null,
): string {
  const s =
    coluna === null
      ? m
      : (m.subconjuntos ?? []).find((x) => chave(x) === coluna);
  if (!s) return "não se aplica";
  const texto = !m.matriz.rotulos.length;
  const valor = texto ? s.concordancia : s.kappa;
  const formatado =
    valor === null || valor === undefined
      ? "—"
      : texto
        ? formatarPorcentagem(valor)
        : formatarDecimal(valor, 2);
  return `${formatado} (${formatarInteiro(s.n)})`;
}

const IDIOMAS_NA_FRASE: Record<string, string> = {
  pt: "em português",
  en: "em inglês",
  es: "em espanhol",
  fr: "em francês",
};

/**
 * A composição da amostra pelo idioma do texto lido, para o lide da vista: pares (rótulo, n). Um documento sorteado que
 * ficou sem resumo depois (um fragmento que a coleta tirou) entra como "sem resumo", para a soma bater com o tamanho
 * da amostra. Sem as contagens (dados até a 1.6), nada.
 */
export function composicaoDaAmostra(
  n: number,
  idiomas: Record<string, number> | undefined,
): [string, number][] {
  const pares: [string, number][] = Object.entries(idiomas ?? {}).map(
    ([idioma, k]) => [IDIOMAS_NA_FRASE[idioma] ?? `em ${idioma}`, k],
  );
  const resto = n - pares.reduce((soma, [, k]) => soma + k, 0);
  return pares.length && resto > 0 ? [...pares, ["sem resumo", resto]] : pares;
}
