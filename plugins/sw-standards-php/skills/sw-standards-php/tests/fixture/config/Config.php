<?php

use SysWeb\Jobs\ESystemJobs;

return [
    'both' => [
        'jwtSerialKey' => sw_env('JWT_SERIAL_KEY'),
        'aws' => [
            'region' => sw_env('AWS_REGION'),
            'bucket' => sw_env('AWS_BUCKET'),
            'key' => sw_env('AWS_ACCESS_KEY_ID'),
            'secret' => sw_env('AWS_SECRET_ACCESS_KEY'),
        ],
        'billing' => [
            'plans' => [
                ['name' => 'Basic', 'amount_in_cents' => 4900, 'yearly' => false],
                ['name' => 'Pro', 'amount_in_cents' => 9900, 'yearly' => false],
                ['name' => 'Pro anual', 'amount_in_cents' => 99000, 'yearly' => true],
            ],
        ],
        'queue' => [
            'driver' => ESystemJobs::RABBITMQ->value,
            'host' => sw_env('RABBITMQ_HOST'),
            'port' => sw_env('RABBITMQ_PORT'),
            'user' => sw_env('RABBITMQ_USER'),
            'password' => sw_env('RABBITMQ_PASSWORD'),
            'heartbeat' => 0,
        ],
        'cache' => [
            'driver' => 'redis',
            'host' => sw_env('REDIS_HOST'),
            'port' => sw_env('REDIS_PORT'),
            'password' => sw_env('REDIS_PASSWORD'),
        ],
        'logger' => [
            'discord' => [
                'webhook' => sw_env('DISCORD_LOG_WEBHOOK_URL'),
            ],
        ],
    ],
    'prod' => [],
    'test' => [],
    'dev' => [],
];
