<?php

namespace App\LogicApp\Services\Billing;

use App\LogicApp\Enums\EModelInvoiceStatus;
use App\LogicApp\Enums\EQueue;
use App\LogicApp\Models\Customer;
use App\LogicApp\Models\Invoice;
use App\LogicApp\Models\InvoiceItem;
use Carbon\CarbonImmutable;
use SysWeb\Database\DB;
use SysWeb\Jobs\Queue;
use SysWeb\Logger\DiscordLogger;
use SysWeb\Logger\ELogger;

final class InvoiceCreateService
{
    public static function create(int $idCompany, Customer $customer, array $invoiceData): Invoice|array
    {
        $dueDays = InvoiceDueDateService::dueDays($customer);
        $dueDate = CarbonImmutable::now()->addDays($dueDays);

        DB::startTransaction();

        try{
            $invoice = new Invoice();
            $invoice->id_company = $idCompany;
            $invoice->id_customer = $customer->id;
            $invoice->description = $invoiceData['description'];
            $invoice->amount_in_cents = $invoiceData['amount_in_cents'];
            $invoice->notes = $invoiceData['notes'] ?? null;
            $invoice->status = EModelInvoiceStatus::OPEN->value;
            $invoice->due_date = $dueDate->format('Y-m-d');

            $created = $invoice->insert();

            // o builder não lança exceção quando a escrita falha: pedido ao framework
            if(!$created){
                throw new \RuntimeException('invoice insert failed');
            }

            $item = new InvoiceItem();
            $item->id_invoice = $created->id;
            $item->description = $invoiceData['description'];
            $item->amount_in_cents = $invoiceData['amount_in_cents'];

            if(!$item->insert()){
                throw new \RuntimeException('invoice_item_insert_failed');
            }

            Queue::send(EQueue::INVOICE_CREATED->queue(), ['id_invoice' => $created->id]);

            DB::commit();
        }catch(\Throwable $exception){
            DB::roolback();
            DiscordLogger::setTitle('Invoice create failed');
            DiscordLogger::send("invoice create company {$idCompany}: {$exception->getMessage()}", ELogger::ERROR);

            return ['error' => 'server_error', 'message' => 'Unexpected error', 'status' => 500];
        }

        return $created;
    }
}
