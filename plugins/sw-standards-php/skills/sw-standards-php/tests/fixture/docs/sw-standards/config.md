# Padrões deste projeto (sw-standards-php)

## Respostas
- Formato do erro: código específico + frase (padrão)
- E-mail: SendGrid (padrão)
- Multiempresa: sim — coluna `id_company`, mecanismo `{Recurso}ExistsMiddleware` (`InvoiceExistsMiddleware`); a empresa logada vem de `$this->shared('company')`, compartilhada pelo `AuthCompanyMiddleware`
- PHP: 8.3   · Core: v1.11.0

## Exceções aceitas
| Arquivo:linha | Regra | Motivo | Quem aceitou | Data |
|---|---|---|---|---|
