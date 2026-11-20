<?php

namespace Tests\Support;

use App\LogicApp\Integrations\Aws\Aws;
use Tests\Support\Fake\FakeAwsStorage;

// Instala, numa chamada, o falso de cada integração externa: nenhum teste fala com serviço real.
// As implementações falsas ficam em Support/Fake/.
// Fila e log não entram aqui: Queue e DiscordLogger ficam desligados pela config com APP_TESTING até o core ganhar fake().
final class Fakes
{
    public static function install(): void
    {
        Aws::fake(new FakeAwsStorage());
    }
}
