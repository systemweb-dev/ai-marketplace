<?php

namespace Scheduler;

use App\LogicApp\Enums\EQueue;
use App\LogicApp\Models\Invoice;
use SysWeb\Jobs\Queue;

final class InvoiceOverdueScheduler
{
    public function handle(): void
    {
        $today = date('Y-m-d');
        $invoices = Invoice::listOverdue($today);

        foreach($invoices as $invoice){
            Queue::send(EQueue::INVOICE_OVERDUE->queue(), ['id_invoice' => $invoice->id]);
        }
    }
}
