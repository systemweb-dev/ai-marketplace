<?php

namespace App\LogicApp\Services\Customer;

use App\LogicApp\Models\Customer;
use SysWeb\Collection\Collection;

final class CustomerService
{
    public static function listByCompany(int $idCompany): Collection
    {
        return Customer::listByCompany($idCompany);
    }

    public static function create(int $idCompany, array $customerData): Customer|array
    {
        $exists = Customer::existsByEmail((int) $idCompany, $customerData['email']);

        if($exists){
            return ['error' => 'customer_email_taken', 'message' => 'Customer email already registered', 'status' => 409];
        }

        $customer = new Customer();
        $customer->id_company = $idCompany;
        $customer->name = $customerData['name'];
        $customer->email = $customerData['email'];

        return $customer->insert();
    }
}
