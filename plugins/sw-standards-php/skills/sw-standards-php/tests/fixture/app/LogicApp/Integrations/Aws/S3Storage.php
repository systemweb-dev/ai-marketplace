<?php

namespace App\LogicApp\Integrations\Aws;

use Aws\S3\S3Client;

final class S3Storage implements AwsStorage
{
    public function __construct(private S3Client $client, private string $bucket)
    {
    }

    public function put(string $key, string $contents): string
    {
        $temporaryPath = tempnam(sys_get_temp_dir(), 's3-');
        file_put_contents($temporaryPath, $contents);

        try{
            $this->client->putObject([
                'Bucket' => $this->bucket,
                'Key' => $key,
                'SourceFile' => $temporaryPath,
            ]);
        }finally{
            // o arquivo temporário pode já ter sido apagado pelo SO; a falha aqui não muda nada
            @unlink($temporaryPath);
        }

        return $key;
    }
}
