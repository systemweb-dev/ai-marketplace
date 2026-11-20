<?php

namespace App\LogicApp\Enums;

enum EQueue: string
{
    case INVOICE_CREATED = 'invoice-created';
    case INVOICE_OVERDUE = 'invoice-overdue';

    public function queue(): string
    {
        $prefix = getenv('APP_TESTING') ? 'billing-test--' : 'billing--';

        return $prefix . $this->value;
    }
}
