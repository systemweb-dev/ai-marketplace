<?php

use App\LogicApp\Enums\EModelInvoiceStatus;
use App\LogicApp\Enums\EQueue;
use App\LogicApp\Models\Invoice;
use Jobs\InvoiceOverdueJob;
use Tests\Support\Fake\FakeMessage;
use Tests\Support\Fixtures;

it('marca a fatura como vencida e dá ack', function () {
    $invoice = Fixtures::invoice(Fixtures::company());
    $message = new FakeMessage(json_encode(['id_invoice' => $invoice->id]));

    (new InvoiceOverdueJob(EQueue::INVOICE_OVERDUE->queue()))->handle($message);

    expect($message->answer)->toBe('ack');
    expect(Invoice::find($invoice->id)->status)->toBe(EModelInvoiceStatus::OVERDUE->value);
});

it('dá nack quando a fatura não está em aberto', function () {
    $invoice = Fixtures::invoice(Fixtures::company(), ['status' => EModelInvoiceStatus::PAID->value]);
    $message = new FakeMessage(json_encode(['id_invoice' => $invoice->id]));

    (new InvoiceOverdueJob(EQueue::INVOICE_OVERDUE->queue()))->handle($message);

    expect($message->answer)->toBe('nack');
});

it('dá nack na mensagem quebrada', function () {
    $message = new FakeMessage('{quebrada');

    (new InvoiceOverdueJob(EQueue::INVOICE_OVERDUE->queue()))->handle($message);

    expect($message->answer)->toBe('nack');
});
