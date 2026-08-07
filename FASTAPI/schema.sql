-- ============================================================
-- SCHEMA: CMM Machine Maintenance Database
-- ============================================================
PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- Lookup table: equipment_type
-- Needed because equipment_type repeats across many machines,
-- so it can't be a FK target directly from machine_status.
-- This is what lets Table 1 and Table 2 join cleanly.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS equipment_type (
    equipment_type TEXT PRIMARY KEY
);

INSERT OR IGNORE INTO equipment_type (equipment_type) VALUES
    ('CNC Machine'),
    ('Lathe Machine'),
    ('Milling Machine'),
    ('Hydraulic Press'),
    ('Industrial Robot'),
    ('Air Compressor'),
    ('Conveyor Belt'),
    ('Packaging Machine'),
    ('Industrial Pump'),
    ('Boiler Unit'),
    ('Injection Molding Machine'),
    ('Welding Robot'),
    ('Grinding Machine'),
    ('Laser Cutting Machine'),
    ('Sheet Metal Press'),
    ('Drilling Machine'),
    ('Surface Grinder'),
    ('Assembly Robot'),
    ('Paint Booth'),
    ('Heat Treatment Furnace'),
    ('Cooling Tower'),
    ('Vacuum Pump'),
    ('Dust Collector'),
    ('Water Chiller'),
    ('Cooling Fan System'),
    ('Generator Unit'),
    ('Power Distribution Panel'),
    ('Material Handling Crane'),
    ('Automated Guided Vehicle'),
    ('Palletizer'),
    ('Shrink Wrapping Machine'),
    ('Bottle Filling Machine'),
    ('Labeling Machine'),
    ('Mixing Tank'),
    ('Extrusion Machine'),
    ('Rolling Mill'),
    ('Printing Machine'),
    ('Inspection Camera System'),
    ('Forklift Charging Station'),
    ('Quality Inspection Station');

-- ------------------------------------------------------------
-- Table 1: machine_status
-- machine_id is restricted to the fixed set M-101..M-140
-- via a CHECK constraint.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS machine_status (
    machine_id                     TEXT PRIMARY KEY
        CHECK (machine_id IN (
            'M-101','M-102','M-103','M-104','M-105','M-106','M-107','M-108',
            'M-109','M-110','M-111','M-112','M-113','M-114','M-115','M-116',
            'M-117','M-118','M-119','M-120','M-121','M-122','M-123','M-124',
            'M-125','M-126','M-127','M-128','M-129','M-130','M-131','M-132',
            'M-133','M-134','M-135','M-136','M-137','M-138','M-139','M-140'
        )),
    equipment_type                 TEXT NOT NULL
        REFERENCES equipment_type(equipment_type),
    machine_name                   TEXT,
    last_service_date              DATE,
    next_service_date              DATE,
    standard_service_interval_days INTEGER,
    expected_usage_hours           REAL,
    actual_usage_hours             REAL,
    days_since_last_service        INTEGER,
    down_time_start                DATETIME,
    down_time_end                  DATETIME,
    status                         TEXT,
    last_updated                   DATETIME
);

-- Pre-populate the 40 machines (id + name + type).
-- Other columns are left NULL until service/usage data is generated.
INSERT OR IGNORE INTO machine_status (machine_id, equipment_type, machine_name) VALUES
    ('M-101', 'CNC Machine', 'CNC Machine'),
    ('M-102', 'Lathe Machine', 'Lathe Machine'),
    ('M-103', 'Milling Machine', 'Milling Machine'),
    ('M-104', 'Hydraulic Press', 'Hydraulic Press'),
    ('M-105', 'Industrial Robot', 'Industrial Robot'),
    ('M-106', 'Air Compressor', 'Air Compressor'),
    ('M-107', 'Conveyor Belt', 'Conveyor Belt'),
    ('M-108', 'Packaging Machine', 'Packaging Machine'),
    ('M-109', 'Industrial Pump', 'Industrial Pump'),
    ('M-110', 'Boiler Unit', 'Boiler Unit'),
    ('M-111', 'Injection Molding Machine', 'Injection Molding Machine'),
    ('M-112', 'Welding Robot', 'Welding Robot'),
    ('M-113', 'Grinding Machine', 'Grinding Machine'),
    ('M-114', 'Laser Cutting Machine', 'Laser Cutting Machine'),
    ('M-115', 'Sheet Metal Press', 'Sheet Metal Press'),
    ('M-116', 'Drilling Machine', 'Drilling Machine'),
    ('M-117', 'Surface Grinder', 'Surface Grinder'),
    ('M-118', 'Assembly Robot', 'Assembly Robot'),
    ('M-119', 'Paint Booth', 'Paint Booth'),
    ('M-120', 'Heat Treatment Furnace', 'Heat Treatment Furnace'),
    ('M-121', 'Cooling Tower', 'Cooling Tower'),
    ('M-122', 'Vacuum Pump', 'Vacuum Pump'),
    ('M-123', 'Dust Collector', 'Dust Collector'),
    ('M-124', 'Water Chiller', 'Water Chiller'),
    ('M-125', 'Cooling Fan System', 'Cooling Fan System'),
    ('M-126', 'Generator Unit', 'Generator Unit'),
    ('M-127', 'Power Distribution Panel', 'Power Distribution Panel'),
    ('M-128', 'Material Handling Crane', 'Material Handling Crane'),
    ('M-129', 'Automated Guided Vehicle', 'Automated Guided Vehicle'),
    ('M-130', 'Palletizer', 'Palletizer'),
    ('M-131', 'Shrink Wrapping Machine', 'Shrink Wrapping Machine'),
    ('M-132', 'Bottle Filling Machine', 'Bottle Filling Machine'),
    ('M-133', 'Labeling Machine', 'Labeling Machine'),
    ('M-134', 'Mixing Tank', 'Mixing Tank'),
    ('M-135', 'Extrusion Machine', 'Extrusion Machine'),
    ('M-136', 'Rolling Mill', 'Rolling Mill'),
    ('M-137', 'Printing Machine', 'Printing Machine'),
    ('M-138', 'Inspection Camera System', 'Inspection Camera System'),
    ('M-139', 'Forklift Charging Station', 'Forklift Charging Station'),
    ('M-140', 'Quality Inspection Station', 'Quality Inspection Station');

-- ------------------------------------------------------------
-- Table 2: technician
-- equipment_type FKs to the same lookup table as machine_status,
-- so technician <-> machine_status can be joined on equipment_type.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS technician (
    technician_id           TEXT PRIMARY KEY,
    equipment_type          TEXT NOT NULL
        REFERENCES equipment_type(equipment_type),
    technician_name         TEXT,
    technician_phone_number TEXT
);

-- ------------------------------------------------------------
-- Table 3: part
-- Standalone lookup table, not linked to anything yet.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS part (
    part_id     TEXT PRIMARY KEY,
    part_name   TEXT,
    stock_size  INTEGER
);

-- ------------------------------------------------------------
-- Table: events
-- Logs every incoming sensor reading + the decision made from it.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    event_id            TEXT PRIMARY KEY,
    timestamp            DATETIME NOT NULL,
    machine_id           TEXT NOT NULL REFERENCES machine_status(machine_id),
    equipment_type        TEXT NOT NULL REFERENCES equipment_type(equipment_type),
    temperature           REAL,
    vibration              REAL,
    humidity               REAL,
    pressure               REAL,
    rotations_per_minute  REAL,
    failure_category      TEXT,
    severity               TEXT,
    confidence             REAL,
    risk_score             INTEGER,
    decision                TEXT,     -- 'advance' | 'delay' | 'no_change'
    date_shift_days        INTEGER,
    previous_next_service_date DATE,
    new_next_service_date DATE,
    reasoning               TEXT
);

-- ============================================================
-- Example JOIN: machine_status <-> technician via equipment_type
-- Gives you, for every machine, the technician(s) qualified
-- to service its equipment_type.
-- ============================================================
-- SELECT
--     m.machine_id,
--     m.machine_name,
--     m.equipment_type,
--     m.status,
--     t.technician_id,
--     t.technician_name,
--     t.technician_phone_number
-- FROM machine_status m
-- JOIN technician t
--     ON m.equipment_type = t.equipment_type
-- ORDER BY m.machine_id;
