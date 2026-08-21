-- ponytail: generate_series for bulk rows, no fixture files needed
SELECT setseed(0.42); -- reproducible row distribution across container rebuilds

CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    amount NUMERIC NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now()
);

INSERT INTO customers (name)
SELECT 'customer_' || i FROM generate_series(1, 5000) i;

INSERT INTO orders (customer_id, amount, created_at)
SELECT (random() * 4999 + 1)::int, (random() * 500)::numeric(10,2),
       now() - (random() * interval '365 days')
FROM generate_series(1, 200000);

ANALYZE customers;
ANALYZE orders;
