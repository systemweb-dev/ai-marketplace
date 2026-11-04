<?php
require_once __DIR__ . '/../Request/UserRequest.php';

final class UserController
{
    public function store(array $input): array
    {
        $data = UserRequest::validate($input);
        return ['id' => $data['id']];
    }
}
