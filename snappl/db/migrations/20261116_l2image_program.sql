-- The Roman program (an integer such as 1055) of an l2image.
--
-- A Roman image file is named r<visit 19 digits>_<exposure 4 digits>_wfi<NN>_<filter>_cal.asdf, and the
-- first 5 digits of the visit are the program (the same number as the program field of the MAST
-- Roman archive; checked on 1,932 rows with 0 differences). New rows carry it from the ingest; this
-- file fills it for the rows that exist, from their file path. Rows whose file name does not have
-- that form (simulations, other sources) keep NULL.
--
-- Do not change this file once it has been applied to a database: the migration runner
-- compares an md5 sum of every applied file.

ALTER TABLE l2image ADD COLUMN program integer DEFAULT NULL;

UPDATE l2image
   SET program = substring( filepath FROM '(?:^|/)r([0-9]{5})[0-9]{14}_[0-9]{4}_wfi[0-9]{2}_' )::integer
 WHERE filepath ~ '(?:^|/)r[0-9]{19}_[0-9]{4}_wfi[0-9]{2}_';

CREATE INDEX ix_l2image_program ON l2image ( program );

COMMENT ON COLUMN l2image.program IS
  'Roman program: the first 5 digits of the visit id in the file name; NULL when the name has no such id';
