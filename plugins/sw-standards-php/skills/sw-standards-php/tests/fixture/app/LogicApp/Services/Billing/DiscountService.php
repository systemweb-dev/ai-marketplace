<?php

namespace App\LogicApp\Services\Billing;

use App\LogicApp\Models\Customer;

final class DiscountService
{
    public static function apply(Customer $customer, int $amountInCents, ?int $discountInCents): int
    {
        // desconto zero é válido: só a ausência cai no desconto padrão do cliente
        if($discountInCents === null){
            $discountInCents = $customer->default_discount_in_cents;
        }

        return max($amountInCents - $discountInCents, 0);
    }
}
