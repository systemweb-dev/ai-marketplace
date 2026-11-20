<?php

use App\LogicApp\Enums\ECache;

it('monta a chave com o prefixo do projeto', function () {
    expect(ECache::PRICING_PAGE->key('all'))->toBe('billing:pricing-page:all');
});

it('dá TTL positivo para toda chave', function () {
    foreach(ECache::cases() as $case){
        expect($case->ttl())->toBeGreaterThan(0);
    }
});
