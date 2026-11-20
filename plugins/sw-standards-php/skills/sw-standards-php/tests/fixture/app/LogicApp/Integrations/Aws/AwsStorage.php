<?php

namespace App\LogicApp\Integrations\Aws;

interface AwsStorage
{
    public function put(string $key, string $contents): string;
}
