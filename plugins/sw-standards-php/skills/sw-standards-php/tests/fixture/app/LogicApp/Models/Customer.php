<?php

namespace App\LogicApp\Models;

use SysWeb\Collection\Collection;
use SysWeb\Model\Model;

final class Customer extends Model
{
    protected static $_table = 'customer';

    public static function findByCompany(int $idCompany, int $id): ?self
    {
        return static::where(['id_company =' => $idCompany, 'AND' => ['id =' => $id]])->first();
    }

    public static function listByCompany(int $idCompany): Collection
    {
        return static::where(['id_company =' => $idCompany])->get();
    }

    public static function existsByEmail(int $idCompany, string $email): bool
    {
        $customer = static::where(['id_company =' => $idCompany, 'AND' => ['email =' => $email]])->first();

        return (bool) $customer;
    }
}
