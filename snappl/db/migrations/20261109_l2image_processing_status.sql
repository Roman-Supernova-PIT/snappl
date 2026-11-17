-- Processing status of an l2image, for the MAST ingest (the package snpit_mast_ingest).
--
-- Lifecycle of an image that the ingest registers:
--
--   standby     registered on purpose without being queued (PRISM: waits for spectroscopy)
--   ingested    registered, not yet announced on the processing queue
--   queued      the ingest sent its message to the queue (queued_at is that moment)
--   processing  the pipeline picked the message up
--   done        the pipeline finished the image
--   failed      the message went to the dead letter queue (set by the dead letter handler)
--
-- NULL means "not tracked": every row that existed before this migration, and any image
-- that was not registered by the ingest. The ingest only touches rows with 'ingested'.
--
-- Do not change this file once it has been applied to a database: the migration runner
-- compares an md5 sum of every applied file.

ALTER TABLE l2image ADD COLUMN processing_status text DEFAULT NULL;
ALTER TABLE l2image ADD COLUMN queued_at timestamp with time zone DEFAULT NULL;
ALTER TABLE l2image ADD COLUMN status_updated_at timestamp with time zone DEFAULT NULL;

ALTER TABLE l2image ADD CONSTRAINT ck_l2image_processing_status
  CHECK (processing_status IN ('standby', 'ingested', 'queued', 'processing', 'done', 'failed'));

-- The ingest's "what is still to announce" query reads only this small slice of the table.
CREATE INDEX ix_l2image_pending ON l2image (provenance_id, mjd) WHERE processing_status = 'ingested';
CREATE INDEX ix_l2image_processing_status ON l2image (processing_status);

COMMENT ON COLUMN l2image.processing_status IS
  'NULL=not tracked, standby, ingested, queued, processing, done or failed (see the migration)';
COMMENT ON COLUMN l2image.queued_at IS 'When the ingest sent the message that starts the processing';
COMMENT ON COLUMN l2image.status_updated_at IS 'When processing_status last changed';
