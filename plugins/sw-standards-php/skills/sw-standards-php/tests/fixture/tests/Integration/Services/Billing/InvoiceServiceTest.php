<?php

use App\LogicApp\Enums\EModelInvoiceStatus;
use App\LogicApp\Integrations\Aws\Aws;
use App\LogicApp\Integrations\Aws\AwsStorage;
use App\LogicApp\Models\Invoice;
use App\LogicApp\Services\Billing\InvoiceService;
use Tests\Support\Fixtures;

it('lista as faturas da empresa no status pedido', function () {
    $company = Fixtures::company();
    Fixtures::invoice($company);
    Fixtures::invoice($company, ['status' => EModelInvoiceStatus::PAID->value]);
    Fixtures::invoice(Fixtures::company());

    $invoices = InvoiceService::listByCompany($company->id, EModelInvoiceStatus::OPEN->value);

    expect($invoices->count())->toBe(1);
});

it('grava o recibo da fatura no storage', function () {
    $invoice = Fixtures::invoice(Fixtures::company());
    $storage = Mockery::mock(AwsStorage::class);
    $storage->shouldReceive('put')->once()->andReturn("receipts/{$invoice->id}.txt");
    Aws::fake($storage);

    $issued = InvoiceService::issue($invoice->id);

    expect($issued->receipt_path)->toBe("receipts/{$invoice->id}.txt");
});

it('não emite recibo de fatura inexistente', function () {
    $issued = InvoiceService::issue(999999);

    expect($issued)->toBe(['error' => 'invoice_not_found', 'message' => 'Invoice not found', 'status' => 404]);
});

it('marca como vencida a fatura em aberto', function () {
    $invoice = Fixtures::invoice(Fixtures::company());

    InvoiceService::markAsOverdue($invoice->id);

    expect(Invoice::find($invoice->id)->status)->toBe(EModelInvoiceStatus::OVERDUE->value);
});

it('não marca como vencida a fatura que não está em aberto', function () {
    $invoice = Fixtures::invoice(Fixtures::company(), ['status' => EModelInvoiceStatus::PAID->value]);

    $overdue = InvoiceService::markAsOverdue($invoice->id);

    expect($overdue)->toBe(['error' => 'invoice_not_open', 'message' => 'Invoice is not open', 'status' => 409]);
});
