---
regra: SEC_USER_ROOT
titulo: Container roda como root
---

## Por que importa

Rodar como root amplia o estrago de qualquer falha na aplicação: uma leitura de arquivo
arbitrária vira leitura de tudo, uma escrita vira persistência. Sozinho não é um buraco — é o
multiplicador de todos os outros.

## Como resolver

1. Crie um usuário na imagem e mude para ele no fim do Dockerfile.
2. Ajuste a propriedade dos diretórios que a aplicação escreve.
3. Se a aplicação precisa de porta abaixo de 1024, publique por outra porta em vez de dar
   privilégio — quem mapeia é o orquestrador.

```dockerfile
RUN adduser --system --uid 10001 app
USER 10001
```

```yaml
# sem mexer na imagem, dá para forçar no deploy:
user: "10001:10001"
```

## Como confirmar

A auditoria deixa de apontar. Na mão, `docker exec <container> id` responde com o uid esperado
em vez de `uid=0(root)`.

## Quando NÃO fazer

Container que precisa mesmo de root para a função dele (agente de sistema, ferramenta de
backup que lê arquivo de todo mundo). Aí vale registrar como risco aceito e reduzir o resto:
sistema de arquivos em modo leitura, capacidades removidas.
