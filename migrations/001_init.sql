-- ============================================
-- AI炒股系统 - 数据库初始化迁移
-- ============================================

-- 启用TimescaleDB扩展
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ========== 股票基础信息 ==========
CREATE TABLE stock_basic (
    symbol VARCHAR(20) PRIMARY KEY,          -- 000001.SZ
    ts_code VARCHAR(20) NOT NULL,            -- 000001.SZ (Tushare格式)
    name VARCHAR(50) NOT NULL,               -- 平安银行
    exchange VARCHAR(10) NOT NULL,           -- SZSE / SSE
    industry VARCHAR(50),                    -- 银行
    sector VARCHAR(50),                      -- 金融
    list_date DATE,                          -- 上市日期
    delist_date DATE,                        -- 退市日期(NULL=正常)
    is_st BOOLEAN DEFAULT FALSE,             -- 是否ST
    board VARCHAR(20) DEFAULT 'main',        -- main/gem/star (主板/创业板/科创板)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========== 交易日历 ==========
CREATE TABLE trade_calendar (
    trade_date DATE PRIMARY KEY,
    is_open BOOLEAN NOT NULL DEFAULT TRUE,
    pretrade_date DATE
);

-- ========== K线数据 (TimescaleDB 超表) ==========

-- 日线
CREATE TABLE kline_daily (
    symbol VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    adj_factor DOUBLE PRECISION DEFAULT 1.0,
    -- 技术指标 (预计算)
    ma5 DOUBLE PRECISION,
    ma10 DOUBLE PRECISION,
    ma20 DOUBLE PRECISION,
    ma60 DOUBLE PRECISION,
    macd_dif DOUBLE PRECISION,
    macd_dea DOUBLE PRECISION,
    macd_bar DOUBLE PRECISION,
    rsi14 DOUBLE PRECISION,
    vol_ma5 DOUBLE PRECISION,
    vol_ma20 DOUBLE PRECISION,
    PRIMARY KEY (symbol, trade_date)
);
SELECT create_hypertable('kline_daily', 'trade_date', chunk_time_interval => INTERVAL '30 days');
CREATE INDEX idx_kline_daily_symbol ON kline_daily (symbol, trade_date DESC);

-- 60分钟线
CREATE TABLE kline_60min (
    symbol VARCHAR(20) NOT NULL,
    trade_time TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (symbol, trade_time)
);
SELECT create_hypertable('kline_60min', 'trade_time', chunk_time_interval => INTERVAL '7 days');

-- 5分钟线
CREATE TABLE kline_5min (
    symbol VARCHAR(20) NOT NULL,
    trade_time TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (symbol, trade_time)
);
SELECT create_hypertable('kline_5min', 'trade_time', chunk_time_interval => INTERVAL '1 day');

-- ========== 财务数据 ==========
CREATE TABLE fundamental_data (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    report_date DATE NOT NULL,               -- 报告期
    total_revenue DOUBLE PRECISION,
    net_profit DOUBLE PRECISION,
    total_assets DOUBLE PRECISION,
    total_liabilities DOUBLE PRECISION,
    shareholder_equity DOUBLE PRECISION,
    eps DOUBLE PRECISION,                    -- 每股收益
    bvps DOUBLE PRECISION,                   -- 每股净资产
    roe DOUBLE PRECISION,                    -- ROE
    pe_ttm DOUBLE PRECISION,
    pb DOUBLE PRECISION,
    market_cap DOUBLE PRECISION,
    UNIQUE (symbol, report_date)
);
CREATE INDEX idx_fundamental_symbol ON fundamental_data (symbol, report_date DESC);

-- ========== 账户配置 ==========
CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    broker VARCHAR(20) NOT NULL DEFAULT 'htsc',  -- htsc(华泰), guoxin(国信), etc.
    account_id VARCHAR(50) UNIQUE NOT NULL,
    account_name VARCHAR(50),
    initial_capital DOUBLE PRECISION NOT NULL,
    current_capital DOUBLE PRECISION,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========== 持仓 ==========
CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) REFERENCES accounts(account_id),
    symbol VARCHAR(20) NOT NULL,
    total_qty INTEGER NOT NULL DEFAULT 0,
    available_sell INTEGER NOT NULL DEFAULT 0,   -- 可卖数量
    locked_qty INTEGER NOT NULL DEFAULT 0,        -- T+1锁定(当日买入)
    avg_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
    current_price DOUBLE PRECISION,
    market_value DOUBLE PRECISION,
    unrealized_pnl DOUBLE PRECISION DEFAULT 0,
    realized_pnl DOUBLE PRECISION DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (account_id, symbol)
);

-- ========== 订单 ==========
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) UNIQUE NOT NULL,
    signal_id VARCHAR(50),
    account_id VARCHAR(50) REFERENCES accounts(account_id),
    symbol VARCHAR(20) NOT NULL,
    action VARCHAR(10) NOT NULL,                 -- BUY / SELL
    order_type VARCHAR(10) NOT NULL DEFAULT 'LIMIT',
    price DOUBLE PRECISION NOT NULL,
    volume INTEGER NOT NULL,
    filled_volume INTEGER DEFAULT 0,
    avg_fill_price DOUBLE PRECISION,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    -- PENDING -> ACCEPTED -> PARTIALLY_FILLED -> FILLED
    -- PENDING -> REJECTED
    -- ACCEPTED -> CANCELLED
    strategy_id VARCHAR(50),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_orders_symbol ON orders (symbol, created_at DESC);
CREATE INDEX idx_orders_status ON orders (status, created_at);

-- ========== 成交记录 ==========
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    trade_id VARCHAR(50) UNIQUE NOT NULL,
    order_id VARCHAR(50) REFERENCES orders(order_id),
    account_id VARCHAR(50) REFERENCES accounts(account_id),
    symbol VARCHAR(20) NOT NULL,
    action VARCHAR(10) NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    volume INTEGER NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    commission DOUBLE PRECISION DEFAULT 0,
    stamp_tax DOUBLE PRECISION DEFAULT 0,        -- 印花税
    trade_time TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
SELECT create_hypertable('trades', 'trade_time', chunk_time_interval => INTERVAL '30 days');

-- ========== 策略定义 ==========
CREATE TABLE strategies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    description TEXT,
    category VARCHAR(30),                        -- trend/mean_reversion/momentum/arbitrage
    status VARCHAR(20) DEFAULT 'draft',          -- draft/backtesting/live/paused/stopped
    params JSONB DEFAULT '{}',                   -- 策略参数
    indicators JSONB DEFAULT '[]',               -- 所需指标列表
    max_position_pct DOUBLE PRECISION DEFAULT 0.1,
    stop_loss_pct DOUBLE PRECISION DEFAULT 5.0,
    take_profit_pct DOUBLE PRECISION DEFAULT 10.0,
    requires_ai BOOLEAN DEFAULT TRUE,
    requires_confirmation BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========== 信号记录 ==========
CREATE TABLE signals (
    id SERIAL PRIMARY KEY,
    signal_id VARCHAR(50) UNIQUE NOT NULL,
    strategy_id VARCHAR(50) REFERENCES strategies(name),
    symbol VARCHAR(20) NOT NULL,
    action VARCHAR(10) NOT NULL,                 -- BUY / SELL
    strength DOUBLE PRECISION,                   -- 信号强度 0-1
    price DOUBLE PRECISION,
    volume INTEGER,
    position_pct DOUBLE PRECISION,
    reason TEXT,
    stop_loss DOUBLE PRECISION,
    take_profit DOUBLE PRECISION,
    ai_enhanced BOOLEAN DEFAULT FALSE,
    ai_confidence DOUBLE PRECISION,
    ai_notes TEXT,
    risk_approved BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'PENDING',        -- PENDING/APPROVED/REJECTED/EXECUTED/EXPIRED
    approved_by VARCHAR(20) DEFAULT 'system',    -- system / manual / user_name
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    executed_at TIMESTAMPTZ
);
SELECT create_hypertable('signals', 'triggered_at', chunk_time_interval => INTERVAL '7 days');

-- ========== 风控事件 ==========
CREATE TABLE risk_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(30) NOT NULL,             -- CIRCUIT_BREAKER/STOP_LOSS/DAILY_LIMIT/VIOLATION
    level VARCHAR(10) NOT NULL DEFAULT 'INFO',   -- INFO/WARNING/CRITICAL
    symbol VARCHAR(20),
    strategy_id VARCHAR(50),
    message TEXT NOT NULL,
    action_taken TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
SELECT create_hypertable('risk_events', 'created_at', chunk_time_interval => INTERVAL '30 days');

-- ========== AI调用日志 ==========
CREATE TABLE ai_prompt_log (
    id SERIAL PRIMARY KEY,
    module VARCHAR(30) NOT NULL,                 -- sentiment/pattern/news/risk
    model VARCHAR(30) NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    cost DOUBLE PRECISION NOT NULL,
    latency_ms INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_msg TEXT,
    request_data JSONB,
    response_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
SELECT create_hypertable('ai_prompt_log', 'created_at', chunk_time_interval => INTERVAL '1 day');

-- ========== 用户 ==========
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'trader',           -- admin/trader/viewer
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ========== 权益快照 ==========
CREATE TABLE equity_snapshots (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) REFERENCES accounts(account_id),
    snapshot_time TIMESTAMPTZ NOT NULL,
    total_equity DOUBLE PRECISION NOT NULL,
    available_cash DOUBLE PRECISION NOT NULL,
    market_value DOUBLE PRECISION NOT NULL,
    daily_pnl DOUBLE PRECISION DEFAULT 0,
    cumulative_pnl DOUBLE PRECISION DEFAULT 0,
    daily_return DOUBLE PRECISION DEFAULT 0,
    UNIQUE (account_id, snapshot_time)
);
SELECT create_hypertable('equity_snapshots', 'snapshot_time', chunk_time_interval => INTERVAL '30 days');

-- ========== 连续聚合视图 ==========

-- 周线聚合
CREATE MATERIALIZED VIEW kline_weekly
WITH (timescaledb.continuous) AS
SELECT
    symbol,
    time_bucket('1 week', trade_date) AS bucket,
    FIRST(open, trade_date) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    LAST(close, trade_date) AS close,
    SUM(volume) AS volume,
    SUM(amount) AS amount
FROM kline_daily
GROUP BY symbol, bucket;

-- 月线聚合
CREATE MATERIALIZED VIEW kline_monthly
WITH (timescaledb.continuous) AS
SELECT
    symbol,
    time_bucket('1 month', trade_date) AS bucket,
    FIRST(open, trade_date) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    LAST(close, trade_date) AS close,
    SUM(volume) AS volume,
    SUM(amount) AS amount
FROM kline_daily
GROUP BY symbol, bucket;

-- ========== 默认管理员用户 ==========
-- 密码: admin123 (需要在应用中用bcrypt哈希)
-- INSERT INTO users (username, password_hash, role) VALUES ('admin', '$2b$12$...', 'admin');
