ALTER TABLE l2image RENAME COLUMN mjd_start TO mjd;
COMMENT ON COLUMN l2image.mjd IS 'MJD at start of exposure';
