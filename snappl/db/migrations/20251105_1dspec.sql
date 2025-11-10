CREATE TABLE spectrum1d(
  id UUID PRIMARY KEY,
  provenance_id UUID NOT NULL,
  diaobject_id UUID NOT NULL,
  diaobject_position_id UUID DEFAULT NULL,
  band text NOT NULL,
  filepath text NOT NULL,
  mjd_start double precision,
  mjd_end double precision,
  epoch int NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX ix_spectrum1d_provenance_id ON spectrum1d USING btree(provenance_id);
CREATE INDEX ix_spectrum1d_diaobject_id ON spectrum1d USING btree(diaobject_id);
CREATE INDEX ix_spectrum1d_diaobject_position_id ON spectrum1d USING btree(diaobject_position_id);
CREATE INDEX ix_spectrum1d_mjd_start ON spectrum1d USING btree(mjd_start);
CREATE INDEX ix_spectrum1d_mjd_end ON spectrum1d USING btree(mjd_end);
CREATE INDEX ix_spectrum1d_epoch ON spectrum1d USING btree(epoch);
CREATE UNIQUE INDEX ix_spectrum1d_unique ON spectrum1d USING btree(provenance_id,diaobject_id,epoch);
ALTER TABLE spectrum1d ADD CONSTRAINT fk_spectrum1d_provenance_id
  FOREIGN KEY(provenance_id) REFERENCES provenance(id);
ALTER TABLE spectrum1d ADD CONSTRAINT fk_spectrum1d_diaobject_id
  FOREIGN KEY(diaobject_id) REFERENCES diaobject(id);
ALTER TABLE spectrum1d ADD CONSTRAINT fk_spectrum1d_diaobject_position_id
  FOREIGN KEY(diaobject_position_id) REFERENCES diaobject_position(id);
COMMENT ON TABLE spectrum1d IS 'Single-epoch (combining ~4 images) 1d transient spectrum';
COMMENT ON COLUMN spectrum1d.mjd_start IS 'mjd of earliest image included';
COMMENT ON COLUMN spectrum1d.mjd_end IS 'mjd + exptime (in days) of latest image included';
COMMENT ON COLUMN spectrum1d.epoch IS 'millidays; floor( (Average MJD of images) * 1000 + 0.5 )';
  

CREATE TABLE spectrum1d_included_image(
  spectrum1d_id UUID,
  l2image_id UUID
);
CREATE UNIQUE INDEX ix_s1d_inclim_dual ON spectrum1d_included_image USING btree(spectrum1d_id, l2image_id);
CREATE INDEX ix_s1d_inclim_spec ON spectrum1d_included_image USING btree(spectrum1d_id);
CREATE INDEX ix_s1d_inclim_im ON spectrum1d_included_image USING btree(l2image_id);
ALTER TABLE spectrum1d_included_image ADD CONSTRAINT fk_s1d_inclim_spec
  FOREIGN KEY(spectrum1d_id) REFERENCES spectrum1d(id) ON DELETE CASCADE;
ALTER TABLE spectrum1d_included_image ADD CONSTRAINT fk_s1d_inclim_im
  FOREIGN KEY(l2image_id) REFERENCES l2image(id) ON DELETE RESTRICT;
  
