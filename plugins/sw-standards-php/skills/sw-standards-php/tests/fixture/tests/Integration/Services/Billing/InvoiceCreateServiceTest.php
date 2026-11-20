<?php

use App\LogicApp\Enums\EModelInvoiceStatus;
use App\LogicApp\Models\Invoice;
use App\LogicApp\Services\Billing\InvoiceCreateService;
use Carbon\CarbonImmutable;
use Tests\Support\Fixtures;

it('cria a fatura em aberto com o vencimento do cliente', function () {
    CarbonImmutable::setTestNow('2026-03-01 10:00:00');
    $company = Fixtures::company();
    $customer = Fixtures::customer($company);

    $invoice = InvoiceCreateService::create($company->id, $customer, ['description' => 'Mensalidade', 'amount_in_cents' => 4900]);

    $saved = Invoice::find($invoice->id);
    expect($saved->status)->toBe(EModelInvoiceStatus::OPEN->value);
    expect($saved->due_date)->toBe('2026-03-31');
    expect($saved->notes)->toBeNull();
});

it('grava a observação quando ela vem', function () {
    $company = Fixtures::company();
    $customer = Fixtures::customer($company);

    $invoice = InvoiceCreateService::create($company->id, $customer, ['description' => 'Mensalidade', 'amount_in_cents' => 4900, 'notes' => 'Pagar até o dia 10']);

    expect(Invoice::find($invoice->id)->notes)->toBe('Pagar até o dia 10');
});
