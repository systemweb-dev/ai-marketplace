<?php
require_once __DIR__ . '/../Request/CouponRequest.php';

final class CouponController
{
    public function store(array $input): array
    {
        $data = CouponRequest::validate($input);
        return ['id' => $data['id']];
    }
}
