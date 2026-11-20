<?php

// Roteador do servidor de teste. O servidor é outro processo: o fake instalado no Pest não chega aqui, então este
// arquivo instala os fakes dentro do servidor e só depois entrega a requisição ao www/index.php, como o nginx faz.
// Sem APP_TESTING ele recusa, para nunca atender com o banco e os fornecedores de verdade.
if(!getenv('APP_TESTING')){
    http_response_code(500);
    echo 'app-router: APP_TESTING é obrigatório';

    return true;
}

$root = dirname(__DIR__, 2);
require $root . '/vendor/autoload.php';

\Tests\Support\Fakes::install();

// o core inclui ../config e ../app relativos a www/
chdir($root . '/www');
require $root . '/www/index.php';
