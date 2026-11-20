<?php

use App\LogicApp\Enums\EModelInvoiceStatus;
use App\LogicApp\Models\Invoice;
use App\LogicApp\Services\Billing\InvoiceCancelService;
use Tests\Support\Fixtures;

it('cancela a fatura em aberto e grava o motivo', function () {
    $invoice = Fixtures::invoice(Fixtures::company());

    InvoiceCancelService::cancel($invoice, 'Pedido duplicado');

    $saved = Invoice::find($invoice->id);
    expect($saved->status)->toBe(EModelInvoiceStatus::CANCELED->value);
    expect($saved->cancel_reason)->toBe('Pedido duplicado');
});

it('não cancela fatura paga', function () {
    $invoice = Fixtures::invoice(Fixtures::company(), ['status' => EModelInvoiceStatus::PAID->value]);

    $canceled = InvoiceCancelService::cancel($invoice, 'Pedido duplicado');

    expect($canceled)->toBe(['error' => 'invoice_already_paid', 'message' => 'Invoice already paid', 'status' => 409]);
});

it('não cancela fatura já cancelada', function () {
    $invoice = Fixtures::invoice(Fixtures::company(), ['status' => EModelInvoiceStatus::CANCELED->value]);

    $canceled = InvoiceCancelService::cancel($invoice, 'Pedido duplicado');

    expect($canceled)->toBe(['error' => 'invoice_already_canceled', 'message' => 'Invoice already canceled', 'status' => 409]);
});
