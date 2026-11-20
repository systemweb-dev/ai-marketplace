<?php

namespace App\LogicApp\Enums;

enum EModelInvoiceStatus: string
{
    case OPEN = 'OPEN';
    case PAID = 'PAID';
    case OVERDUE = 'OVERDUE';
    case CANCELED = 'CANCELED';
}
