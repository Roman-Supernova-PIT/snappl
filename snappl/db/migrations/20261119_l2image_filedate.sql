-- The file creation date that MAST gives for the file of an image.  It tells the processings of one
-- file apart: a file that MAST processes again is delivered again with a later date, and its row (under
-- another provenance) has the later filedate.  NULL for an image that was not registered from MAST.
--
-- Do not change this file once it has been applied to a database: the migration runner
-- compares an md5 sum of every applied file.

ALTER TABLE l2image ADD COLUMN filedate timestamp with time zone DEFAULT NULL;

COMMENT ON COLUMN l2image.filedate IS 'The file creation date that MAST gives for the file; later for a later processing of the same file';
