<?php

namespace App\LogicApp\Models;

use App\LogicApp\Enums\EModelInvoiceStatus;
use SysWeb\Collection\Collection;
use SysWeb\Database\DB;
use SysWeb\Model\Model;

final class Invoice extends Model
{
    protected static $_table = 'invoice';

    public static function findByCompany(int $idCompany, int $id): ?self
    {
        return static::where(['id_company =' => $idCompany, 'AND' => ['id =' => $id]])->first();
    }

    public static function listByCompany(int $idCompany): Collection
    {
        return static::where(['id_company =' => $idCompany])->get();
    }

    public static function listOverdue(string $today): Collection
    {
        return static::where(['status =' => EModelInvoiceStatus::OPEN->value, 'AND' => ['due_date <' => $today]])->get();
    }

    public static function sumOpenByCompany(int $idCompany): int
    {
        // o builder do core não faz SUM
        $sql = 'SELECT COALESCE(SUM(amount_in_cents), 0) AS total FROM invoice WHERE id_company = :id_company AND status = :status';

        $row = DB::query($sql, ['id_company' => $idCompany, 'status' => EModelInvoiceStatus::OPEN->value])->get(true);

        return (int) $row['total'];
    }
}
