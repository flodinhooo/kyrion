-- Keep applied proof and identity history intact; failed checks grant no authority.
ALTER TABLE business_domain ADD COLUMN verification_failed_at TIMESTAMPTZ;
