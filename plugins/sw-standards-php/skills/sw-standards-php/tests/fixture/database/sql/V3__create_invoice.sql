CREATE TABLE invoice (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_company INT UNSIGNED NOT NULL,
    id_customer INT UNSIGNED NOT NULL,
    description VARCHAR(255) NOT NULL,
    amount_in_cents INT NOT NULL,
    notes VARCHAR(500) NULL,
    status VARCHAR(20) NOT NULL,
    due_date DATE NOT NULL,
    receipt_path VARCHAR(255) NULL,
    cancel_reason VARCHAR(255) NULL,
    canceled_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_invoice_company_status (id_company, status),
    KEY idx_invoice_status_due_date (status, due_date),
    CONSTRAINT fk_invoice_company FOREIGN KEY (id_company) REFERENCES company (id),
    CONSTRAINT fk_invoice_customer FOREIGN KEY (id_customer) REFERENCES customer (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE invoice_item (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_invoice INT UNSIGNED NOT NULL,
    description VARCHAR(255) NOT NULL,
    amount_in_cents INT NOT NULL,
    CONSTRAINT fk_invoice_item_invoice FOREIGN KEY (id_invoice) REFERENCES invoice (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
