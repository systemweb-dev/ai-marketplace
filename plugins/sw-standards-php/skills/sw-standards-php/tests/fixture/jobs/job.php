<?php

include_once __DIR__ . '/../vendor/autoload.php';

$jobs = \SysWeb\Jobs::create();
$jobs->registerJobs([
    new \Jobs\InvoiceCreatedJob(\App\LogicApp\Enums\EQueue::INVOICE_CREATED->queue()),
    new \Jobs\InvoiceOverdueJob(\App\LogicApp\Enums\EQueue::INVOICE_OVERDUE->queue()),
]);
$jobs->listen();
