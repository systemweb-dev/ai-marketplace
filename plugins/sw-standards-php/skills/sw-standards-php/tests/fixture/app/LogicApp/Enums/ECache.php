<?php

namespace App\LogicApp\Enums;

enum ECache: string
{
    case PRICING_PAGE = 'pricing-page';

    public function key(int|string $id): string
    {
        return "billing:{$this->value}:{$id}";
    }

    public function ttl(): int
    {
        return match($this){
            self::PRICING_PAGE => 3600,
        };
    }
}
