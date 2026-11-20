-- filepath of a spectrum1d row may now be an object store URI such as s3://bucket/key as well as a
-- path relative to the base path.  Nothing else about the file is stored: its format and its version
-- are in its name (and the version is in the file itself).  The images that went into a spectrum are
-- in spectrum1d_included_image.
--
-- Do not change this file once it has been applied to a database: the migration runner
-- compares an md5 sum of every applied file.

COMMENT ON COLUMN spectrum1d.filepath IS 'A path relative to the base path, or an object store URI such as s3://bucket/key';
