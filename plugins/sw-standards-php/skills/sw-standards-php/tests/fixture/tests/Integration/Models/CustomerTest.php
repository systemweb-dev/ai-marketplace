<?php

use App\LogicApp\Models\Customer;
use Tests\Support\Fixtures;

it('acha o cliente só dentro da empresa', function () {
    $company = Fixtures::company();
    $customer = Fixtures::customer($company);

    expect(Customer::findByCompany($company->id, $customer->id)->id)->toBe($customer->id);
    expect(Customer::findByCompany(Fixtures::company()->id, $customer->id))->toBeNull();
});

it('lista só os clientes da empresa', function () {
    $company = Fixtures::company();
    Fixtures::customer($company);
    Fixtures::customer(Fixtures::company());

    $customers = Customer::listByCompany($company->id);

    expect($customers->count())->toBe(1);
});

it('confere o e-mail dentro da empresa', function () {
    $company = Fixtures::company();
    Fixtures::customer($company, ['email' => 'ana@example.com']);

    expect(Customer::existsByEmail($company->id, 'ana@example.com'))->toBeTrue();
    expect(Customer::existsByEmail(Fixtures::company()->id, 'ana@example.com'))->toBeFalse();
});
