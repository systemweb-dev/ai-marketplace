<?php

use App\LogicApp\Enums\EModelInvoiceStatus;
use Tests\Support\Fixtures;
use Tests\Support\Http;

it('recusa a lista de faturas sem token', function () {
    $response = Http::get('/api/v1/invoices');

    expect($response['status'])->toBe(401);
});

it('lista só as faturas da empresa no status pedido', function () {
    $company = Fixtures::company();
    Fixtures::invoice($company);
    Fixtures::invoice(Fixtures::company());

    $response = Http::as($company)->get('/api/v1/invoices', ['status' => EModelInvoiceStatus::OPEN->value]);

    expect($response['status'])->toBe(200);
    expect($response['json']['data'])->toHaveCount(1);
    expect(array_keys($response['json']['data'][0]))->toBe(['id', 'status', 'amount_in_cents', 'due_date']);
});

it('recusa a criação sem token', function () {
    $response = Http::post('/api/v1/invoices', ['description' => 'Mensalidade']);

    expect($response['status'])->toBe(401);
});

it('exige os campos da fatura', function () {
    $response = Http::as(Fixtures::company())->post('/api/v1/invoices', []);

    expect($response['status'])->toBe(422);
});

it('não cria fatura para cliente de outra empresa', function () {
    $customer = Fixtures::customer(Fixtures::company());

    $response = Http::as(Fixtures::company())->post('/api/v1/invoices', ['id_customer' => $customer->id, 'description' => 'Mensalidade', 'amount_in_cents' => 4900]);

    expect($response['status'])->toBe(404);
    expect($response['json']['message'])->toBe('customer_not_found');
});

it('cria a fatura e devolve só os campos da lista', function () {
    $company = Fixtures::company();
    $customer = Fixtures::customer($company);

    $response = Http::as($company)->post('/api/v1/invoices', ['id_customer' => $customer->id, 'description' => 'Mensalidade', 'amount_in_cents' => 4900]);

    expect($response['status'])->toBe(200);
    expect(array_keys($response['json']['data']))->toBe(['id', 'status', 'amount_in_cents', 'due_date']);
});

it('recusa a consulta sem token', function () {
    $response = Http::get('/api/v1/invoices/1');

    expect($response['status'])->toBe(401);
});

it('não acha a fatura de outra empresa', function () {
    $invoice = Fixtures::invoice(Fixtures::company());

    $response = Http::as(Fixtures::company())->get("/api/v1/invoices/{$invoice->id}");

    expect($response['status'])->toBe(404);
    expect($response['json']['message'])->toBe('invoice_not_found');
});

it('mostra a fatura da empresa', function () {
    $company = Fixtures::company();
    $invoice = Fixtures::invoice($company);

    $response = Http::as($company)->get("/api/v1/invoices/{$invoice->id}");

    expect($response['status'])->toBe(200);
    expect(array_keys($response['json']['data']))->toBe(['id', 'status', 'amount_in_cents', 'due_date']);
});

it('recusa o cancelamento sem token', function () {
    $response = Http::post('/api/v1/invoices/1/cancel', ['reason' => 'Pedido duplicado']);

    expect($response['status'])->toBe(401);
});

it('não cancela a fatura de outra empresa', function () {
    $invoice = Fixtures::invoice(Fixtures::company());

    $response = Http::as(Fixtures::company())->post("/api/v1/invoices/{$invoice->id}/cancel", ['reason' => 'Pedido duplicado']);

    expect($response['status'])->toBe(404);
});

it('exige o motivo do cancelamento', function () {
    $company = Fixtures::company();
    $invoice = Fixtures::invoice($company);

    $response = Http::as($company)->post("/api/v1/invoices/{$invoice->id}/cancel", []);

    expect($response['status'])->toBe(422);
});

it('cancela e devolve só os campos da lista', function () {
    $company = Fixtures::company();
    $invoice = Fixtures::invoice($company);

    $response = Http::as($company)->post("/api/v1/invoices/{$invoice->id}/cancel", ['reason' => 'Pedido duplicado']);

    expect($response['status'])->toBe(200);
    expect(array_keys($response['json']['data']))->toBe(['id', 'status', 'cancel_reason']);
});
