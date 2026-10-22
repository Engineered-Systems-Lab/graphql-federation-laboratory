-- Missions six-table schema, Oracle 18c. UTC TIMESTAMP(3) values.
-- XML/domain code-point bounds are validated before persistence; human text
-- has physical headroom. External reference capacity 50 is a lab limitation.
CREATE TABLE missions (
  mission_id VARCHAR2(12 BYTE) PRIMARY KEY,
  title VARCHAR2(144 CHAR) NOT NULL,
  mission_type VARCHAR2(20 BYTE) NOT NULL,
  classification VARCHAR2(12 BYTE) NOT NULL,
  status VARCHAR2(12 BYTE) NOT NULL,
  priority NUMBER(1) NOT NULL,
  stardate NUMBER(7,2) NOT NULL,
  duration_hours NUMBER(4) NOT NULL,
  objective CLOB NOT NULL,
  location_type VARCHAR2(12 BYTE) NOT NULL,
  location_name VARCHAR2(144 CHAR) NOT NULL,
  coordinates VARCHAR2(144 CHAR),
  travel_vector VARCHAR2(144 CHAR),
  issuing_authority VARCHAR2(24 BYTE) NOT NULL,
  commanding_officer_id VARCHAR2(50 BYTE),
  estimated_cost NUMBER(15,2),
  actual_cost NUMBER(15,2),
  outcome CLOB,
  last_updated TIMESTAMP(3) NOT NULL,
  current_change_id NUMBER(28) NOT NULL,
  cancelled_without_estimate_allowed NUMBER(1) DEFAULT 0 NOT NULL,
  CONSTRAINT m_id CHECK (REGEXP_LIKE(mission_id,'^ST-[A-Z0-9]{9}$','c')),
  CONSTRAINT m_type CHECK (mission_type IN ('DIPLOMATIC','EXPLORATION','SCIENTIFIC','FIRST_CONTACT','MEDICAL','RESCUE','HUMANITARIAN','SECURITY','TACTICAL','TRANSPORT','MAINTENANCE')),
  CONSTRAINT m_class CHECK (classification IN ('UNCLASSIFIED','SECRET','TOP_SECRET')),
  CONSTRAINT m_status CHECK (status IN ('PLANNED','AUTHORIZED','ACTIVE','POSTPONED','COMPLETED','FAILED','CANCELLED')),
  CONSTRAINT m_priority CHECK (priority BETWEEN 1 AND 5),
  CONSTRAINT m_stardate CHECK (stardate >= 43000 AND stardate < 49000 AND MOD(stardate * 100,5)=0),
  CONSTRAINT m_duration CHECK (duration_hours BETWEEN 1 AND 8760),
  CONSTRAINT m_location CHECK (location_type IN ('PLANET','STARBASE','VESSEL','SECTOR','DEEP_SPACE','ENTERPRISE','OTHER')),
  CONSTRAINT m_authority CHECK (issuing_authority IN ('STARFLEET_COMMAND','ENTERPRISE_COMMAND','STARFLEET_MEDICAL','STARFLEET_SCIENCE','STARFLEET_SECURITY','FEDERATION_COUNCIL')),
  CONSTRAINT m_commander CHECK (commanding_officer_id IS NULL OR REGEXP_LIKE(commanding_officer_id,'^C-[1-9][0-9]*$','c')),
  CONSTRAINT m_required_commander CHECK (status IN ('PLANNED','CANCELLED') OR commanding_officer_id IS NOT NULL),
  CONSTRAINT m_cancel_flag CHECK (cancelled_without_estimate_allowed IN (0,1) AND (status='CANCELLED' OR cancelled_without_estimate_allowed=0)),
  CONSTRAINT m_estimate CHECK (estimated_cost IS NULL OR estimated_cost>=0),
  CONSTRAINT m_actual CHECK (actual_cost IS NULL OR actual_cost>=0),
  CONSTRAINT m_cost_lifecycle CHECK (
    (status='PLANNED' AND actual_cost IS NULL) OR
    (status IN ('AUTHORIZED','ACTIVE','POSTPONED') AND estimated_cost IS NOT NULL AND actual_cost IS NULL) OR
    (status IN ('COMPLETED','FAILED') AND estimated_cost IS NOT NULL AND actual_cost IS NOT NULL) OR
    (status='CANCELLED' AND actual_cost IS NOT NULL AND (estimated_cost IS NOT NULL OR cancelled_without_estimate_allowed=1))),
  CONSTRAINT m_current CHECK (current_change_id>0 AND current_change_id=TRUNC(current_change_id))
);
CREATE TABLE mission_assigned_crew (
  mission_id VARCHAR2(12 BYTE) NOT NULL REFERENCES missions(mission_id),
  reference VARCHAR2(50 BYTE) NOT NULL,
  PRIMARY KEY (mission_id, reference),
  CHECK (REGEXP_LIKE(reference,'^C-[1-9][0-9]*$','c'))
);
CREATE TABLE mission_participants (
  mission_id VARCHAR2(12 BYTE) NOT NULL REFERENCES missions(mission_id),
  reference VARCHAR2(50 BYTE) NOT NULL,
  PRIMARY KEY (mission_id, reference),
  CHECK (REGEXP_LIKE(reference,'^[PO]-[1-9][0-9]*$','c'))
);
CREATE TABLE mission_assigned_assets (
  mission_id VARCHAR2(12 BYTE) NOT NULL REFERENCES missions(mission_id),
  reference VARCHAR2(50 BYTE) NOT NULL,
  PRIMARY KEY (mission_id, reference),
  CHECK (REGEXP_LIKE(reference,'^[A-Z]{2,5}-[1-9][0-9]*$','c'))
);
CREATE TABLE mission_changes (
  change_id NUMBER(28) PRIMARY KEY,
  mission_id VARCHAR2(12 BYTE) NOT NULL REFERENCES missions(mission_id),
  operation VARCHAR2(7 BYTE) NOT NULL,
  changed_at TIMESTAMP(3) NOT NULL,
  changed_by VARCHAR2(50 BYTE) NOT NULL,
  ordered_by VARCHAR2(50 BYTE) NOT NULL,
  previous_status VARCHAR2(12 BYTE),
  new_status VARCHAR2(12 BYTE) NOT NULL,
  estimated_cost NUMBER(15,2),
  estimated_cost_change NUMBER(15,2),
  actual_cost NUMBER(15,2),
  actual_cost_change NUMBER(15,2),
  summary VARCHAR2(308 CHAR) NOT NULL,
  CONSTRAINT c_id CHECK (change_id>0 AND change_id=TRUNC(change_id)),
  CONSTRAINT c_actor CHECK (REGEXP_LIKE(changed_by,'^C-[1-9][0-9]*$','c') AND REGEXP_LIKE(ordered_by,'^C-[1-9][0-9]*$','c')),
  CONSTRAINT c_population CHECK ((operation='CREATED' AND previous_status IS NULL) OR (operation='UPDATED' AND previous_status IS NOT NULL)),
  CONSTRAINT c_status CHECK (new_status IN ('PLANNED','AUTHORIZED','ACTIVE','POSTPONED','COMPLETED','FAILED','CANCELLED') AND (previous_status IS NULL OR previous_status IN ('PLANNED','AUTHORIZED','ACTIVE','POSTPONED','COMPLETED','FAILED','CANCELLED'))),
  CONSTRAINT c_estimate CHECK (estimated_cost IS NULL OR estimated_cost>=0),
  CONSTRAINT c_actual CHECK (actual_cost IS NULL OR actual_cost>=0),
  CONSTRAINT c_estimate_absence CHECK (estimated_cost IS NOT NULL OR estimated_cost_change IS NULL),
  CONSTRAINT c_actual_absence CHECK (actual_cost IS NOT NULL OR actual_cost_change IS NULL)
);
CREATE INDEX mission_changes_order ON mission_changes(mission_id, change_id);
CREATE TABLE mission_clock (
  singleton NUMBER(1) PRIMARY KEY CHECK (singleton=1),
  baseline TIMESTAMP(3) NOT NULL,
  counter NUMBER(28) NOT NULL CHECK (counter>=0 AND counter=TRUNC(counter)),
  interval_ms NUMBER(8) NOT NULL CHECK (interval_ms=1000),
  dataset_version VARCHAR2(32 BYTE) NOT NULL,
  release_sha256 VARCHAR2(64 BYTE) NOT NULL CHECK (REGEXP_LIKE(release_sha256,'^[0-9a-f]{64}$','c'))
);
CREATE SEQUENCE mission_id_seq START WITH 1 MINVALUE 1 MAXVALUE 101559956668415 NOCACHE NOCYCLE;
CREATE SEQUENCE change_id_seq START WITH 1 MINVALUE 1 MAXVALUE 9999999999999999999999999999 NOCACHE NOCYCLE;
CREATE OR REPLACE TRIGGER missions_identity_immutable
BEFORE UPDATE OF mission_id ON missions FOR EACH ROW
BEGIN
  IF :NEW.mission_id != :OLD.mission_id THEN
    RAISE_APPLICATION_ERROR(-20001,'Mission identity is immutable');
  END IF;
END;
/
CREATE OR REPLACE TRIGGER mission_changes_append_only
BEFORE UPDATE OR DELETE ON mission_changes
BEGIN
  RAISE_APPLICATION_ERROR(-20002,'Mission audit is append-only');
END;
/
-- Later repository writes must call tick before target-row lock, recheck ETag,
-- allocate change_id_seq while holding this lock, then write and commit together.
-- This helper never commits or rolls back the caller's transaction.
CREATE OR REPLACE FUNCTION missions_clock_tick RETURN TIMESTAMP
AUTHID DEFINER
IS
  v_baseline TIMESTAMP(3);
  v_counter NUMBER(28);
  v_interval NUMBER(8);
BEGIN
  SELECT baseline,counter,interval_ms INTO v_baseline,v_counter,v_interval
    FROM mission_clock WHERE singleton=1 FOR UPDATE;
  v_counter := v_counter+1;
  UPDATE mission_clock SET counter=v_counter WHERE singleton=1;
  RETURN v_baseline + NUMTODSINTERVAL(v_counter*v_interval/1000,'SECOND');
END;
/
CREATE OR REPLACE TRIGGER missions_outcome_domain
BEFORE INSERT OR UPDATE ON missions FOR EACH ROW
BEGIN
  IF :NEW.status NOT IN ('COMPLETED','FAILED','CANCELLED') AND :NEW.outcome IS NOT NULL THEN
    RAISE_APPLICATION_ERROR(-20003,'Outcome forbidden for nonterminal mission');
  END IF;
END;
/
