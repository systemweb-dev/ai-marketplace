<?php

namespace Tests\Support\Fake;

// Mensagem da fila sem o RabbitMQ: o teste de job confere qual resposta o job deu.
final class FakeMessage
{
    public ?string $answer = null;

    public function __construct(public string $body)
    {
    }

    public function ack(): void
    {
        $this->answer = 'ack';
    }

    public function nack(): void
    {
        $this->answer = 'nack';
    }
}
