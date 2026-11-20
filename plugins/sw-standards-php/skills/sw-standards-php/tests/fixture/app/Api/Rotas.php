<?php

// Faturas
Rota::authJwt('', function ($auth) {
    Rota::get('v1/invoices')->controller('invoice')->method('index')->auth($auth);
    Rota::post('v1/invoices')->controller('invoice')->method('create')->auth($auth)->middlewareBefore('validateInvoiceCreate');
    Rota::get('v1/invoices/{id}')->controller('invoice')->method('show')->auth($auth)->middlewareBefore('invoiceExists');
    Rota::post('v1/invoices/{id}/cancel')->controller('invoice')->method('cancel')->auth($auth)->middlewareBefore(['invoiceExists', 'validateInvoiceCancel']);
});

// Clientes
Rota::authJwt('', function ($auth) {
    Rota::get('customers')->controller('customer')->method('index')->auth($auth);
    Rota::post('v1/customers')->controller('customer')->method('create')->auth($auth)->middlewareBefore('validateCustomerCreate');
});
