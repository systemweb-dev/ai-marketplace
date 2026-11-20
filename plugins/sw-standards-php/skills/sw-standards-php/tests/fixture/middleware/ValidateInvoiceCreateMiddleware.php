<?php

namespace Middleware;

use App\LogicApp\Models\Company;
use App\LogicApp\Models\Customer;
use SysWeb\Api\ResponseApi;
use SysWeb\Request\Request;
use SysWeb\Response\Response;
use SysWeb\Validator\Validator;

final class ValidateInvoiceCreateMiddleware
{
    public function __invoke(Request $request, Response $response, callable $next)
    {
        $company = Request::shared('company', Company::class);
        $data = Request::post();

        $rules = [
            'id_customer' => 'require|int',
            'description' => 'require|max:255',
            'amount_in_cents' => 'require|int',
        ];

        if(!Validator::check($data, $rules)){
            ResponseApi::error('invalid_data', Validator::error()->msg, 422);
        }

        // o min do Validator conta caracteres, não valor: pedido ao framework
        if((int) $data['amount_in_cents'] < 1){
            ResponseApi::error('amount_must_be_positive', 'Amount must be positive', 422);
        }

        $invoiceData = [
            'id_customer' => (int) $data['id_customer'],
            'description' => trim($data['description']),
            'amount_in_cents' => (int) $data['amount_in_cents'],
        ];

        // o Validator não tem campo opcional: pedido ao framework
        if(isset($data['notes'])){
            $invoiceData['notes'] = trim($data['notes']);
        }

        $customer = Customer::findByCompany($company->id, $invoiceData['id_customer']);

        if(!$customer){
            ResponseApi::error('customer_not_found', 'Customer not found', 404);
        }

        Request::share('customer', $customer);
        Request::share('invoiceData', $invoiceData);

        return $next();
    }
}
