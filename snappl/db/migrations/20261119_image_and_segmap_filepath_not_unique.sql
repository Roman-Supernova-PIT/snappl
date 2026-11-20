-- The same file can be registered under more than one provenance: the Roman images that MAST
-- processes again (other calibration software or reference files) keep their file name, and so do
-- their segmentation maps, and each gets a row of its own under the provenance that says how it was
-- processed.  The unique indexes on filepath of l2image and of segmap become plain ones, so that
-- lookups by filepath stay fast.  The id (the primary key) is the only unique key that is left.
--
-- Do not change this file once it has been applied to a database: the migration runner
-- compares an md5 sum of every applied file.

DROP INDEX ix_l2image_filepath;
CREATE INDEX ix_l2image_filepath ON l2image(filepath);

DROP INDEX ix_segmap_filepath;
CREATE INDEX ix_segmap_filepath ON segmap(filepath);

COMMENT ON COLUMN l2image.filepath IS 'The file of the image (a path or a URI); not unique: one file has one row per provenance';
COMMENT ON COLUMN segmap.filepath IS 'The file of the segmentation map; not unique: one file has one row per provenance';
