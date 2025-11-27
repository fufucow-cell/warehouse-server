-- ============================================
-- Migration: 002_alter_cabinet_room_id_nullable.sql
-- Description: 修改 cabinet 表的 room_id 字段为可空（nullable）
-- ============================================

-- 修改 cabinet 表的 room_id 字段为可空
ALTER TABLE cabinet ALTER COLUMN room_id DROP NOT NULL;

-- 添加注释
COMMENT ON COLUMN cabinet.room_id IS '房间 ID（关联到 household_server.room.id，跨服务无法建立外键约束，可选）';

