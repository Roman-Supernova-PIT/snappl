CREATE TABLE zeropoint(
    id UUID PRIMARY KEY,
    image_id UUID NOT NULL,
    provenance_id UUID NOT NULL,
    zp real NOT NULL,
    dzp real NOT NULL
);
CREATE INDEX ix_zeropoint_image_id ON zeropoint(image_id);
CREATE INDEX ix_zeropoint_provenance_id ON zeropoint(provenance_id);
CREATE UNIQUE INDEX ix_zeropoint_unique ON zeropoint(image_id, provenance_id);
ALTER TABLE zeropoint ADD CONSTRAINT fk_zeropoint_image
  FOREIGN KEY(image_id) REFERENCES l2image(id) ON DELETE RESTRICT;
ALTER TABLE zeropoint ADD CONSTRAINT fk_zeropoint_provid
  FOREIGN KEY(provenance_id) REFERENCES provenance(id) ON DELETE RESTRICT;
