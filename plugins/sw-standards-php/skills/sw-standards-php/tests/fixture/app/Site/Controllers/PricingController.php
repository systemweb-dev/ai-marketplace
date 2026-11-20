<?php

namespace App\Site\Controllers;

use App\LogicApp\Services\Billing\PricingPageService;
use SysWeb\Controller;

final class PricingController extends Controller
{
    public function index(): void
    {
        $page = PricingPageService::build();

        sw_seo()
            ->title('Planos | Billing')
            ->description('Planos e preços do Billing')
            ->canonical('/planos');

        $this->view('pricing/index', $page);
    }
}
