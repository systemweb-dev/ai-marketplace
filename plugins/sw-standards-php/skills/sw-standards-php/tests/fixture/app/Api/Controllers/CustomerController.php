<?php

namespace App\Api\Controllers;

use App\LogicApp\Models\Company;
use App\LogicApp\Services\Customer\CustomerService;
use SysWeb\Api\Api;
use SysWeb\Api\ResponseApi;
use SysWeb\Controller;

final class CustomerController extends Controller
{
    public function index(): void
    {
        $company = $this->shared('company', Company::class);

        $customers = CustomerService::listByCompany($company->id);

        ResponseApi::success('customers_found', Api::returnAttributes($customers, ['id', 'name', 'email']));
    }

    public function create(): void
    {
        $company = $this->shared('company', Company::class);
        $customerData = $this->shared('customerData');

        $customer = CustomerService::create($company->id, $customerData);

        if(is_array($customer) && isset($customer['error'])){
            ResponseApi::error($customer['error'], $customer['message'], $customer['status']);
        }

        ResponseApi::success('customer_created', Api::returnAttributes($customer, ['id', 'name', 'email']));
    }
}
