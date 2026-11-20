<?php

use App\LogicApp\Enums\ECache;
use App\LogicApp\Services\Billing\PricingPageService;
use SysWeb\Cache\Cache;

it('monta os planos da página com o período', function () {
    Cache::delete(ECache::PRICING_PAGE->key('all'));

    $page = PricingPageService::build();

    expect($page['plans'][0])->toBe(['name' => 'Basic', 'amountInCents' => 4900, 'periodLabel' => '/mês']);
    expect($page['plans'][2]['periodLabel'])->toBe('/ano');
});
