<?php

namespace App\LogicApp\Services\Billing;

use App\LogicApp\Enums\EModelInvoiceStatus;
use App\LogicApp\Helpers\Money;
use App\LogicApp\Integrations\Aws\Aws;
use App\LogicApp\Models\Invoice;
use SysWeb\Collection\Collection;

final class InvoiceService
{
    public static function listByCompany(int $idCompany, string $status): Collection
    {
        $invoices = Invoice::where(['id_company =' => $idCompany, 'AND' => ['status =' => $status]])->get();

        return $invoices;
    }

    public static function issue(int $idInvoice): Invoice|array
    {
        $invoice = Invoice::find($idInvoice);

        if(!$invoice){
            return ['error' => 'invoice_not_found', 'message' => 'Invoice not found', 'status' => 404];
        }

        $amountLabel = Money::centsToBrl($invoice->amount_in_cents);
        $receipt = "Invoice {$invoice->id}: {$invoice->description} - {$amountLabel}";

        $invoice->receipt_path = Aws::instance()->put("receipts/{$invoice->id}.txt", $receipt);
        $invoice->save();

        return $invoice;
    }

    public static function markAsOverdue(int $idInvoice): Invoice|array
    {
        $invoice = Invoice::find($idInvoice);

        if(!$invoice){
            return ['error' => 'invoice_not_found', 'message' => 'Invoice not found', 'status' => 404];
        }

        if($invoice->status !== EModelInvoiceStatus::OPEN->value){
            return ['error' => 'invoice_not_open', 'message' => 'Invoice is not open', 'status' => 409];
        }

        $invoice->status = EModelInvoiceStatus::OVERDUE->value;
        $invoice->save();

        return $invoice;
    }
}
