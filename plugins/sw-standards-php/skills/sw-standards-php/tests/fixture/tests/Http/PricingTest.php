<?php

use Tests\Support\Http;

it('mostra a página de planos', function () {
    $response = Http::get('/planos');

    expect($response['status'])->toBe(200);
});
