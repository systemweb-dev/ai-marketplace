<?php

namespace App\Api\Controllers;

use App\LogicApp\Models\Company;
use App\LogicApp\Models\Customer;
use App\LogicApp\Models\Invoice;
use App\LogicApp\Services\Billing\InvoiceCancelService;
use App\LogicApp\Services\Billing\InvoiceCreateService;
use App\LogicApp\Services\Billing\InvoiceService;
use SysWeb\Api\Api;
use SysWeb\Api\ResponseApi;
use SysWeb\Controller;
use SysWeb\Request\Request;

final class InvoiceController extends Controller
{
    public function index(): void
    {
        $company = $this->shared('company', Company::class);
        $status = Request::get('status');

        $invoices = InvoiceService::listByCompany($company->id, $status);

        ResponseApi::success('invoices_found', Api::returnAttributes($invoices, ['id', 'status', 'amount_in_cents', 'due_date']));
    }

    public function create(): void
    {
        $company = $this->shared('company', Company::class);
        $customer = $this->shared('customer', Customer::class);
        $invoiceData = $this->shared('invoiceData');

        $invoice = InvoiceCreateService::create($company->id, $customer, $invoiceData);

        if(is_array($invoice) && isset($invoice['error'])){
            ResponseApi::error($invoice['error'], $invoice['message'], $invoice['status']);
        }

        ResponseApi::success('invoice_created', Api::returnAttributes($invoice, ['id', 'status', 'amount_in_cents', 'due_date']));
    }

    public function show(): void
    {
        $invoice = $this->shared('invoice', Invoice::class);

        ResponseApi::success('invoice_found', $this->_invoiceAttributes($invoice));
    }

    public function cancel(): void
    {
        $invoice = $this->shared('invoice', Invoice::class);
        $reason = $this->shared('cancelReason');

        $canceled = InvoiceCancelService::cancel($invoice, $reason);

        if(is_array($canceled) && isset($canceled['error'])){
            ResponseApi::error($canceled['error'], $canceled['message'], $canceled['status']);
        }

        ResponseApi::success('invoice_canceled', Api::returnAttributes($canceled, ['id', 'status', 'cancel_reason']));
    }

    private function _invoiceAttributes(Invoice $invoice): array
    {
        return Api::returnAttributes($invoice, ['id', 'status', 'amount_in_cents', 'due_date']);
    }
}
