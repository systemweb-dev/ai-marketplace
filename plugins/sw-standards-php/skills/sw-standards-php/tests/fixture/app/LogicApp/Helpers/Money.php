<?php

namespace App\LogicApp\Helpers;

final class Money
{
    public static function centsToBrl($cents): string
    {
        return 'R$ ' . number_format($cents / 100, 2, ',', '.');
    }
}
