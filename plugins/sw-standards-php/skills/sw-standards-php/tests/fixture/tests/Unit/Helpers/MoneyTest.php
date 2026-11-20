<?php

use App\LogicApp\Helpers\Money;

it('formata centavos em reais', function () {
    expect(Money::centsToBrl(123456))->toBe('R$ 1.234,56');
});

it('formata zero centavos', function () {
    expect(Money::centsToBrl(0))->toBe('R$ 0,00');
});
