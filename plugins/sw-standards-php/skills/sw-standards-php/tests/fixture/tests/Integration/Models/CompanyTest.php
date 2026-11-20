<?php

use App\LogicApp\Models\Company;
use Tests\Support\Fixtures;

it('acha a empresa pelo uuid', function () {
    $company = Fixtures::company();

    $found = Company::findByUuid($company->uuid);

    expect($found->id)->toBe($company->id);
});

it('não acha uuid inexistente', function () {
    expect(Company::findByUuid('00000000-0000-0000-0000-000000000000'))->toBeNull();
});
