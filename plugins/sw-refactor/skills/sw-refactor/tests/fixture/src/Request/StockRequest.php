<?php
final class StockRequest
{
    public static function validate(array $input): array
    {
        if (!isset($input['id']) || $input['id'] <= 0) {
            throw new InvalidArgumentException('invalid id');
        }
        return $input;
    }
}
