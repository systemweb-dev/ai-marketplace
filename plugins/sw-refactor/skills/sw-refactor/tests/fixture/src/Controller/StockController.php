<?php
require_once __DIR__ . '/../Request/StockRequest.php';

final class StockController
{
    public function store(array $input): array
    {
        $data = StockRequest::validate($input);
        return ['id' => $data['id']];
    }
}
