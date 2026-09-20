---
regra: OPS_ENGINE_DRIFT
titulo: Nós com versões diferentes de engine
---

## Por que importa

Nós com versões diferentes se comportam de forma diferente em detalhes que aparecem no pior
momento: opção que um aceita e o outro ignora, mudança de rede, diferença no tratamento de
recurso. O sintoma típico é "só falha quando cai naquele nó" — que é o bug mais caro de achar.

## Como resolver

1. Escolha a versão alvo (a mais nova estável que você já usa).
2. Atualize **um nó de cada vez**, drenando antes e devolvendo ao ativo depois de conferir.

```bash
docker node update --availability drain <nó>
# atualize o pacote do engine no host, e então:
docker node update --availability active <nó>
docker node ls        # confira a versão e o estado antes do próximo
```

## Como confirmar

`docker node ls` mostra a mesma versão em todos, e a auditoria seguinte sai sem o achado.

## Quando NÃO fazer

Durante a própria janela de atualização — é esperado divergir enquanto ela acontece. O que não
pode é a divergência virar permanente por esquecimento.
