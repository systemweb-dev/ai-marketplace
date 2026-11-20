<?php

return [
    'application' => 'website',
    'prod' => [
        'env' => 'billing.example.com',
        'display_errors' => false,
    ],
    'test' => [
        'env' => 'test.billing.example.com',
        'display_errors' => true,
    ],
    'dev' => [
        'env' => ['localhost:8000', 'billing.local'],
        'display_errors' => true,
    ],
];
