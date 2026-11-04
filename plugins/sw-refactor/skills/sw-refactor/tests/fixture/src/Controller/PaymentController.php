<?php
final class PaymentController
{
    public function store(array $input): array
    {
        if (!isset($input['id']) || $input['id'] <= 0) {
            throw new InvalidArgumentException('invalid id');
        }
        return ['id' => $input['id']];
    }
}
