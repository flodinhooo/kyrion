ALTER TABLE integration_connection
    ADD COLUMN device_class VARCHAR(40) NOT NULL DEFAULT 'other';

UPDATE integration_connection
SET device_class = 'light'
WHERE provider IN ('nanoleaf', 'zigbee');

ALTER TABLE integration_connection
    ADD CONSTRAINT integration_connection_device_class_check
    CHECK (device_class IN ('light', 'switch', 'sensor', 'other'));
