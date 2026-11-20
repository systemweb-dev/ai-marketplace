<?php

use App\LogicApp\Enums\EQueue;
use App\LogicApp\Models\Invoice;
use Jobs\InvoiceCreatedJob;
use Tests\Support\Fake\FakeMessage;
use Tests\Support\Fixtures;

it('emite o recibo e dá ack', function () {
    $invoice = Fixtures::invoice(Fixtures::company());
    $message = new FakeMessage(json_encode(['id_invoice' => $invoice->id]));

    (new InvoiceCreatedJob(EQueue::INVOICE_CREATED->queue()))->handle($message);

    expect($message->answer)->toBe('ack');
    expect(Invoice::find($invoice->id)->receipt_path)->toBe("receipts/{$invoice->id}.txt");
});

it('dá nack na mensagem quebrada', function () {
    $message = new FakeMessage('{quebrada');

    (new InvoiceCreatedJob(EQueue::INVOICE_CREATED->queue()))->handle($message);

    expect($message->answer)->toBe('nack');
});
