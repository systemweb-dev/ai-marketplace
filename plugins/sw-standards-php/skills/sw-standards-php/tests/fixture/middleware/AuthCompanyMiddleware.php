<?php

namespace Middleware;

use App\LogicApp\Models\Company;
use SysWeb\Api\ResponseApi;
use SysWeb\Jwt\Jwt;
use SysWeb\Request\Request;
use SysWeb\Response\Response;

final class AuthCompanyMiddleware
{
    public function __invoke(Request $request, Response $response, callable $next)
    {
        $payload = Jwt::getPayload();

        if(!$payload){
            ResponseApi::error('unauthenticated', 'Unauthenticated', 401);
        }

        $company = Company::findByUuid($payload['sub']);

        if(!$company){
            ResponseApi::error('unauthenticated', 'Unauthenticated', 401);
        }

        Request::share('company', $company);

        return $next();
    }
}
