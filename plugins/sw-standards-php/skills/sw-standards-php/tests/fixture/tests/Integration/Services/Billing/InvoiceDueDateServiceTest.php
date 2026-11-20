<?php

use App\LogicApp\Services\Billing\InvoiceDueDateService;
use Tests\Support\Fixtures;

it('dá 45 dias ao cliente parceiro', function () {
    $customer = Fixtures::customer(Fixtures::company(), ['is_partner' => 1]);

    expect(InvoiceDueDateService::dueDays($customer))->toBe(45);
});

it('dá 30 dias ao cliente comum', function () {
    $customer = Fixtures::customer(Fixtures::company());

    expect(InvoiceDueDateService::dueDays($customer))->toBe(30);
});
