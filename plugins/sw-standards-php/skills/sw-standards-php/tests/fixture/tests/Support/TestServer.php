<?php

namespace Tests\Support;

// O ResponseApi termina com exit(), então o endpoint não roda dentro do processo do Pest: o Http/ chama este
// servidor embutido, que sobe uma vez por rodada e cai no fim do processo, mesmo quando um teste falha.
// Ele é outro processo: os fakes do Pest não chegam nele, por isso ele sobe pelo app-router.php, que instala os
// fakes dentro do servidor antes de entregar a requisição ao www/index.php.
final class TestServer
{
    public const PORT = 18080;

    /** @var resource|null */
    private static $process = null;
    private static string $log = '';

    public static function url(): string
    {
        return 'http://127.0.0.1:' . self::PORT;
    }

    public static function start(): void
    {
        if(self::$process){
            return;
        }

        // sem isso, a suíte falaria com um servidor que não é o de teste
        // @: sondagem de porta; porta fechada gera warning esperado, e é justamente o caso bom
        if(@fsockopen('127.0.0.1', self::PORT, $errno, $errstr, 0.2)){
            throw new \RuntimeException('Porta ' . self::PORT . ' já está em uso');
        }

        self::$log = tempnam(sys_get_temp_dir(), 'test-server-');
        register_shutdown_function([self::class, 'stop']);

        // o core inclui ../config e ../app relativos a www/
        self::$process = proc_open(
            [PHP_BINARY, '-S', '127.0.0.1:' . self::PORT, __DIR__ . '/app-router.php'],
            [0 => ['file', '/dev/null', 'r'], 1 => ['file', self::$log, 'a'], 2 => ['file', self::$log, 'a']],
            $pipes,
            __DIR__ . '/../../www',
            ['APP_TESTING' => '1'] + getenv()
        );

        self::_waitPort();
    }

    public static function stop(): void
    {
        if(!self::$process){
            return;
        }

        proc_terminate(self::$process);
        proc_close(self::$process);
        self::$process = null;
        // @: limpeza do log temporário; se já sumiu, tudo bem
        @unlink(self::$log);
    }

    // espera o boot do servidor (até 5 s), para o primeiro teste não pegar a porta fechada
    private static function _waitPort(): void
    {
        for($i = 0; $i < 100; $i++){
            // @: sondagem enquanto o servidor sobe; porta ainda fechada gera warning esperado
            $socket = @fsockopen('127.0.0.1', self::PORT, $errno, $errstr, 0.1);

            if($socket){
                fclose($socket);

                return;
            }

            usleep(50000);
        }

        throw new \RuntimeException('O servidor de teste não subiu: ' . file_get_contents(self::$log));
    }
}
