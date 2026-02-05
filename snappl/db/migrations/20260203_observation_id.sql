ALTER TABLE l2image ADD COLUMN observation_id text;
UPDATE l2image SET observation_id=pointing;
CREATE INDEX idx_l2image_obseration_id ON l2image( observation_id );
ALTER TABLE l2image DROP COLUMN pointing;
