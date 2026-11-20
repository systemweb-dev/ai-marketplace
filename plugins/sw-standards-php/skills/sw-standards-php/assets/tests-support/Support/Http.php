<?php

namespace Tests\Support;

use App\LogicApp\Models\Company;
use Curl\Curl;
use SysWeb\Jwt\Jwt;

// Requisição de verdade ao TestServer. Http::get e Http::post vão sem token; Http::as($company)->post(...) vai
// autenticado. Não segue redirect, porque o redirect da rota também é comportamento a testar.
final class Http
{
    // o core escolhe o ambiente pelo Host (config/Env.php): use o host de dev do projeto
    private const HOST = 'localhost:8000';

    public function __construct(private ?string $token = null)
    {
    }

    public static function as(Company $company): self
    {
        // o payload é o que o middleware de auth do projeto lê
        return new self(Jwt::generate(['sub' => $company->uuid]));
    }

    public static function __callStatic(string $method, array $args): array
    {
        return (new self())->$method(...$args);
    }

    public function __call(string $method, array $args): array
    {
        return $this->_request(strtoupper($method), ...$args);
    }

    private function _request(string $method, string $path, array $body = []): array
    {
        $curl = new Curl();
        $curl->setHeader('Host', self::HOST);
        $curl->setHeader('Content-Type', 'application/json');
        $curl->setFollowLocation(false);
        $curl->setTimeout(20);

        if($this->token){
            $curl->setHeader('Authorization', 'Bearer ' . $this->token);
        }

        $url = TestServer::url() . '/' . ltrim($path, '/');
        match($method){
            'GET' => $curl->get($url, $body),
            'POST' => $curl->post($url, $body),
            'PUT' => $curl->put($url, $body),
            'PATCH' => $curl->patch($url, $body),
            'DELETE' => $curl->delete($url, [], $body),
        };
        // corpo vazio é resposta válida (ex.: 204); JSON quebrado faz o teste falhar com o motivo, em vez de virar []
        $body = $curl->rawResponse;
        $json = $body === '' ? [] : json_decode($body, true, 512, JSON_THROW_ON_ERROR);
        $response = ['status' => $curl->httpStatusCode, 'json' => $json];
        $curl->close();

        return $response;
    }
}
