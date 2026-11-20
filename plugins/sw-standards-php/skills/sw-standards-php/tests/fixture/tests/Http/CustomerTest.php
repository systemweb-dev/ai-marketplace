<?php

use Tests\Support\Fixtures;
use Tests\Support\Http;

it('recusa a lista de clientes sem token', function () {
    $response = Http::get('/api/customers');

    expect($response['status'])->toBe(401);
});

it('lista só os clientes da empresa', function () {
    $company = Fixtures::company();
    Fixtures::customer($company);
    Fixtures::customer(Fixtures::company());

    $response = Http::as($company)->get('/api/customers');

    expect($response['status'])->toBe(200);
    expect($response['json']['data'])->toHaveCount(1);
});

it('recusa a criação de cliente sem token', function () {
    $response = Http::post('/api/v1/customers', ['name' => 'Ana', 'email' => 'ana@example.com']);

    expect($response['status'])->toBe(401);
});

it('exige nome e e-mail do cliente', function () {
    $response = Http::as(Fixtures::company())->post('/api/v1/customers', []);

    expect($response['status'])->toBe(422);
});

it('recusa e-mail já cadastrado na empresa', function () {
    $company = Fixtures::company();
    Fixtures::customer($company, ['email' => 'ana@example.com']);

    $response = Http::as($company)->post('/api/v1/customers', ['name' => 'Ana', 'email' => 'ana@example.com']);

    expect($response['status'])->toBe(409);
});

it('cria o cliente e devolve só os campos da lista', function () {
    $company = Fixtures::company();

    $response = Http::as($company)->post('/api/v1/customers', ['name' => 'Ana', 'email' => 'ana@example.com']);

    expect($response['status'])->toBe(200);
    expect(array_keys($response['json']['data']))->toBe(['id', 'name', 'email']);
});
