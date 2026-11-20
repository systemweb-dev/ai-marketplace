<?php

include_once __DIR__ . '/../vendor/autoload.php';

require __DIR__ . '/../config/ExceptionHandler.php';

$start = new SysWeb\System();
$start->start();
