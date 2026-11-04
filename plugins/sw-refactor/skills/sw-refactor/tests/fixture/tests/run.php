<?php
foreach (glob(__DIR__ . '/../src/Controller/*.php') as $arquivo) {
    require_once $arquivo;
    $classe = basename($arquivo, '.php');
    $ok = (new $classe())->store(['id' => 3]) === ['id' => 3];
    try {
        (new $classe())->store(['id' => 0]);
        $ok = false;
    } catch (InvalidArgumentException $erro) {
    }
    if (!$ok) {
        fwrite(STDERR, "falhou: $classe\n");
        exit(1);
    }
}
echo "ok\n";
