<?php

$db = [
    'sgbd' => 'mysql',
    'host' => sw_env('MARIADB_HOST'),
    'username' => sw_env('MARIADB_USER'),
    'password' => sw_env('MARIADB_PASSWORD'),
    'dbname' => sw_env('MARIADB_DBNAME'),
    'charset' => 'utf8mb4',
    'options' => [
        PDO::ATTR_PERSISTENT => true,
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ],
];

return [
    'prod' => [
        'db' => $db,
    ],
    'test' => [
        'db' => $db,
    ],
    'dev' => [
        'db' => [
            'dbname' => getenv('APP_TESTING') ? sw_env('MARIADB_DBNAME_TEST') : sw_env('MARIADB_DBNAME'),
        ] + $db,
    ],
];
