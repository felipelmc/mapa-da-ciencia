# 0001. Certificados do sistema operacional com `truststore`

- **Status:** aceita
- **Data:** 2026-09-26
- **Marco:** M0

## Contexto

O `mapa-da-ciencia` faz requisições HTTPS à ArticleMeta e ao OpenAlex. Na máquina de desenvolvimento, a mesma requisição teve resultados diferentes:

- o `curl` funcionou;
- o Python instalado pelo python.org falhou com `CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain`.

O `curl` usa o chaveiro do macOS. O Python do python.org usa o próprio pacote de certificados, que não inclui a autoridade certificadora presente na cadeia desta rede. Redes com proxy ou inspeção de TLS, comuns em universidades e órgãos públicos, causam o mesmo problema. Para o público do projeto (alunos, oficinas, laboratórios), isso vira erro na primeira execução.

## Opções consideradas

- **Desligar a verificação de TLS:** descartada, porque é insegura.
- **Pedir que o usuário rode `Install Certificates.command` ou configure `SSL_CERT_FILE`:** frágil e difícil de explicar numa oficina.
- **`certifi`:** tem o mesmo problema, já que é outro pacote que não inclui a CA local.
- **`truststore`:** faz o Python usar o repositório de certificados do sistema operacional (Keychain no macOS, CryptoAPI no Windows, OpenSSL do sistema no Linux).

## Evidência

- Com `urllib` e o Python 3.13 do python.org, a requisição à ArticleMeta falha com o erro acima.
- Com `httpx` e `truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)` como `verify`, o spike de fontes (`spikes/s01_fontes.py`) fez milhares de requisições à ArticleMeta e ao OpenAlex sem erro de certificado.

## Decisão

Todas as chamadas HTTP do pacote passam por um cliente `httpx` criado em `rede.py`, com `verify=truststore.SSLContext(...)`. `truststore` passa a ser uma dependência obrigatória.

## Consequências

- O projeto funciona em redes com proxy corporativo ou acadêmico sem configuração extra.
- `mapa diagnostico` deve testar a conexão HTTPS com a ArticleMeta e o OpenAlex e, se falhar, explicar a causa provável.
- Nenhum código do projeto deve criar um cliente HTTP fora de `rede.py`.

## Como reproduzir

    uv run spikes/s01_fontes.py --revistas op
