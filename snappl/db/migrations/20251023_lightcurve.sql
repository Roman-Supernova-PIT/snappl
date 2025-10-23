-- Totally redo the lightcurve table
-- Don't have any production databases yet, so we can freely drop this table.

CREATE TABLE lightcurve(
  id UUID PRIMARY KEY,
  provenance_id UUID NOT NULL,
  diaobject_id UUID NOT NULL,
  diaobject_position_id UUID DEFAULT NULL,
  bands text[],
  filepath text NOT NULL,
  created_at timestamp with time zone default NOW()
);
CREATE INDEX ix_lightcurve_provenance ON lightcurve(provenance_id);
CREATE INDEX ix_lightcurve_diaobject ON lightcurve(diaobject_id);
CREATE INDEX ix_lightcurve_diaobject_position ON lightcurve(diaobject_position_id);
CREATE INDEX ix_lightcurve_filepath ON lightcurve(filepath);
CREATE UNIQUE INDEX ix_lightcurve_spec ON lightcurve(provenance_id,diaobject_id,bands);
ALTER TABLE lightcurve ADD CONSTRAINT fk_lightcurve_prov
  FOREIGN KEY(provenance_id) REFERENCES provenance(id) ON DELETE RESTRICT;
ALTER TABLE lightcurve ADD CONSTRAINT fk_lightcurve_diaobject
  FOREIGN KEY(diaobject_id) REFERENCES diaobject(id) ON DELETE RESTRICT;
ALTER TABLE lightcurve ADD CONSTRAINT fk_lightcurve_diaobject_position
  FOREIGN KEY(diaobject_position_id) REFERENCES diaobject_position(id) ON DELETE RESTRICT;
COMMENT ON TABLE lightcurve IS 'Transient object light curves; (provenance_id,diaobject_id,filter) is unique';
COMMENT ON COLUMN lightcurve.bands IS 'Filters included in the lightcurve, sorted alphabetically.';
COMMENT ON COLUMN filepath IS 'file path relative to standard base directory of lightcurve storage';
