<?php
require_once __DIR__ . '/../Request/TaxRequest.php';

final class TaxController
{
    public function store(array $input): array
    {
        $data = TaxRequest::validate($input);
        return ['id' => $data['id']];
    }
}
