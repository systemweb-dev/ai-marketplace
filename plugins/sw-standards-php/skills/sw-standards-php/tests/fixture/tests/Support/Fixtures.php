<?php

// Exceção à regra banco-no-model: truncar todas as tabelas entre testes não é operação de um model.
// Vale só para tests/Support/; os dados de teste continuam sendo criados pelo ORM.

namespace Tests\Support;

use App\LogicApp\Enums\EModelInvoiceStatus;
use App\LogicApp\Models\Company;
use App\LogicApp\Models\Customer;
use App\LogicApp\Models\Invoice;
use Carbon\CarbonImmutable;
use SysWeb\Database\DB;
use SysWeb\Help\Help;

// Dados de teste com nome, sempre pelo ORM: o teste diz Fixtures::company(), não monta SQL.
final class Fixtures
{
    // tabelas com dado de referência que as migrations semeiam e o teste não recria
    private const KEEP = [];

    public static function truncate(): void
    {
        $tables = DB::query("SELECT table_name AS name FROM information_schema.tables WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'")->get();

        DB::query('SET FOREIGN_KEY_CHECKS = 0')->get();

        foreach(array_diff(array_column($tables, 'name'), self::KEEP) as $table){
            DB::query("TRUNCATE TABLE `{$table}`")->get();
        }

        DB::query('SET FOREIGN_KEY_CHECKS = 1')->get();
    }

    public static function company(): Company
    {
        $company = new Company();
        $company->uuid = Help::generateUuid();
        $company->name = 'Empresa ' . substr($company->uuid, 0, 6);

        return $company->insert();
    }

    public static function customer(Company $company, array $attributes = []): Customer
    {
        $values = $attributes + [
            'name' => 'Cliente',
            'email' => uniqid('cliente-') . '@example.com',
            'is_partner' => 0,
            'default_discount_in_cents' => 0,
        ];

        $customer = new Customer();
        $customer->id_company = $company->id;

        foreach($values as $column => $value){
            $customer->$column = $value;
        }

        return $customer->insert();
    }

    public static function invoice(Company $company, array $attributes = []): Invoice
    {
        $dueDate = CarbonImmutable::now()->addDays(30);

        $values = $attributes + [
            'id_customer' => self::customer($company)->id,
            'description' => 'Mensalidade',
            'amount_in_cents' => 4900,
            'status' => EModelInvoiceStatus::OPEN->value,
            'due_date' => $dueDate->format('Y-m-d'),
        ];

        $invoice = new Invoice();
        $invoice->id_company = $company->id;

        foreach($values as $column => $value){
            $invoice->$column = $value;
        }

        return $invoice->insert();
    }
}
