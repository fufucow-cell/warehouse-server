-- ============================================
-- Warehouse Server Database Schema
-- Description: Complete database schema for warehouse management system
-- ============================================

-- Enable uuid extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- Note: log.type 使用 VARCHAR 而不是 enum 类型
-- ============================================

-- ============================================
-- Table: cabinet
-- Description: 橱柜表，存储橱柜信息，关联到 household_server.room
-- ============================================
CREATE TABLE IF NOT EXISTS cabinet (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    room_id INTEGER,  -- FK to household_server.room.id (跨服务，无法建立外键约束，可选)
    home_id INTEGER NOT NULL,  -- FK to household_server.home.id (跨服务，无法建立外键约束)
    name VARCHAR(255) NOT NULL,
    description VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for cabinet table
CREATE INDEX IF NOT EXISTS idx_cabinet_room_id ON cabinet(room_id);
CREATE INDEX IF NOT EXISTS idx_cabinet_home_id ON cabinet(home_id);
CREATE INDEX IF NOT EXISTS idx_cabinet_name ON cabinet(name);

-- ============================================
-- Add comments for cabinet table
-- ============================================
COMMENT ON TABLE cabinet IS '橱柜表，存储橱柜信息，关联到 household_server.room';
COMMENT ON COLUMN cabinet.id IS '橱柜 ID（UUID）';
COMMENT ON COLUMN cabinet.room_id IS '房间 ID（关联到 household_server.room.id，跨服务无法建立外键约束，可选）';
COMMENT ON COLUMN cabinet.home_id IS '家庭 ID（关联到 household_server.home.id，跨服务无法建立外键约束）';
COMMENT ON COLUMN cabinet.name IS '橱柜名称';
COMMENT ON COLUMN cabinet.description IS '橱柜描述';

-- ============================================
-- Table: category
-- Description: 分类表，支持最多三层分类层级，关联到 household_server.home
-- ============================================
CREATE TABLE IF NOT EXISTS category (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    home_id INTEGER NOT NULL,  -- FK to household_server.home.id (跨服务，无法建立外键约束)
    name VARCHAR(255) NOT NULL,
    parent_id UUID,  -- FK to category.id (自引用，用于层级关系)
    level SMALLINT NOT NULL CHECK (level IN (1, 2, 3)),  -- 分类层级：1=第一层，2=第二层，3=第三层
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES category(id) ON DELETE CASCADE
);

-- Create indexes for category table
CREATE INDEX IF NOT EXISTS idx_category_home_id ON category(home_id);
CREATE INDEX IF NOT EXISTS idx_category_parent_id ON category(parent_id);
CREATE INDEX IF NOT EXISTS idx_category_level ON category(level);

-- ============================================
-- Add comments for category table
-- ============================================
COMMENT ON TABLE category IS '分类表，支持最多三层分类层级，关联到 household_server.home';
COMMENT ON COLUMN category.id IS '分类 ID（UUID）';
COMMENT ON COLUMN category.home_id IS '家庭 ID（关联到 household_server.home.id，跨服务无法建立外键约束）';
COMMENT ON COLUMN category.name IS '分类名称';
COMMENT ON COLUMN category.parent_id IS '父分类 ID（用于层级关系，第一层为 NULL）';
COMMENT ON COLUMN category.level IS '分类层级：1=第一层，2=第二层，3=第三层';

-- ============================================
-- Table: item
-- Description: 物品表，存储物品信息，关联到 cabinet
-- ============================================
CREATE TABLE IF NOT EXISTS item (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cabinet_id UUID REFERENCES cabinet(id) ON DELETE CASCADE,  -- 可选，物品可能不属于任何橱柜
    room_id INTEGER,  -- FK to household_server.room.id (跨服务，无法建立外键约束，可选)
    home_id INTEGER NOT NULL,  -- FK to household_server.home.id (跨服务，无法建立外键约束)
    name VARCHAR(255) NOT NULL,
    description TEXT,
    quantity INTEGER NOT NULL DEFAULT 0,
    min_stock_alert INTEGER NOT NULL DEFAULT 0,  -- 最低库存警报阈值
    photo VARCHAR(500),  -- 照片 URL
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for item table
CREATE INDEX IF NOT EXISTS idx_item_cabinet_id ON item(cabinet_id);
CREATE INDEX IF NOT EXISTS idx_item_room_id ON item(room_id);
CREATE INDEX IF NOT EXISTS idx_item_home_id ON item(home_id);
CREATE INDEX IF NOT EXISTS idx_item_name ON item(name);
CREATE INDEX IF NOT EXISTS idx_item_quantity ON item(quantity);

-- ============================================
-- Add comments for item table
-- ============================================
COMMENT ON TABLE item IS '物品表，存储物品信息，关联到 cabinet';
COMMENT ON COLUMN item.id IS '物品 ID（UUID）';
COMMENT ON COLUMN item.cabinet_id IS '橱柜 ID（关联到 cabinet.id，可选，物品可能不属于任何橱柜）';
COMMENT ON COLUMN item.room_id IS '房间 ID（关联到 household_server.room.id，跨服务无法建立外键约束，可选）';
COMMENT ON COLUMN item.home_id IS '家庭 ID（关联到 household_server.home.id，跨服务无法建立外键约束）';
COMMENT ON COLUMN item.name IS '物品名称';
COMMENT ON COLUMN item.description IS '物品描述';
COMMENT ON COLUMN item.quantity IS '物品数量';
COMMENT ON COLUMN item.min_stock_alert IS '最低库存警报阈值';
COMMENT ON COLUMN item.photo IS '照片 URL';

-- ============================================
-- Table: item_category
-- Description: 物品与分类关联表（多对多关系）
-- ============================================
CREATE TABLE IF NOT EXISTS item_category (
    item_id UUID NOT NULL REFERENCES item(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES category(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (item_id, category_id)
);

-- Create indexes for item_category table
CREATE INDEX IF NOT EXISTS idx_item_category_item_id ON item_category(item_id);
CREATE INDEX IF NOT EXISTS idx_item_category_category_id ON item_category(category_id);

-- ============================================
-- Add comments for item_category table
-- ============================================
COMMENT ON TABLE item_category IS '物品与分类关联表（多对多关系）';
COMMENT ON COLUMN item_category.item_id IS '物品 ID（关联到 item.id）';
COMMENT ON COLUMN item_category.category_id IS '分类 ID（关联到 category.id）';

-- ============================================
-- Table: item_log
-- Description: 物品异动日志表，记录物品的数量增减和其他字段变更
-- ============================================
CREATE TABLE IF NOT EXISTS item_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    item_id UUID NOT NULL REFERENCES item(id) ON DELETE CASCADE,
    type SMALLINT NOT NULL CHECK (type IN (1, 2)),  -- 1=一般信息异动记录，2=告警类型（数量低于条件）
    log_message TEXT NOT NULL,  -- 异动日志内容（数量增减、其他字段变更等）
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for item_log table
CREATE INDEX IF NOT EXISTS idx_item_log_item_id ON item_log(item_id);
CREATE INDEX IF NOT EXISTS idx_item_log_type ON item_log(type);
CREATE INDEX IF NOT EXISTS idx_item_log_created_at ON item_log(created_at);

-- ============================================
-- Add comments for item_log table
-- ============================================
COMMENT ON TABLE item_log IS '物品异动日志表，记录物品的数量增减和其他字段变更';
COMMENT ON COLUMN item_log.id IS '日志 ID（UUID）';
COMMENT ON COLUMN item_log.item_id IS '物品 ID（关联到 item.id）';
COMMENT ON COLUMN item_log.type IS '日志类型：1=一般信息异动记录，2=告警类型（数量低于条件）';
COMMENT ON COLUMN item_log.log_message IS '异动日志内容（数量增减、其他字段变更等）';

-- ============================================
-- Table: log
-- Description: 操作日志表，记录用户对 cabinet、item 等的操作
-- ============================================
CREATE TABLE IF NOT EXISTS log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    home_id INTEGER NOT NULL,  -- FK to household_server.home.id (跨服务，无法建立外键约束)
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    state SMALLINT NOT NULL,  -- 操作状态：0=新增（create），1=更新（modify），2=删除（delete），后续可能扩充
    item_type SMALLINT NOT NULL,  -- 物品类型：0=cabinet（橱柜），1=item（物品），后续可能扩充
           operate_type SMALLINT[],  -- 操作类型数组：0=name（名称），1=description（描述），2=move（移动），3=quantity（数量），4=photo（照片），5=min_stock_alert（最低库存警报阈值）。仅在 state=1（modify）时使用，可包含多个操作类型，后续可能扩充
    user_name VARCHAR(255) NOT NULL,  -- 用户名
    type SMALLINT NOT NULL DEFAULT 0  -- 日志类型：0=一般（normal），1=警告（warning），后续可能扩充
);

-- Create indexes for log table
CREATE INDEX IF NOT EXISTS idx_log_home_id ON log(home_id);
CREATE INDEX IF NOT EXISTS idx_log_created_at ON log(created_at);
CREATE INDEX IF NOT EXISTS idx_log_state ON log(state);
CREATE INDEX IF NOT EXISTS idx_log_item_type ON log(item_type);
-- 注意：operate_type 是数组类型，如果需要数组查询，可以使用 GIN 索引
-- CREATE INDEX IF NOT EXISTS idx_log_operate_type ON log USING GIN (operate_type);
CREATE INDEX IF NOT EXISTS idx_log_operate_type ON log(operate_type);
CREATE INDEX IF NOT EXISTS idx_log_type ON log(type);
CREATE INDEX IF NOT EXISTS idx_log_user_name ON log(user_name);

-- ============================================
-- Add comments for log table
-- ============================================
COMMENT ON TABLE log IS '操作日志表，记录用户对 cabinet、item 等的操作';
COMMENT ON COLUMN log.id IS '日志 ID（UUID）';
COMMENT ON COLUMN log.home_id IS '家庭 ID（关联到 household_server.home.id，跨服务无法建立外键约束）';
COMMENT ON COLUMN log.created_at IS '创建时间';
COMMENT ON COLUMN log.state IS '操作状态：0=新增（create），1=更新（modify），2=删除（delete），后续可能扩充';
COMMENT ON COLUMN log.item_type IS '物品类型：0=cabinet（橱柜），1=item（物品），后续可能扩充';
COMMENT ON COLUMN log.operate_type IS '操作类型数组：0=name（名称），1=description（描述），2=move（移动），3=quantity（数量），4=photo（照片）。仅在 state=1（modify）时使用，可包含多个操作类型，后续可能扩充';
COMMENT ON COLUMN log.user_name IS '用户名';
COMMENT ON COLUMN log.type IS '日志类型：0=一般（normal），1=警告（warning），后续可能扩充';
