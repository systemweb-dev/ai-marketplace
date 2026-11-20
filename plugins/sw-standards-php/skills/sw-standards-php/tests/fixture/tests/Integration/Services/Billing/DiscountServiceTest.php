<?php

use App\LogicApp\Services\Billing\DiscountService;
use Tests\Support\Fixtures;

it('usa o desconto padrão do cliente quando não vem desconto', function () {
    $customer = Fixtures::customer(Fixtures::company(), ['default_discount_in_cents' => 500]);

    expect(DiscountService::apply($customer, 4900, null))->toBe(4400);
});

it('respeita o desconto zero sem cair no padrão', function () {
    $customer = Fixtures::customer(Fixtures::company(), ['default_discount_in_cents' => 500]);

    expect(DiscountService::apply($customer, 4900, 0))->toBe(4900);
});

it('não deixa o valor ficar negativo', function () {
    $customer = Fixtures::customer(Fixtures::company());

    expect(DiscountService::apply($customer, 4900, 9000))->toBe(0);
});
