<?php

use App\LogicApp\Enums\EQueue;

it('usa o prefixo de teste quando APP_TESTING está ligado', function () {
    expect(EQueue::INVOICE_CREATED->queue())->toBe('billing-test--invoice-created');
});
