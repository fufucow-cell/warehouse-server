-- ============================================
-- Warehouse Server Database Schema
-- ============================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================

CREATE TABLE IF NOT EXISTS category (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    household_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    parent_id UUID,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_category_parent_id 
        FOREIGN KEY (parent_id) 
        REFERENCES category(id) 
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_category_parent_id ON category(parent_id);

-- ============================================

CREATE TABLE IF NOT EXISTS cabinet (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    room_id UUID,
    household_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_cabinet_household_id ON cabinet(household_id);
CREATE INDEX IF NOT EXISTS ix_cabinet_room_id ON cabinet(room_id);


-- ============================================

CREATE TABLE IF NOT EXISTS item (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_id UUID,
    cabinet_id UUID,
    household_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(200),
    quantity INTEGER NOT NULL DEFAULT 0,
    min_stock_alert INTEGER NOT NULL DEFAULT 0,
    photo VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_item_category_id 
        FOREIGN KEY (category_id) 
        REFERENCES category(id) 
        ON DELETE SET NULL,
    
    CONSTRAINT fk_item_cabinet_id 
        FOREIGN KEY (cabinet_id) 
        REFERENCES cabinet(id) 
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_item_household_id ON item(household_id);
CREATE INDEX IF NOT EXISTS ix_item_cabinet_id ON item(cabinet_id);
CREATE INDEX IF NOT EXISTS ix_item_category_id ON item(category_id);

-- ============================================

CREATE TABLE IF NOT EXISTS record (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    household_id UUID NOT NULL,
    user_name VARCHAR(100) NOT NULL,
    operate_type SMALLINT NOT NULL,
    entity_type SMALLINT NOT NULL,
    record_type SMALLINT NOT NULL DEFAULT 0,
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
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_record_household_id ON record(household_id);
CREATE INDEX IF NOT EXISTS ix_record_created_at ON record(created_at);
CREATE INDEX IF NOT EXISTS ix_record_operate_type ON record(operate_type);
CREATE INDEX IF NOT EXISTS ix_record_entity_type ON record(entity_type);
CREATE INDEX IF NOT EXISTS ix_record_record_type ON record(record_type);