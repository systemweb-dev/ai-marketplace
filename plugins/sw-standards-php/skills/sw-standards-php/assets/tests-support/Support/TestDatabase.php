<?php

// Exceção às regras banco-no-model e seguranca-e-config: este arquivo cria o banco de teste antes de a config
// de banco existir, então lê as credenciais com sw_env e fala com o PDO direto. Vale só para tests/Support/.

namespace Tests\Support;

use PDO;

// Recria o banco de teste uma vez por rodada, direto das migrations, para o teste não depender do Flyway.
final class TestDatabase
{
    public static function recreate(): void
    {
        $name = (string) sw_env('MARIADB_DBNAME_TEST');

        // um nome errado aqui apagaria o banco de verdade
        if(!str_ends_with($name, '_test')){
            throw new \RuntimeException('MARIADB_DBNAME_TEST precisa terminar em _test');
        }

        $pdo = new PDO(
            'mysql:host=' . sw_env('MARIADB_HOST') . ';charset=utf8mb4',
            (string) sw_env('MARIADB_USER'),
            (string) sw_env('MARIADB_PASSWORD'),
            [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]
        );

        $pdo->exec("CREATE DATABASE IF NOT EXISTS `{$name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");
        $pdo->exec("USE `{$name}`");

        // apaga as tabelas, não o banco: conexão persistente do PHP-FPM ficaria sem banco selecionado
        $pdo->exec('SET FOREIGN_KEY_CHECKS = 0');

        foreach($pdo->query("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")->fetchAll(PDO::FETCH_COLUMN) as $table){
            $pdo->exec("DROP TABLE `{$table}`");
        }

        $pdo->exec('SET FOREIGN_KEY_CHECKS = 1');

        foreach(self::_migrations() as $file){
            $pdo->exec(file_get_contents($file));
        }
    }

    // V{n}__*.sql na ordem de versão, como o Flyway aplica: V10 vem depois de V9
    private static function _migrations(): array
    {
        $files = glob(__DIR__ . '/../../database/sql/V*__*.sql');
        $version = fn ($file) => str_replace('_', '.', substr(basename($file), 1, strpos(basename($file), '__') - 1));
        usort($files, fn ($a, $b) => version_compare($version($a), $version($b)));

        return $files;
    }
}
