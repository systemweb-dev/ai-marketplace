# Certificados TLS do acesso ao daemon — o que reportar e como recomendar

O acesso remoto ao Docker (`tcp://host:2376`) depende de três certificados: **CA**,
**servidor** (no host) e **cliente** (em quem conecta). Quando **qualquer um** vence, todo
acesso remoto para — CLI, deploys de CI/CD e painéis que usam TCP. **Os containers continuam
rodando**; o que quebra é a *gestão*. Diga isso ao usuário: é um susto grande com impacto
operacional limitado.

A skill lê **só as datas** de `ca.pem` e `cert.pem` do diretório do context (nunca `key.pem`)
e publica em `report["tls"]`. Contexts `ssh://` ou socket local não têm certificado → seção n/a.

**A CA tem validade própria.** É comum CA e folhas serem geradas no mesmo dia com o mesmo
prazo — e vencerem juntas. Uma CA vencida invalida tudo, mesmo com o certificado de cliente
ainda válido. Por isso a checagem cobre os dois e reporta o que vence **primeiro**.

## O que escrever na recomendação (quando `OPS_TLS_EXPIRED` ou `OPS_TLS_EXPIRING`)

Monte a recomendação com estes elementos — **adapte os caminhos ao que a coleta mostrar**
(`systemctl cat docker | grep tls` revela onde o daemon lê os certificados):

**1. Renovar mantendo a mesma CA.** Se as chaves privadas existem (`ca-key.pem`,
`server-key.pem`, `key.pem`), reemita os certificados **reutilizando-as** — a identidade da CA
não muda e nenhum cliente precisa trocar de contexto. Valide **antes** de aplicar:
```
openssl verify -CAfile ca.pem.new server-cert.pem.new   # precisa dizer OK
openssl verify -CAfile ca.pem.new cert.pem.new          # precisa dizer OK
```
Só troque os arquivos se ambos derem `OK` — é o que evita o usuário se trancar pra fora.
Sempre recomende **backup** do diretório antes.

**2. Avisar do impacto do restart.** O daemon só relê certificado ao subir (`reload`/SIGHUP
**não** recarrega TLS). Reiniciar o dockerd **reinicia as tasks daquele nó**. Use os fatos do
próprio relatório para dimensionar: se o **ingress** (Traefik/nginx) roda naquele nó com **1
réplica**, o tráfego externo de *todas* as aplicações cai por ~30–60s. Recomende janela.

**3. Lembrar dos outros clientes.** Todo lugar que conecta via `tcp://…:2376` precisa do
**novo `ca.pem` e `cert.pem`** (a chave privada não muda): máquinas de dev, **secrets de CI/CD**,
painéis. Painéis que usam o socket local (`/var/run/docker.sock`) **não** precisam.

**4. Sugerir que isso não se repita:**
- **Validade longa** na reemissão (10–20 anos numa CA privada é aceitável; avise que
  certificado eterno que vaze é acesso eterno).
- **Trocar TLS por `ssh://`** — sem certificado, sem expiração, e revogar é remover a chave do
  `authorized_keys`: `docker context create <nome> --docker "host=ssh://user@host"`.
- **Restringir a porta 2376** no firewall se estiver aberta (a API é root-equivalente no host).

**5. Checagens pós-restart.** Réplicas `N/N` não provam funcionamento. Depois de reiniciar o
daemon, mande conferir os componentes que mantêm **cluster interno próprio** (agentes de
painel, service discovery, gossip) — eles podem ficar com estado partido enquanto aparentam
saudáveis. Sintoma típico: painel alternando entre "vê tudo" e "vê nada". Correção costuma ser
um `docker service update --force <serviço-agente>`, que é seguro (proxy sem estado, não toca
em container de aplicação).

## Quando as chaves privadas não existem (ou a passphrase se perdeu)
Aí não dá para manter a CA: é preciso gerar uma nova e **distribuir o novo `ca.pem` para todos
os clientes**. Diga isso claramente, porque muda o tamanho do trabalho.
