CREATE TABLE segmap(
    id UUID PRIMARY KEY,
    provenance_id UUID NOT NULL,
    band text NOT NULL,
    ra double precision NOT NULL,
    dec double precision NOT NULL,
    ra_corner_00 real NOT NULL,
    ra_corner_01 real NOT NULL,
    ra_corner_10 real NOT NULL,
    ra_corner_11 real NOT NULL,
    dec_corner_00 real NOT NULL,
    dec_corner_01 real NOT NULL,
    dec_corner_10 real NOT NULL,
    dec_corner_11 real NOT NULL,
    filepath text NOT NULL,
    width smallint,
    height smallint,
    format smallint NOT NULL DEFAULT 0,
    l2image_id UUID DEFAULT NULL
);
CREATE INDEX ix_segmap_band ON segmap (band);
CREATE INDEX ix_segmap_q3c ON segmap (q3c_ang2ipix(ra,dec));
CREATE INDEX ix_segmap_ra00 ON segmap (ra_corner_00);
CREATE INDEX ix_segmap_ra01 ON segmap (ra_corner_01);
CREATE INDEX ix_segmap_ra10 ON segmap (ra_corner_10);
CREATE INDEX ix_segmap_ra11 ON segmap (ra_corner_11);
CREATE INDEX ix_segmap_dec00 ON segmap (dec_corner_00);
CREATE INDEX ix_segmap_dec01 ON segmap (dec_corner_01);
CREATE INDEX ix_segmap_dec10 ON segmap (dec_corner_10);
CREATE INDEX ix_segmap_dec11 ON segmap (dec_corner_11);
CREATE UNIQUE INDEX ix_segmap_filepath ON segmap (filepath);
CREATE INDEX iX_segmap_l2image ON segmap (l2image_id);
ALTER TABLE segmap ADD CONSTRAINT fk_segmap_l2image
  FOREIGN KEY(l2image_id) REFERENCES l2image(id) ON DELETE RESTRICT;
COMMENT ON TABLE segmap IS 'Segmentation maps';
COMMENT ON COLUMN segmap.ra_corner_00 IS 'RA of pixel (0,0)';
COMMENT ON COLUMN segmap.ra_corner_01 IS 'RA of pixel (0,height-1)';
COMMENT ON COLUMN segmap.ra_corner_10 IS 'RA of pixel (width-1,0)';
COMMENT ON COLUMN segmap.ra_corner_11 IS 'RA of pixel (width-1,height-1)';
COMMENT ON COLUMN segmap.dec_corner_00 IS 'Dec of pixel (0,0)';
COMMENT ON COLUMN segmap.dec_corner_01 IS 'Dec of pixel (0,height-1)';
COMMENT ON COLUMN segmap.dec_corner_10 IS 'Dec of pixel (width-1,0)';
COMMENT ON COLUMN segmap.dec_corner_11 IS 'Dec of pixel (width-1,height-1)';
COMMENT ON COLUMN segmap.l2image_id IS 'This segmentation map is for this image';
COMMENT ON COLUMN segmap.format IS '0=Unknown, 1=OpenUniverse2024FITSImage';
