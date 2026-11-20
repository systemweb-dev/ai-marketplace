<?php

namespace Tests\Support;

use Carbon\CarbonImmutable;

// Quando o core ganhar um boot de teste, este arquivo some e o Pest.php chama o core.
final class Boot
{
    public static function start(): void
    {
        self::_forceDevEnv();
        putenv('APP_TESTING=1');

        // o core lê a config antes do teste: recarrega já no modo de teste
        $GLOBALS['_ENVS'] = include __DIR__ . '/../../config/Env.php';
        $GLOBALS['_SWCONFIGS'] = include __DIR__ . '/../../config/Config.php';

        TestDatabase::recreate();
        TestServer::start();
    }

    public static function reset(): void
    {
        Fixtures::truncate();
        Fakes::install();
        CarbonImmutable::setTestNow();
    }

    private static function _forceDevEnv(): void
    {
        $envs = array_values(array_filter($_SERVER['argv'], fn ($arg) => str_starts_with($arg, 'env=')));

        if($envs && $envs !== ['env=dev']){
            fwrite(STDERR, "Testes só rodam com env=dev\n");
            exit(1);
        }

        $_SERVER['argv'][] = 'env=dev';
    }
}
