<?php

namespace Middleware;

use SysWeb\Api\ResponseApi;
use SysWeb\Request\Request;
use SysWeb\Response\Response;
use SysWeb\Validator\Validator;

final class ValidateInvoiceCancelMiddleware
{
    public function __invoke(Request $request, Response $response, callable $next)
    {
        $data = Request::post();

        $rules = [
            'reason' => 'require|max:255',
        ];

        if(!Validator::check($data, $rules)){
            ResponseApi::error('invalid_data', Validator::error()->msg, 422);
        }

        Request::share('cancelReason', trim($data['reason']));

        return $next();
    }
}
