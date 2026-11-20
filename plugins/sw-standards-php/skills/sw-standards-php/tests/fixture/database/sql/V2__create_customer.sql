CREATE TABLE customer (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    id_company INT UNSIGNED NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    is_partner TINYINT(1) NOT NULL DEFAULT 0,
    default_discount_in_cents INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_customer_company_email (id_company, email),
    CONSTRAINT fk_customer_company FOREIGN KEY (id_company) REFERENCES company (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
