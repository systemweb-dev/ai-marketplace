<?php

// Tratador global do projeto: a exceção que ninguém capturou vira server_error 500, sem trace, e o detalhe vai
// para o log. Some quando o core ganhar o tratador dele. Copie para config/ExceptionHandler.php e carregue uma
// vez no www/index.php, com require __DIR__ . '/../config/ExceptionHandler.php'; antes do new SysWeb\System():
// o construtor já faz o boot, e o que for lançado ali escaparia.
set_exception_handler(function (\Throwable $exception): void {
    $contexto = ($_SERVER['REQUEST_METHOD'] ?? 'cli') . ' ' . ($_SERVER['REQUEST_URI'] ?? '');

    $classe = $exception::class;

    // o warning de um envio que falha cairia no Error.php do core, que em dev responde sozinho com a URL do webhook
    set_error_handler(static function (int $tipo, string $mensagem): never {
        throw new \ErrorException($mensagem, 0, $tipo);
    });

    try{
        // sem o setTitle o DiscordLogger do core falha (propriedade estática não inicializada)
        \SysWeb\Logger\DiscordLogger::setTitle('Unhandled exception');
        \SysWeb\Logger\DiscordLogger::send("unhandled {$classe} {$contexto}: {$exception->getMessage()}", \SysWeb\Logger\ELogger::ERROR);
    }catch(\Throwable){
        error_log("unhandled {$classe} {$contexto}");
    }finally{
        restore_error_handler();
    }

    \SysWeb\Api\ResponseApi::error('server_error', 'Unexpected error', 500);
});
