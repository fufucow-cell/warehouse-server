-- ============================================
-- Warehouse Server Database Schema (MySQL)
-- ============================================

-- ============================================

CREATE TABLE IF NOT EXISTS category (
    id CHAR(36) PRIMARY KEY,
    household_id CHAR(36) NOT NULL,
    name VARCHAR(100) NOT NULL,
    parent_id CHAR(36),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_category_parent_id 
        FOREIGN KEY (parent_id) 
        REFERENCES category(id) 
        ON DELETE CASCADE
);
CREATE INDEX ix_category_parent_id ON category(parent_id);

-- ============================================

CREATE TABLE IF NOT EXISTS cabinet (
    id CHAR(36) PRIMARY KEY,
    household_id CHAR(36) NOT NULL,
    room_id CHAR(36),
    name VARCHAR(100) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE INDEX ix_cabinet_household_id ON cabinet(household_id);
CREATE INDEX ix_cabinet_room_id ON cabinet(room_id);


-- ============================================

CREATE TABLE IF NOT EXISTS item (
    id CHAR(36) PRIMARY KEY,
    household_id CHAR(36) NOT NULL,
    category_id CHAR(36),
    name VARCHAR(100) NOT NULL,
    description VARCHAR(200),
    min_stock_alert INTEGER NOT NULL DEFAULT 0,
    photo VARCHAR(500),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_item_category_id 
        FOREIGN KEY (category_id) 
        REFERENCES category(id) 
        ON DELETE SET NULL
);

CREATE INDEX ix_item_household_id ON item(household_id);
CREATE INDEX ix_item_category_id ON item(category_id);

-- ============================================

CREATE TABLE IF NOT EXISTS item_cabinet_quantity (
    id CHAR(36) PRIMARY KEY,
    household_id CHAR(36) NOT NULL,
    item_id CHAR(36) NOT NULL,
    cabinet_id CHAR(36) NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_item_cabinet_quantity_item_id 
        FOREIGN KEY (item_id) 
        REFERENCES item(id) 
        ON DELETE CASCADE,
    
    CONSTRAINT fk_item_cabinet_quantity_cabinet_id 
        FOREIGN KEY (cabinet_id) 
        REFERENCES cabinet(id) 
        ON DELETE SET NULL,
    
    CONSTRAINT uk_item_cabinet_quantity_item_cabinet 
        UNIQUE (item_id, cabinet_id)
);

CREATE INDEX ix_item_cabinet_quantity_item_id ON item_cabinet_quantity(item_id);
CREATE INDEX ix_item_cabinet_quantity_cabinet_id ON item_cabinet_quantity(cabinet_id);

-- ============================================

CREATE TABLE IF NOT EXISTS record (
    id CHAR(36) PRIMARY KEY,
    item_id CHAR(36) NULL,
    household_id CHAR(36) NOT NULL,
    user_name VARCHAR(100) NOT NULL,
    operate_type SMALLINT NOT NULL,
    entity_type SMALLINT NOT NULL,
    item_name_old VARCHAR(100),
    item_name_new VARCHAR(100),
    item_description_old VARCHAR(200),
    item_description_new VARCHAR(200),
    item_photo_old VARCHAR(500),
    item_photo_new VARCHAR(500),
    category_name_old VARCHAR(100),
    category_name_new VARCHAR(100),
    room_name_old VARCHAR(100),
    room_name_new VARCHAR(100),
    cabinet_name_old VARCHAR(100),
    cabinet_name_new VARCHAR(100),
    quantity_count_old INTEGER,
    quantity_count_new INTEGER,
    min_stock_count_old INTEGER,
    min_stock_count_new INTEGER,
    description VARCHAR(200),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_record_household_id ON record(household_id);
CREATE INDEX ix_record_created_at ON record(created_at);
CREATE INDEX ix_record_operate_type ON record(operate_type);
CREATE INDEX ix_record_entity_type ON record(entity_type);
