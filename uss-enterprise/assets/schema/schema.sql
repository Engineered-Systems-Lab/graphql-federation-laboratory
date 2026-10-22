-- Assets service schema for PostgreSQL 17.
--
-- Applied once to an empty database by an administrative role; the release is loaded afterwards
-- by service/load_release.py. The service itself only reads, through a login that is a member of
-- the group role assets_reader (see the README for the one statement that creates it).
--
-- The kind-to-category table lives here and nowhere else in the service: asset_kinds says which
-- category a kind belongs to, asset_categories says which categories may carry other assets, and
-- the category of an asset is never stored: the view asset_records derives it from the kind.
-- Contract 1.0 and docs/ASSETS-V1-DESIGN.md own the values; a new kind is one row of asset_kinds.

DO $roles$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'assets_reader') THEN
        CREATE ROLE assets_reader NOLOGIN;
    END IF;
END
$roles$;

-- Reference data -------------------------------------------------------------------------------

CREATE TABLE asset_categories (
    category        text    PRIMARY KEY CHECK (category ~ '^[A-Z]+$'),
    can_be_parent   boolean NOT NULL
);

CREATE TABLE asset_kinds (
    kind            text    PRIMARY KEY CHECK (kind ~ '^[A-Z]+(_[A-Z]+)*$'),
    category        text    NOT NULL REFERENCES asset_categories (category)
);

CREATE TABLE asset_statuses (
    status          text    PRIMARY KEY CHECK (status ~ '^[A-Z]+$')
);

INSERT INTO asset_categories (category, can_be_parent) VALUES
    ('VEHICLE', true),
    ('EQUIPMENT', false);

INSERT INTO asset_kinds (kind, category) VALUES
    ('STARSHIP', 'VEHICLE'),
    ('SHUTTLE', 'VEHICLE'),
    ('ROVER', 'VEHICLE'),
    ('ARMORED_VEHICLE', 'VEHICLE'),
    ('PHASER', 'EQUIPMENT'),
    ('TRICORDER', 'EQUIPMENT'),
    ('COMMUNICATOR', 'EQUIPMENT'),
    ('SCIENTIFIC_INSTRUMENT', 'EQUIPMENT'),
    ('MUSICAL_INSTRUMENT', 'EQUIPMENT');

INSERT INTO asset_statuses (status) VALUES
    ('ACTIVE'),
    ('MAINTENANCE'),
    ('DECOMMISSIONED'),
    ('DESTROYED'),
    ('MISSING');

-- The assets ------------------------------------------------------------------------------------

CREATE TABLE assets (
    asset_id        text    PRIMARY KEY CHECK (asset_id ~ '^[A-Z]{2,8}(?:_[A-Z]{1,8}){0,2}-(?:0[0-9]{2}[1-9]|0[0-9][1-9][0-9]|0[1-9][0-9]{2}|[1-9][0-9]{3,})$'),
    kind            text    NOT NULL REFERENCES asset_kinds (kind),
    name            text    NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
    description     text    NOT NULL CHECK (char_length(description) BETWEEN 1 AND 1000),
    status          text    NOT NULL REFERENCES asset_statuses (status),
    parent_asset_id text    REFERENCES assets (asset_id),
    -- The two parts of the identifier, kept for the order: the letter prefix as text, then the
    -- number as a number, so AST-0002 comes before AST-0017, AST-9999 before AST-10000 and AB before AB_C.
    -- Computed only for a well-formed identifier, so that the check below refuses a malformed one with its own error.
    asset_prefix    text    GENERATED ALWAYS AS (CASE WHEN asset_id ~ '^[A-Z]{2,8}(?:_[A-Z]{1,8}){0,2}-(?:0[0-9]{2}[1-9]|0[0-9][1-9][0-9]|0[1-9][0-9]{2}|[1-9][0-9]{3,})$' THEN split_part(asset_id, '-', 1) END) STORED,
    asset_number    numeric GENERATED ALWAYS AS (CASE WHEN asset_id ~ '^[A-Z]{2,8}(?:_[A-Z]{1,8}){0,2}-(?:0[0-9]{2}[1-9]|0[0-9][1-9][0-9]|0[1-9][0-9]{2}|[1-9][0-9]{3,})$' THEN split_part(asset_id, '-', 2)::numeric END) STORED,
    CONSTRAINT assets_not_its_own_parent CHECK (parent_asset_id IS DISTINCT FROM asset_id)
);

CREATE INDEX assets_by_id_order ON assets (asset_prefix COLLATE "C", asset_number);
CREATE INDEX assets_by_parent ON assets (parent_asset_id);
CREATE INDEX assets_by_kind ON assets (kind);
CREATE INDEX assets_by_status ON assets (status);

-- The read model: the category is derived from the kind and never stored apart from it.
CREATE VIEW asset_records AS
SELECT a.asset_id, a.kind, k.category, a.name, a.description, a.status, a.parent_asset_id,
       a.asset_prefix, a.asset_number
FROM assets a
JOIN asset_kinds k ON k.kind = a.kind;

-- Rules the contract cannot express ------------------------------------------------------------
-- A parent exists (the foreign key), only a VEHICLE may be a parent, an asset is not its own parent
-- (the check above) and the parent chain has no cycle.

CREATE FUNCTION assets_check_parent() RETURNS trigger
LANGUAGE plpgsql AS $function$
DECLARE
    parent_may_carry boolean;
BEGIN
    IF NEW.parent_asset_id IS NULL THEN
        RETURN NEW;
    END IF;
    SELECT c.can_be_parent INTO parent_may_carry
    FROM assets p
    JOIN asset_kinds k ON k.kind = p.kind
    JOIN asset_categories c ON c.category = k.category
    WHERE p.asset_id = NEW.parent_asset_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'the parent asset % does not exist', NEW.parent_asset_id
            USING ERRCODE = 'foreign_key_violation';
    END IF;
    IF NOT parent_may_carry THEN
        RAISE EXCEPTION 'asset % cannot be a parent: only a VEHICLE may carry other assets', NEW.parent_asset_id
            USING ERRCODE = 'check_violation';
    END IF;
    IF EXISTS (
        WITH RECURSIVE above(asset_id, parent_asset_id) AS (
            SELECT p.asset_id, p.parent_asset_id FROM assets p WHERE p.asset_id = NEW.parent_asset_id
            UNION
            SELECT p.asset_id, p.parent_asset_id FROM assets p JOIN above ON p.asset_id = above.parent_asset_id
        )
        SELECT 1 FROM above WHERE above.asset_id = NEW.asset_id
    ) THEN
        RAISE EXCEPTION 'asset % would be its own ancestor', NEW.asset_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$function$;

CREATE TRIGGER assets_parent_rules
    BEFORE INSERT OR UPDATE OF parent_asset_id ON assets
    FOR EACH ROW EXECUTE FUNCTION assets_check_parent();

-- A change of kind must not turn an asset that carries others into one that cannot.
CREATE FUNCTION assets_check_kind_change() RETURNS trigger
LANGUAGE plpgsql AS $function$
BEGIN
    IF EXISTS (SELECT 1 FROM assets child WHERE child.parent_asset_id = NEW.asset_id)
       AND NOT (SELECT c.can_be_parent FROM asset_kinds k JOIN asset_categories c ON c.category = k.category
                WHERE k.kind = NEW.kind) THEN
        RAISE EXCEPTION 'asset % carries other assets and cannot take a kind that cannot be a parent', NEW.asset_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$function$;

CREATE TRIGGER assets_kind_change_rules
    BEFORE UPDATE OF kind ON assets
    FOR EACH ROW EXECUTE FUNCTION assets_check_kind_change();

-- The reference tables are append-only: a new kind is a new row; a change would break the rows that use it.
CREATE FUNCTION asset_reference_is_append_only() RETURNS trigger
LANGUAGE plpgsql AS $function$
BEGIN
    RAISE EXCEPTION '% is reference data and is append-only', TG_TABLE_NAME
        USING ERRCODE = 'integrity_constraint_violation';
END
$function$;

CREATE TRIGGER asset_categories_append_only BEFORE UPDATE OR DELETE ON asset_categories
    FOR EACH ROW EXECUTE FUNCTION asset_reference_is_append_only();
CREATE TRIGGER asset_categories_no_truncate BEFORE TRUNCATE ON asset_categories
    FOR EACH STATEMENT EXECUTE FUNCTION asset_reference_is_append_only();
CREATE TRIGGER asset_kinds_append_only BEFORE UPDATE OR DELETE ON asset_kinds
    FOR EACH ROW EXECUTE FUNCTION asset_reference_is_append_only();
CREATE TRIGGER asset_kinds_no_truncate BEFORE TRUNCATE ON asset_kinds
    FOR EACH STATEMENT EXECUTE FUNCTION asset_reference_is_append_only();
CREATE TRIGGER asset_statuses_append_only BEFORE UPDATE OR DELETE ON asset_statuses
    FOR EACH ROW EXECUTE FUNCTION asset_reference_is_append_only();
CREATE TRIGGER asset_statuses_no_truncate BEFORE TRUNCATE ON asset_statuses
    FOR EACH STATEMENT EXECUTE FUNCTION asset_reference_is_append_only();

-- The service only reads ------------------------------------------------------------------------

GRANT SELECT ON asset_categories, asset_kinds, asset_statuses, assets, asset_records TO assets_reader;
