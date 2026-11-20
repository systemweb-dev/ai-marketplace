# Jobs e scheduler

## Regra
Job e scheduler são finos, como o controller. O **job** lê a mensagem, chama o service e termina sempre com
`$message->ack()` ou `$message->nack()`, um dos dois em todo caminho. O **scheduler** busca os registros por um
método do model e publica um item na fila por registro; quem faz o trabalho é o job. Os nomes das filas ficam no
enum `EQueue` (`app/LogicApp/Enums/EQueue.php`), com um método que devolve o nome com prefixo do projeto e um
prefixo separado para teste. A publicação acontece só depois do commit, e o payload leva só ids (veja
`transacao-e-fila.md`). O worker sobe com `Jobs::create()`, em `jobs/job.php`, e o scheduler com
`new Scheduler()`, em `scheduler/scheduler.php`.

## Por quê
Regra de negócio dentro do job não tem teste e se repete quando a mesma ação também roda pela API. Mensagem sem
`ack` nem `nack` fica presa: o RabbitMQ a devolve para a fila e o worker a reprocessa sem fim. Exceção que escapa
do `handle` derruba o consumo e o core reconecta, com a mensagem ainda sem resposta. No worker não há o tratador
global da API, por isso o job é o único lugar que pode logar e dar `nack`. O `nack` manda a mensagem para a fila de
falhas que o core declara, onde ela pode ser vista e reenviada. Scheduler que processa tudo sozinho prende o cron
num laço longo e não paraleliza; publicando um item por registro, os workers dividem o trabalho e uma falha não
para os outros. Nome de fila solto em string vira erro de digitação, e sem o prefixo de teste o Pest publica na
fila que o worker de dev consome.

## Certo
O enum das filas:

```php
namespace App\LogicApp\Enums;

enum EQueue: string
{
    case SEND_INVOICE_EMAIL = 'send-invoice-email';
    case SEND_INVOICE_REMINDER = 'send-invoice-reminder';

    public function queue(): string
    {
        $prefix = getenv('APP_TESTING') ? 'billing-test--' : 'billing--';

        return $prefix . $this->value;
    }
}
```

O job:

```php
namespace Jobs;

use App\LogicApp\Services\Billing\InvoiceEmailService;
use SysWeb\Jobs\IJobs;
use SysWeb\Logger\DiscordLogger;
use SysWeb\Logger\ELogger;

final class SendInvoiceEmailJob implements IJobs
{
    public function __construct(public string $topic)
    {
    }

    public function handle($message): void
    {
        try{
            $data = json_decode($message->body, true, 512, JSON_THROW_ON_ERROR);
            $sent = InvoiceEmailService::send($data['id_invoice']);

            if(is_array($sent) && isset($sent['error'])){
                $message->nack();

                return;
            }

            $message->ack();
        }catch(\Throwable $exception){
            DiscordLogger::setTitle('Job send-invoice-email failed');
            DiscordLogger::send("{$this->topic}: {$exception->getMessage()}", ELogger::ERROR);
            $message->nack();
        }
    }
}
```

O scheduler busca pelo model e publica um item por registro:

```php
namespace Scheduler;

use App\LogicApp\Enums\EQueue;
use App\LogicApp\Models\Invoice;
use SysWeb\Jobs\Queue;

final class InvoiceReminderScheduler
{
    public function handle(): void
    {
        $invoices = Invoice::listDueTomorrow();

        foreach($invoices as $invoice){
            Queue::send(EQueue::SEND_INVOICE_REMINDER->queue(), ['id_invoice' => $invoice->id]);
        }
    }
}
```

O worker (`jobs/job.php`) e o agendamento (`scheduler/scheduler.php`):

```php
include_once __DIR__ . '/../vendor/autoload.php';

$jobs = \SysWeb\Jobs::create();
$jobs->registerJobs([
    new \Jobs\SendInvoiceEmailJob(\App\LogicApp\Enums\EQueue::SEND_INVOICE_EMAIL->queue()),
    new \Jobs\SendInvoiceReminderJob(\App\LogicApp\Enums\EQueue::SEND_INVOICE_REMINDER->queue()),
]);
$jobs->listen();
```

```php
include_once __DIR__ . '/../vendor/autoload.php';

$scheduler = new \SysWeb\Scheduler\Scheduler();
$scheduler->task(\Scheduler\InvoiceReminderScheduler::class)->hours(9)->minutes(0)->log();
$scheduler->run();
```

## Errado
```php
class SendInvoiceEmailJob implements IJobs
{
    public function handle($message)
    {
        $data = json_decode($message->body, true);
        $invoice = Invoice::where(['id =' => $data['invoice']['id']])->first();
        if ($invoice->status == 'canceled') {
            return;
        }
        $html = '<p>Fatura ' . $invoice->number . ' de R$ ' . number_format($invoice->amount / 100, 2, ',', '.') . '</p>';
        (new SendGrid(sw_env('SENDGRID_KEY')))->send($invoice->email, 'Sua fatura', $html);
        $message->ack();
    }
}

// no scheduler
foreach (Invoice::where(['due_date =' => date('Y-m-d', strtotime('+1 day'))])->get() as $invoice) {
    $html = '...';
    (new SendGrid(sw_env('SENDGRID_KEY')))->send($invoice->email, 'Lembrete', $html);
}

Queue::send('send-invoice-email', $invoice->toArray());
```

Query, regra e montagem de e-mail no job, caminho que sai sem `ack` nem `nack` (a fatura cancelada volta para a
fila para sempre), exceção do `json_decode` ou do SendGrid sem `nack`, scheduler que faz o trabalho todo num laço
com query no cabeçalho, fila em string solta e payload com o registro inteiro.

## Como reconhecer
- Em `jobs/`: `DB::`, `Model::where(`, SQL, montagem de HTML ou chamada direta a SDK; mais de uma chamada de
  service no `handle`.
- `handle` com algum caminho (um `return`, um `catch`, o fim do método) sem `->ack()` nem `->nack()`.
- `handle` sem `try/catch` em volta da leitura da mensagem e da chamada ao service.
- `json_decode($message->body` sem `JSON_THROW_ON_ERROR`.
- Em `scheduler/`: envio de e-mail, chamada de integração ou escrita no banco dentro do laço, em vez de
  `Queue::send` por registro; query montada no scheduler em vez de método do model.
- `Queue::send('nome-solto'` ou `new XJob('nome-solto')`: fila fora do `EQueue`.
- `EQueue` sem o prefixo de teste, ou fila com o mesmo nome em teste e em dev.
- Worker que não usa `Jobs::create()` ou que instancia o consumidor do RabbitMQ à mão.

## Como corrigir
1. Crie (ou complete) o `EQueue` com um caso por fila e o método `queue()` com o prefixo do projeto e o de teste;
   troque toda string de fila por `EQueue::CASO->queue()`, no `Queue::send` e no `registerJobs`.
2. Leve a regra do job para um service do domínio, que devolve o dado ou o array de erro (veja
   `erro-e-resposta.md`), e a query para um método do model.
3. Deixe o `handle` com duas partes: `try` com a leitura, a chamada ao service, o teste do erro
   (`is_array($x) && isset($x['error'])`, que dá `nack`) e o `ack` no fim; `catch` com log e `nack`.
4. No scheduler, troque o trabalho do laço por `Queue::send` de um item por registro, com só o id, e crie o job que
   consome essa fila.
5. Reduza os payloads aos ids e registre os jobs novos no `jobs/job.php`.

```php
public function handle($message): void
{
    try{
        $data = json_decode($message->body, true, 512, JSON_THROW_ON_ERROR);
        $sent = InvoiceReminderService::send($data['id_invoice']);

        if(is_array($sent) && isset($sent['error'])){
            $message->nack();

            return;
        }

        $message->ack();
    }catch(\Throwable $exception){
        DiscordLogger::setTitle('Job send-invoice-reminder failed');
        DiscordLogger::send("{$this->topic}: {$exception->getMessage()}", ELogger::ERROR);
        $message->nack();
    }
}
```

## Enquanto o core não corrigir
Vale para o core até a 1.11.0, inclusive; confira o CHANGELOG do core instalado.

- **`IJobs::handle($response)` não tem tipo.** O parâmetro do job fica sem tipo (tipar como `AMQPMessage` quebra a
  assinatura da interface); o retorno pode e deve ser `: void`.
- **`Queue::send` não tem `fake()`.** Nos testes, o `Support/Boot.php` liga o `APP_TESTING` e o `EQueue` devolve o
  nome com o prefixo de teste, que nenhum worker escuta. O teste confere o resultado do service, não a
  publicação.
- **O worker não passa pelo tratador global** (`www/index.php` não roda no `jobs/job.php`): o `try/catch` do
  `handle` é o que loga e dá `nack`. Sai quando o core tratar a exceção do job no `listen()`.
