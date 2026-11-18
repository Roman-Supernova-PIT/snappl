CREATE TABLE diaforcedsource(
  id UUID PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
  provenance_id UUID NOT NULL,
  diaobject_id UUID NOT NULL,
  diaobject_position_id UUID DEFAULT NULL,
  image_id UUID NOT NULL,
  template_id UUID NOT NULL,
  flux real NOT NULL,
  dflux real NOT NULL
);
CREATE INDEX ix_diaforcedsource_provenance_id ON diaforcedsource(provenance_id);
CREATE INDEX ix_diaforcedsource_diaobject_id ON diaforcedsource(diaobject_id);
CREATE INDEX ix_diaforcedsource_diaobject_position_id ON diaforcedsource(diaobject_position_id);
CREATE INDEX ix_diaforcedsource_image_id ON diaforcedsourced(image_id);
CREATE INDEX ix_diaforcedsource_template_id ON diaforcedsource(template_id);
ALTER TABLE diaforcedsource ADD CONSTRAINT fk_diaforcedsource_provenance
  FOREIGN KEY(provenance_id) REFERENCES provenance(id) ON DELETE RESTRICT;
ALTER TABLE diaforcedsource ADD CONSTRAINT fk_diaforcedsource_diaobject
  FOREIGN KEY(diaobject_id) REFERENCES diaobject(id) ON DELETE RESTRICT;
ALTER TABLE diaforcedsource ADD CONSTRAINT fk_diaforcedsource_diaobject_position
  FOREIGN KEY(diaobject_position_id) REFERENCES diaobject_position(id) ON DELETE RESTRICT;
ALTER TABLE diaforcedsource ADD CONSTRAINT fk_diaforcedsource_image
  FOREIGN KEY(image_id) REFERENCES l2image(id) ON DELETE RESTRICT;
ALTER TABLE diaforcedsource ADD CONSTRAINT fk_diaforcedsource_template
  FOREIGN KEY(template_id) REFERENCES l2image(id) ON DELETE RESTRICT;
ALTER TABLE diaforcedsource add constraint cnst_diaforcedsource_unique
  UNIQUE( provenance_id, diaobject_id, diaobject_position_id, image_id, template_id );
