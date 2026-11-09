-- 資料助秘工具之進銷存系統 資料庫結構（MariaDB 10.5+）
CREATE TABLE IF NOT EXISTS meta (
  k VARCHAR(40) PRIMARY KEY,
  v VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS company (
  id TINYINT PRIMARY KEY DEFAULT 1,
  name VARCHAR(60) NOT NULL DEFAULT '',
  tax_id VARCHAR(10) DEFAULT '',
  tel VARCHAR(20) DEFAULT '',
  address VARCHAR(100) DEFAULT '',
  prod_len TINYINT DEFAULT 20,
  color_len TINYINT DEFAULT 3,
  size_len TINYINT DEFAULT 3,
  size_group_a VARCHAR(120) DEFAULT '',
  size_group_b VARCHAR(120) DEFAULT '',
  size_group_c VARCHAR(120) DEFAULT '',
  size_group_d VARCHAR(120) DEFAULT '',
  roc_date TINYINT DEFAULT 1
);

CREATE TABLE IF NOT EXISTS users (
  user_no VARCHAR(12) PRIMARY KEY,
  name VARCHAR(30) NOT NULL DEFAULT '',
  dept VARCHAR(30) DEFAULT '',
  pw_hash VARCHAR(200) NOT NULL DEFAULT '',
  is_admin TINYINT NOT NULL DEFAULT 0,
  active TINYINT NOT NULL DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_perms (
  user_no VARCHAR(12) NOT NULL,
  func_id VARCHAR(10) NOT NULL,
  PRIMARY KEY (user_no, func_id)
);

CREATE TABLE IF NOT EXISTS codes (
  kind VARCHAR(10) NOT NULL,      -- color/size/class/brand/series/reason/unit/subject
  code VARCHAR(10) NOT NULL,
  name VARCHAR(40) NOT NULL DEFAULT '',
  memo VARCHAR(60) DEFAULT '',
  PRIMARY KEY (kind, code)
);

CREATE TABLE IF NOT EXISTS warehouses (
  wh_no VARCHAR(4) PRIMARY KEY,
  name VARCHAR(30) NOT NULL DEFAULT '',
  contact VARCHAR(20) DEFAULT '',
  tel VARCHAR(20) DEFAULT '',
  area VARCHAR(20) DEFAULT '',
  address VARCHAR(100) DEFAULT '',
  memo VARCHAR(60) DEFAULT '',
  active TINYINT NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS shops (
  sh_no VARCHAR(10) PRIMARY KEY,
  short_name VARCHAR(30) NOT NULL DEFAULT '',
  full_name VARCHAR(60) DEFAULT '',
  contact VARCHAR(20) DEFAULT '',
  contact2 VARCHAR(20) DEFAULT '',
  tel1 VARCHAR(20) DEFAULT '',
  tel2 VARCHAR(20) DEFAULT '',
  fax VARCHAR(20) DEFAULT '',
  email VARCHAR(60) DEFAULT '',
  sh_class VARCHAR(10) DEFAULT '',
  price_level TINYINT NOT NULL DEFAULT 1,      -- 1/2/3 對應產品售價一/二/三
  settle_mode CHAR(1) NOT NULL DEFAULT 'W',    -- W 批發(依出退貨) / C 專櫃(依銷售扣抽成)
  discount DECIMAL(6,2) NOT NULL DEFAULT 100,  -- 出貨折數 %
  commission DECIMAL(6,2) NOT NULL DEFAULT 0,  -- 專櫃抽成 %
  tax_id VARCHAR(10) DEFAULT '',
  tax_type VARCHAR(4) DEFAULT '',
  salesman VARCHAR(10) DEFAULT '',
  credit_limit DECIMAL(14,2) DEFAULT 0,
  address1 VARCHAR(100) DEFAULT '',
  address2 VARCHAR(100) DEFAULT '',
  address3 VARCHAR(100) DEFAULT '',
  memo VARCHAR(100) DEFAULT '',
  active TINYINT NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS vendors (
  ma_no VARCHAR(10) PRIMARY KEY,
  short_name VARCHAR(30) NOT NULL DEFAULT '',
  full_name VARCHAR(60) DEFAULT '',
  contact VARCHAR(20) DEFAULT '',
  contact2 VARCHAR(20) DEFAULT '',
  tel1 VARCHAR(20) DEFAULT '',
  tel2 VARCHAR(20) DEFAULT '',
  fax VARCHAR(20) DEFAULT '',
  email VARCHAR(60) DEFAULT '',
  tax_id VARCHAR(10) DEFAULT '',
  tax_type VARCHAR(4) DEFAULT '',
  made_in VARCHAR(20) DEFAULT '',
  address1 VARCHAR(100) DEFAULT '',
  address2 VARCHAR(100) DEFAULT '',
  memo VARCHAR(100) DEFAULT '',
  active TINYINT NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS employees (
  per_no VARCHAR(10) PRIMARY KEY,
  name VARCHAR(20) NOT NULL DEFAULT '',
  en_name VARCHAR(20) DEFAULT '',
  id_no VARCHAR(14) DEFAULT '',
  sex VARCHAR(2) DEFAULT '',
  tel1 VARCHAR(20) DEFAULT '',
  tel2 VARCHAR(20) DEFAULT '',
  mobile VARCHAR(20) DEFAULT '',
  email VARCHAR(60) DEFAULT '',
  sh_no VARCHAR(10) DEFAULT '',
  dept VARCHAR(20) DEFAULT '',
  job VARCHAR(20) DEFAULT '',
  birth DATE NULL,
  hire_date DATE NULL,
  leave_date DATE NULL,
  bank VARCHAR(30) DEFAULT '',
  bank_acct VARCHAR(20) DEFAULT '',
  address VARCHAR(100) DEFAULT '',
  memo VARCHAR(100) DEFAULT '',
  active TINYINT NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS products (
  prod_no VARCHAR(20) NOT NULL,
  color VARCHAR(3) NOT NULL DEFAULT '',
  size VARCHAR(3) NOT NULL DEFAULT '',
  name VARCHAR(60) NOT NULL DEFAULT '',
  spec VARCHAR(60) DEFAULT '',
  class VARCHAR(10) DEFAULT '',
  brand VARCHAR(10) DEFAULT '',
  series VARCHAR(10) DEFAULT '',
  unit VARCHAR(10) DEFAULT '',
  price1 DECIMAL(12,2) NOT NULL DEFAULT 0,
  price2 DECIMAL(12,2) NOT NULL DEFAULT 0,
  price3 DECIMAL(12,2) NOT NULL DEFAULT 0,
  cost DECIMAL(12,2) NOT NULL DEFAULT 0,
  barcode VARCHAR(30) DEFAULT '',
  source_no VARCHAR(20) DEFAULT '',
  image_path VARCHAR(200) DEFAULT '',
  safe_qty INT NOT NULL DEFAULT 0,
  active TINYINT NOT NULL DEFAULT 1,
  updated_by VARCHAR(12) DEFAULT '',
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (prod_no, color, size),
  KEY idx_prod_barcode (barcode),
  KEY idx_prod_brand (brand)
);

CREATE TABLE IF NOT EXISTS docs (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  doc_type VARCHAR(4) NOT NULL,
  doc_no VARCHAR(20) NOT NULL,
  doc_date DATE NOT NULL,
  wh_no VARCHAR(4) DEFAULT '',
  wh_no2 VARCHAR(4) DEFAULT '',
  sh_no VARCHAR(10) DEFAULT '',
  sh_no2 VARCHAR(10) DEFAULT '',
  ma_no VARCHAR(10) DEFAULT '',
  per_no VARCHAR(10) DEFAULT '',
  reason VARCHAR(10) DEFAULT '',
  ref_no VARCHAR(20) DEFAULT '',
  bill_no VARCHAR(20) DEFAULT '',
  discount DECIMAL(6,2) NOT NULL DEFAULT 100,
  total_qty INT NOT NULL DEFAULT 0,
  total_amt DECIMAL(14,2) NOT NULL DEFAULT 0,
  total_cost DECIMAL(14,2) NOT NULL DEFAULT 0,
  pay_cash DECIMAL(14,2) NOT NULL DEFAULT 0,
  pay_card DECIMAL(14,2) NOT NULL DEFAULT 0,
  pay_voucher DECIMAL(14,2) NOT NULL DEFAULT 0,
  memo VARCHAR(120) DEFAULT '',
  created_by VARCHAR(12) DEFAULT '',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_by VARCHAR(12) DEFAULT '',
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_doc (doc_type, doc_no),
  KEY idx_doc_date (doc_type, doc_date),
  KEY idx_doc_shop (sh_no, doc_date),
  KEY idx_doc_ref (ref_no)
);

CREATE TABLE IF NOT EXISTS doc_lines (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  doc_id BIGINT NOT NULL,
  seq INT NOT NULL DEFAULT 0,
  prod_no VARCHAR(20) NOT NULL,
  color VARCHAR(3) NOT NULL DEFAULT '',
  size VARCHAR(3) NOT NULL DEFAULT '',
  qty INT NOT NULL DEFAULT 0,
  price DECIMAL(12,2) NOT NULL DEFAULT 0,
  cost DECIMAL(12,2) NOT NULL DEFAULT 0,
  amount DECIMAL(14,2) NOT NULL DEFAULT 0,
  memo VARCHAR(60) DEFAULT '',
  KEY idx_line_doc (doc_id),
  KEY idx_line_prod (prod_no, color, size),
  CONSTRAINT fk_line_doc FOREIGN KEY (doc_id) REFERENCES docs(id) ON DELETE CASCADE
);

-- 庫存異動帳（每張單據展開成的加減量）；庫存表＝異動帳的加總
CREATE TABLE IF NOT EXISTS stock_moves (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  doc_id BIGINT NOT NULL,
  doc_type VARCHAR(4) NOT NULL,
  doc_date DATE NOT NULL,
  loc_type CHAR(1) NOT NULL,          -- W 倉庫 / S 店家
  loc_no VARCHAR(10) NOT NULL,
  prod_no VARCHAR(20) NOT NULL,
  color VARCHAR(3) NOT NULL DEFAULT '',
  size VARCHAR(3) NOT NULL DEFAULT '',
  qty INT NOT NULL,
  KEY idx_mv_doc (doc_id),
  KEY idx_mv_loc (loc_type, loc_no, doc_date),
  KEY idx_mv_prod (prod_no, color, size),
  CONSTRAINT fk_mv_doc FOREIGN KEY (doc_id) REFERENCES docs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS stock (
  loc_type CHAR(1) NOT NULL,
  loc_no VARCHAR(10) NOT NULL,
  prod_no VARCHAR(20) NOT NULL,
  color VARCHAR(3) NOT NULL DEFAULT '',
  size VARCHAR(3) NOT NULL DEFAULT '',
  qty INT NOT NULL DEFAULT 0,
  PRIMARY KEY (loc_type, loc_no, prod_no, color, size)
);

-- 應收帳款
CREATE TABLE IF NOT EXISTS ar_closings (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  sh_no VARCHAR(10) NOT NULL,
  period CHAR(6) NOT NULL,              -- YYYYMM
  ship_amt DECIMAL(14,2) NOT NULL DEFAULT 0,
  return_amt DECIMAL(14,2) NOT NULL DEFAULT 0,
  sales_amt DECIMAL(14,2) NOT NULL DEFAULT 0,
  commission_amt DECIMAL(14,2) NOT NULL DEFAULT 0,
  fee_amt DECIMAL(14,2) NOT NULL DEFAULT 0,
  amount DECIMAL(14,2) NOT NULL DEFAULT 0,  -- 本期應收
  closed_by VARCHAR(12) DEFAULT '',
  closed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_close (sh_no, period)
);

CREATE TABLE IF NOT EXISTS ar_payments (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  sh_no VARCHAR(10) NOT NULL,
  pay_date DATE NOT NULL,
  amount DECIMAL(14,2) NOT NULL DEFAULT 0,
  allowance DECIMAL(14,2) NOT NULL DEFAULT 0,   -- 折讓
  method VARCHAR(10) DEFAULT '現金',
  bill_no VARCHAR(20) DEFAULT '',
  memo VARCHAR(60) DEFAULT '',
  created_by VARCHAR(12) DEFAULT '',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_pay_shop (sh_no, pay_date)
);

CREATE TABLE IF NOT EXISTS ar_fees (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  sh_no VARCHAR(10) NOT NULL,
  fee_date DATE NOT NULL,
  subject VARCHAR(10) DEFAULT '',
  amount DECIMAL(14,2) NOT NULL DEFAULT 0,      -- 正數＝向店家扣款
  memo VARCHAR(60) DEFAULT '',
  created_by VARCHAR(12) DEFAULT '',
  KEY idx_fee_shop (sh_no, fee_date)
);

CREATE TABLE IF NOT EXISTS audit_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  at DATETIME DEFAULT CURRENT_TIMESTAMP,
  user_no VARCHAR(12) DEFAULT '',
  action VARCHAR(20) NOT NULL,
  target VARCHAR(60) DEFAULT '',
  detail VARCHAR(255) DEFAULT ''
);

-- 特價品（舊系統 15 依貨號、16 依客戶）：sh_no 空白＝全部店家；color/size 空白＝該貨號全部規格
CREATE TABLE IF NOT EXISTS specials (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  sh_no VARCHAR(10) NOT NULL DEFAULT '',
  prod_no VARCHAR(20) NOT NULL,
  color VARCHAR(3) NOT NULL DEFAULT '',
  size VARCHAR(3) NOT NULL DEFAULT '',
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  special_price DECIMAL(12,2) NULL,      -- 特價（優先）
  discount DECIMAL(6,2) NULL,            -- 或折數 %（例：80＝打八折）
  memo VARCHAR(60) DEFAULT '',
  active TINYINT NOT NULL DEFAULT 1,
  created_by VARCHAR(12) DEFAULT '',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_sp_prod (prod_no, start_date, end_date),
  KEY idx_sp_shop (sh_no)
);
