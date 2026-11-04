<?php
require_once __DIR__ . '/../Request/RefundRequest.php';

final class RefundController
{
    public function store(array $input): array
    {
        $data = RefundRequest::validate($input);
        return ['id' => $data['id']];
    }
}
