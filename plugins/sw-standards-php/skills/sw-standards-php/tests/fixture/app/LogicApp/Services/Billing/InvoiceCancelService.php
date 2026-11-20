<?php

namespace App\LogicApp\Services\Billing;

use App\LogicApp\Enums\EModelInvoiceStatus;
use App\LogicApp\Models\Invoice;
use Carbon\CarbonImmutable;

final class InvoiceCancelService
{
    public static function cancel(Invoice $invoice, string $reason): Invoice|array
    {
        if($invoice->status === EModelInvoiceStatus::PAID->value){
            return ['error' => 'invoice_already_paid', 'message' => 'Invoice already paid', 'status' => 409];
        }

        if($invoice->status === EModelInvoiceStatus::CANCELED->value){
            return ['error' => 'invoice_already_canceled', 'message' => 'Invoice already canceled', 'status' => 409];
        }

        $canceledAt = CarbonImmutable::now();

        $invoice->status = 'CANCELED';
        $invoice->cancel_reason = $reason;
        $invoice->canceled_at = $canceledAt->format('Y-m-d H:i:s');
        $invoice->save();

        return $invoice;
    }
}
