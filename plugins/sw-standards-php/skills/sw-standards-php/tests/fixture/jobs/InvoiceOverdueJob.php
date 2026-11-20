<?php

namespace Jobs;

use App\LogicApp\Services\Billing\InvoiceService;
use SysWeb\Jobs\IJobs;
use SysWeb\Logger\DiscordLogger;
use SysWeb\Logger\ELogger;

final class InvoiceOverdueJob implements IJobs
{
    public function __construct(public string $topic)
    {
    }

    public function handle($message): void
    {
        try{
            $data = json_decode($message->body, true, 512, JSON_THROW_ON_ERROR);
            $overdue = InvoiceService::markAsOverdue($data['id_invoice']);

            if(is_array($overdue) && isset($overdue['error'])){
                $message->nack();

                return;
            }

            $message->ack();
        }catch(\Throwable $exception){
            DiscordLogger::setTitle('Job invoice-overdue failed');
            DiscordLogger::send("{$this->topic}: {$exception->getMessage()}", ELogger::ERROR);
            $message->nack();
        }
    }
}
