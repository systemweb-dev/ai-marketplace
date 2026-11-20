<?php

use App\LogicApp\Models\Customer;
use App\LogicApp\Services\Customer\CustomerService;
use Tests\Support\Fixtures;

it('lista só os clientes da empresa', function () {
    $company = Fixtures::company();
    Fixtures::customer($company);
    Fixtures::customer(Fixtures::company());

    expect(CustomerService::listByCompany($company->id)->count())->toBe(1);
});

it('cria o cliente na empresa', function () {
    $company = Fixtures::company();

    $customer = CustomerService::create($company->id, ['name' => 'Ana', 'email' => 'ana@example.com']);

    expect(Customer::findByCompany($company->id, $customer->id)->email)->toBe('ana@example.com');
});

it('recusa e-mail já cadastrado na empresa', function () {
    $company = Fixtures::company();
    Fixtures::customer($company, ['email' => 'ana@example.com']);

    $customer = CustomerService::create($company->id, ['name' => 'Ana', 'email' => 'ana@example.com']);

    expect($customer)->toBe(['error' => 'customer_email_taken', 'message' => 'Customer email already registered', 'status' => 409]);
});
