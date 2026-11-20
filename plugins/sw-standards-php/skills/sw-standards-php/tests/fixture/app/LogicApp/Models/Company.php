<?php

namespace App\LogicApp\Models;

use SysWeb\Model\Model;

final class Company extends Model
{
    protected static $_table = 'company';

    public static function findByUuid(string $uuid): ?self
    {
        return static::where(['uuid =' => $uuid])->first();
    }
}
