CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 거래처
CREATE TABLE customers (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    type            VARCHAR(20) NOT NULL,       -- cafe / restaurant / bakery
    email           VARCHAR(200) UNIQUE,
    default_address TEXT,
    created_at      TIMESTAMP DEFAULT now()
);

-- 상품 마스터
CREATE TABLE products (
    id            SERIAL PRIMARY KEY,
    sku           VARCHAR(30) UNIQUE NOT NULL,
    name          VARCHAR(200) NOT NULL,        -- 정식 명칭
    category      VARCHAR(20) NOT NULL,         -- dairy / coffee / syrup / powder / fruit / bakery / supplies
    base_unit     VARCHAR(20) NOT NULL,         -- 재고·가격 기준 단위
    units_per_box INT,                          -- 박스당 개수 (NULL이면 박스 판매 없음)
    price         INT NOT NULL,                 -- base_unit 기준 단가
    stock         INT NOT NULL DEFAULT 0        -- base_unit 기준 재고
);
CREATE INDEX idx_products_name_trgm ON products USING gin (name gin_trgm_ops);

-- 상품 별칭 (customer_id가 NULL이면 공용, 있으면 해당 거래처 전용)
CREATE TABLE product_aliases (
    id          SERIAL PRIMARY KEY,
    product_id  INT NOT NULL REFERENCES products(id),
    customer_id INT REFERENCES customers(id),
    alias       VARCHAR(200) NOT NULL,
    source      VARCHAR(20) NOT NULL DEFAULT 'seed', -- seed / human_review
    created_at  TIMESTAMP DEFAULT now()
);
CREATE UNIQUE INDEX uq_product_aliases ON product_aliases (COALESCE(customer_id, 0), alias);
CREATE INDEX idx_product_aliases_trgm ON product_aliases USING gin (alias gin_trgm_ops);

-- 원본 발주·회신 문서
CREATE TABLE intake_documents (
    id              SERIAL PRIMARY KEY,
    message_id      VARCHAR(200) UNIQUE,
    in_reply_to     VARCHAR(200),
    sender_email    VARCHAR(200),
    subject         TEXT,
    body            TEXT,
    attachment_path TEXT,
    status          VARCHAR(20) DEFAULT 'received',
        -- received / processing / awaiting_reply / needs_review / done / skipped / rejected / failed
    thread_id       VARCHAR(100),
    received_at     TIMESTAMP DEFAULT now()
);

-- 주문
CREATE TABLE orders (
    id               SERIAL PRIMARY KEY,
    customer_id      INT REFERENCES customers(id),
    document_id      INT REFERENCES intake_documents(id),  -- 시드 이력 주문은 NULL
    idempotency_key  VARCHAR(100) UNIQUE NOT NULL,
    delivery_date    DATE NOT NULL,
    delivery_address TEXT NOT NULL,
    status           VARCHAR(20) DEFAULT 'confirmed',
    created_at       TIMESTAMP DEFAULT now()
);

CREATE TABLE order_items (
    id            SERIAL PRIMARY KEY,
    order_id      INT REFERENCES orders(id),
    product_id    INT REFERENCES products(id),
    quantity      INT NOT NULL,          -- 원문 단위 기준 수량
    unit          VARCHAR(20) NOT NULL,  -- 원문 단위: 박스 / base_unit
    base_quantity INT NOT NULL,          -- base_unit 환산 수량
    unit_price    INT NOT NULL,
    raw_text      TEXT,
    match_method  VARCHAR(20)            -- exact_alias / resolver / human / history
);

-- 우리가 보낸 메일 (재질의·주문 확인). 회신의 In-Reply-To/References로 원래 발주 스레드를 찾는 데 쓴다
CREATE TABLE outbound_messages (
    id          SERIAL PRIMARY KEY,
    message_id  VARCHAR(200) UNIQUE NOT NULL,
    document_id INT NOT NULL REFERENCES intake_documents(id),
    kind        VARCHAR(20) NOT NULL,      -- inquiry / confirmation
    subject     TEXT,
    body        TEXT,
    created_at  TIMESTAMP DEFAULT now()
);
