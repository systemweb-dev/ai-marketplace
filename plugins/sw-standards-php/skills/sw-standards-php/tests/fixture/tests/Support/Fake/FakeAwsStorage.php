<?php

namespace Tests\Support\Fake;

use App\LogicApp\Integrations\Aws\AwsStorage;

final class FakeAwsStorage implements AwsStorage
{
    public array $files = [];

    public function put(string $key, string $contents): string
    {
        $this->files[$key] = $contents;

        return $key;
    }
}
