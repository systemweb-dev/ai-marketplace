<?php

namespace App\LogicApp\Services\Billing;

use App\LogicApp\Models\Customer;

final class InvoiceDueDateService
{
    public static function dueDays(Customer $customer): int
    {
        if($customer->is_partner){
            $dueDays = 45;
        }else{
            $dueDays = 30;
        }

        return $dueDays;
    }
}
