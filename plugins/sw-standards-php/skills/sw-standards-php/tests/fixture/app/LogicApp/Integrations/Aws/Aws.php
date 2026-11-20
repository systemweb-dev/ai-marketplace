<?php

namespace App\LogicApp\Integrations\Aws;

use Aws\S3\S3Client;

final class Aws
{
    private static ?AwsStorage $instance = null;

    public static function instance(): AwsStorage
    {
        $aws = sw_config('aws');
        $bucket = sw_env('AWS_BUCKET');

        return self::$instance ??= self::_s3Storage($aws, $bucket);
    }

    public static function fake(AwsStorage $fake): void
    {
        self::$instance = $fake;
    }

    private static function _s3Storage(array $aws, string $bucket): S3Storage
    {
        $client = new S3Client([
            'region' => $aws['region'],
            'version' => 'latest',
            'credentials' => ['key' => $aws['key'], 'secret' => $aws['secret']],
        ]);

        return new S3Storage($client, $bucket);
    }
}
