<?php

namespace Tests\Support;

// Instala, numa chamada, o falso de cada integração externa: nenhum teste fala com serviço real.
// As implementações falsas ficam em Support/Fake/.
// Fila e log não entram aqui: Queue e DiscordLogger ficam desligados pela config com APP_TESTING até o core ganhar fake().
final class Fakes
{
    public static function install(): void
    {
        // uma linha por integração: Integracao::fake(new FakeIntegracao());
        // Pagamento::fake(new \Tests\Support\Fake\FakePagamento());
    }
}
