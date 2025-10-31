ALTER TABLE l2image ADD COLUMN position_angle real DEFAULT NULL;
CREATE INDEX ix_l2image_posang ON l2image(position_angle);

ALTER TABLE segmap ADD COLUMN position_angle real DEFAULT NULL;
CREATE INDEX ix_segmap_posang ON segmap(position_angle);
