<?php

include_once __DIR__ . '/../vendor/autoload.php';

$scheduler = new \SysWeb\Scheduler\Scheduler();
$scheduler->task(\Scheduler\InvoiceOverdueScheduler::class)->hours(6)->minutes(0)->log();
$scheduler->run();
