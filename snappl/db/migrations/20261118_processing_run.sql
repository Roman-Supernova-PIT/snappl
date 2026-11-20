-- The state of one run of a pipeline for one object and one epoch.
--
-- l2image.processing_status says what happened to an image; it cannot say that a run for
-- one of the many objects in that image is done.  This table can: a run is identified by
-- (process, object, epoch), where epoch is in millidays, as spectrum1d.epoch
-- (floor( (average MJD of the images) * 1000 + 0.5 )).
--
-- Lifecycle:
--
--   processing  the run started
--   done        the run finished and registered its product (provenance_id, if it made one)
--   failed      the run failed (message says why)
--
-- A run is repeated on purpose (a new release, a corrected configuration), so starting a run
-- that exists, whatever its status, sets it back to processing and clears its message,
-- provenance and finish time; a start is never refused.
--
-- Do not change this file once it has been applied to a database: the migration runner
-- compares an md5 sum of every applied file.

CREATE TABLE processing_run(
  id UUID PRIMARY KEY,
  process text NOT NULL,
  diaobject_id UUID NOT NULL,
  epoch int NOT NULL,
  status text NOT NULL,
  execution text DEFAULT NULL,
  provenance_id UUID DEFAULT NULL,
  message text DEFAULT NULL,
  created_at timestamp with time zone DEFAULT NOW(),
  started_at timestamp with time zone DEFAULT NULL,
  finished_at timestamp with time zone DEFAULT NULL,
  status_updated_at timestamp with time zone DEFAULT NULL
);
CREATE UNIQUE INDEX ix_processing_run_unique ON processing_run USING btree(process, diaobject_id, epoch);
CREATE INDEX ix_processing_run_diaobject_id ON processing_run USING btree(diaobject_id);
CREATE INDEX ix_processing_run_status ON processing_run USING btree(status);
CREATE INDEX ix_processing_run_provenance_id ON processing_run USING btree(provenance_id);

ALTER TABLE processing_run ADD CONSTRAINT ck_processing_run_status
  CHECK (status IN ('processing', 'done', 'failed'));
ALTER TABLE processing_run ADD CONSTRAINT fk_processing_run_diaobject_id
  FOREIGN KEY(diaobject_id) REFERENCES diaobject(id);
ALTER TABLE processing_run ADD CONSTRAINT fk_processing_run_provenance_id
  FOREIGN KEY(provenance_id) REFERENCES provenance(id);

COMMENT ON TABLE processing_run IS 'The state of a run of a pipeline for one object and one epoch';
COMMENT ON COLUMN processing_run.process IS 'Which pipeline, for example spec_pipeline';
COMMENT ON COLUMN processing_run.epoch IS 'millidays, as spectrum1d.epoch: floor( (average MJD of the images) * 1000 + 0.5 )';
COMMENT ON COLUMN processing_run.status IS 'processing, done or failed';
COMMENT ON COLUMN processing_run.execution IS 'The name of the execution of the workflow that ran it (never an ARN)';
COMMENT ON COLUMN processing_run.provenance_id IS 'The provenance of the product, once the run is done';
COMMENT ON COLUMN processing_run.message IS 'Why the run failed';
