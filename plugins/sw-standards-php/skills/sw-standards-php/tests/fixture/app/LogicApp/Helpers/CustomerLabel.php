<?php

namespace App\LogicApp\Helpers;

use App\LogicApp\Models\Customer;
use App\LogicApp\Models\Invoice;

final class CustomerLabel
{
    public static function forInvoice(Invoice $invoice): string
    {
        $customer = Customer::findByCompany($invoice->id_company, $invoice->id_customer);

        return "{$customer->name} <{$customer->email}>";
    }
}
