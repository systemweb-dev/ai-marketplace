<?php

namespace Middleware;

use SysWeb\Api\ResponseApi;
use SysWeb\Request\Request;
use SysWeb\Response\Response;
use SysWeb\Validator\Validator;

final class ValidateCustomerCreateMiddleware
{
    public function __invoke(Request $request, Response $response, callable $next)
    {
        $data = Request::post();

        $rules = [
            'name' => 'require|max:255',
            'email' => 'require|email|max:255',
        ];

        if(!Validator::check($data, $rules)){
            ResponseApi::error('invalid_data', Validator::error()->msg);
        }

        Request::share('customerData', [
            'name' => trim($data['name']),
            'email' => strtolower(trim($data['email'])),
        ]);

        return $next();
    }
}
