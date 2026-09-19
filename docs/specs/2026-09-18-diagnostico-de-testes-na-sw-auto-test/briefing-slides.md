---
marp: true
paginate: true
theme: default
style: |
  section { font-family: 'Inter', 'Segoe UI', system-ui, sans-serif; color: #1c1d22; }
  h1 { color: #1f6f5c; letter-spacing: -.01em; }
  h2 { color: #1f6f5c; font-size: 1.35em; }
  strong { color: #1c1d22; }
  section.capa { justify-content: center; }
  .suave { color: #5b6070; }
---

<!-- _class: capa -->

# Check-up dos testes automáticos

Uma revisão da ferramenta que escreve e avalia os testes dos nossos sistemas

<span class="suave">Briefing · setembro de 2026</span>

---

## O problema

Testes automáticos são as verificações que rodam sozinhas e acusam quando uma alteração quebra o sistema.

- Hoje ninguém confere se os testes escritos **realmente funcionam**
- Existe o caso silencioso: **o teste que passa mesmo com o sistema quebrado**
- A bateria acumulada de anos nunca é revisada: testes desligados, instáveis, e partes do sistema sem verificação

O resultado é confiança baseada em quantidade, não em qualidade.

---

## O que muda

| Antes | Depois |
|---|---|
| Testes escritos sem conferência | Cada teste novo é **provado** |
| Bateria antiga nunca revisada | **Relatório de saúde** com o que consertar primeiro |
| Confiança por quantidade | Correção acompanhada, com aprovação a cada lote |

---

## Como a prova funciona

1. A ferramenta quebra um trecho do sistema **de propósito**
2. Confere se o teste acusa o erro
3. Devolve o trecho ao que era

Se o teste **não** acusou, esse é o achado mais valioso do processo: ele não estava protegendo nada.

---

## Entregas

- **Relatório de saúde** dos testes, com notas por área e cada problema localizado
- **Correção acompanhada**: nada muda sem aprovação, e o que quebrar volta ao que era
- **Prova do teste novo**, para não criar falsa sensação de segurança
- **Três tecnologias principais** cobertas a fundo; as demais, de forma simplificada

---

## Fases

| Etapa | Entrega |
|---|---|
| 1 e 2 | Levantamento da bateria e das medições, sem alterar nada |
| 3 | Relatório e correção acompanhada — **dá para parar aqui com valor entregue** |
| 4 | Prova do teste novo e regras contra teste frágil |
| 5 | Organização final e liberação para o time |

---

## Por que foi assim

- **Aproveitar o que já existe** — cada tecnologia tem suas ferramentas de medição; o resultado vira fato, não opinião
- **Nada roda sem autorização** — executar testes pode tocar banco e serviços
- **A ferramenta não decide sozinha** — aponta e propõe; sem dado suficiente, diz "sem dados" em vez de chutar

**Fora de escopo:** reescrever teste ruim sozinha, configurar a esteira de publicação, perseguir percentual de cobertura.

<span class="suave">Esforço: médio · trabalho interno, sem impacto para o cliente final</span>
