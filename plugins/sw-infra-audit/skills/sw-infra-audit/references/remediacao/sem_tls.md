---
regra: sem_tls
titulo: Endpoint público servido sem TLS
---

## Por que importa

O endereço é público e responde em `http`. Tudo que trafega ali vai legível: credencial,
cookie de sessão, dado de cliente. E qualquer intermediário pode alterar a resposta no caminho —
não é só escuta, é injeção.

## Como resolver

1. Emita o certificado (ACME resolve para host público, e é automático).
2. Sirva em `https` e redirecione o `http` em vez de desligá-lo — link antigo continua existindo.
3. Depois que estiver estável, ligue HSTS para o navegador nem tentar o caminho inseguro.

```yaml
# no proxy: um roteador para redirecionar, outro para servir com TLS
- "traefik.http.routers.app-http.middlewares=redir-https"
- "traefik.http.routers.app.tls.certresolver=le"
```

## Como confirmar

`curl -sSI http://<host>/` responde com redirecionamento permanente para `https`, e a auditoria
seguinte mostra o certificado no lugar do achado.

## Quando NÃO fazer

Endereço interno, em rede fechada, que a skill já reconhece como interno e não aponta. Se um
endereço interno apareceu aqui, o que está errado é ele ser resolvível de fora.
