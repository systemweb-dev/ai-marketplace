<?php

namespace App\LogicApp\Services\Billing;

use App\LogicApp\Enums\ECache;
use SysWeb\Cache\Cache;

final class PricingPageService
{
    public static function build(): array
    {
        $cacheKey = ECache::PRICING_PAGE->key('all');
        $cached = Cache::get($cacheKey);

        if($cached){
            return $cached;
        }

        $plans = sw_config('billing')['plans'];

        $page = ['plans' => []];

        foreach($plans as $plan){
            $page['plans'][] = [
                'name' => $plan['name'],
                'amountInCents' => $plan['amount_in_cents'],
                'periodLabel' => $plan['yearly'] ? '/ano' : '/mês',
            ];
        }

        Cache::set($cacheKey, $page);

        return $page;
    }
}
