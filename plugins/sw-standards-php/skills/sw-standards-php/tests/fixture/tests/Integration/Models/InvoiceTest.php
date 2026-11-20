<?php

use App\LogicApp\Enums\EModelInvoiceStatus;
use App\LogicApp\Models\Invoice;
use Tests\Support\Fixtures;

it('acha a fatura só dentro da empresa', function () {
    $company = Fixtures::company();
    $invoice = Fixtures::invoice($company);

    expect(Invoice::findByCompany($company->id, $invoice->id)->id)->toBe($invoice->id);
    expect(Invoice::findByCompany(Fixtures::company()->id, $invoice->id))->toBeNull();
});

it('lista só as faturas da empresa', function () {
    $company = Fixtures::company();
    Fixtures::invoice($company);
    Fixtures::invoice(Fixtures::company());

    $invoices = Invoice::listByCompany($company->id);

    expect($invoices->count())->toBe(1);
});

it('lista as faturas em aberto vencidas antes do dia', function () {
    $company = Fixtures::company();
    Fixtures::invoice($company, ['due_date' => '2026-01-10']);
    Fixtures::invoice($company, ['due_date' => '2026-01-20']);
    Fixtures::invoice($company, ['due_date' => '2026-01-05', 'status' => EModelInvoiceStatus::PAID->value]);

    $invoices = Invoice::listOverdue('2026-01-15');

    expect($invoices->count())->toBe(1);
});

it('soma só as faturas em aberto da empresa', function () {
    $company = Fixtures::company();
    Fixtures::invoice($company, ['amount_in_cents' => 1000]);
    Fixtures::invoice($company, ['amount_in_cents' => 2500]);
    Fixtures::invoice($company, ['amount_in_cents' => 9999, 'status' => EModelInvoiceStatus::CANCELED->value]);
    Fixtures::invoice(Fixtures::company(), ['amount_in_cents' => 7000]);

    expect(Invoice::sumOpenByCompany($company->id))->toBe(3500);
});

it('soma zero quando a empresa não tem fatura em aberto', function () {
    expect(Invoice::sumOpenByCompany(Fixtures::company()->id))->toBe(0);
});
