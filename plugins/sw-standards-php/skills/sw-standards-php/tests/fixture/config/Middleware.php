<?php

return [
    'authCompany' => \Middleware\AuthCompanyMiddleware::class,
    'invoiceExists' => \Middleware\InvoiceExistsMiddleware::class,
    'validateInvoiceCreate' => \Middleware\ValidateInvoiceCreateMiddleware::class,
    'validateInvoiceCancel' => \Middleware\ValidateInvoiceCancelMiddleware::class,
    'validateCustomerCreate' => \Middleware\ValidateCustomerCreateMiddleware::class,
];
