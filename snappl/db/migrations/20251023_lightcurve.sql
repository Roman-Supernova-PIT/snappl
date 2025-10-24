ALTER TABLE l2image RENAME COLUMN filter TO band;
ALTER TABLE summed_image RENAME COLUMN filter TO band;
ALTER TABLE lightcurve RENAME COLUMN filter TO band;

ALTER TABLE lightcurve ADD COLUMN diaobject_position_id UUID DEFAULT NULL;
