<?php

namespace Middleware;

use App\LogicApp\Models\Company;
use App\LogicApp\Models\Invoice;
use SysWeb\Api\ResponseApi;
use SysWeb\Request\Request;
use SysWeb\Response\Response;
use SysWeb\Router\Router;

final class InvoiceExistsMiddleware
{
    public function __invoke(Request $request, Response $response, callable $next)
    {
        $company = Request::shared('company', Company::class);
        $idInvoice = filter_var(Router::param('id'), FILTER_VALIDATE_INT);

        if(!$idInvoice){
            ResponseApi::error('invoice_not_found', 'Invoice not found', 404);
        }

        $invoice = Invoice::findByCompany($company->id, $idInvoice);

        if(!$invoice){
            ResponseApi::error('invoice_not_found', 'Invoice not found', 404);
        }

        Request::share('invoice', $invoice);

        return $next();
    }
}
