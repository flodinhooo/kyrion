ALTER TABLE owner_room
    ADD COLUMN room_type VARCHAR(32) NOT NULL DEFAULT 'other';

ALTER TABLE owner_room
    ADD CONSTRAINT owner_room_type_valid CHECK (room_type IN (
        'living_room', 'office', 'study', 'bedroom', 'children_room', 'guest_room',
        'hobby_room', 'gaming_room', 'kitchen', 'dining_room', 'bathroom', 'toilet',
        'hallway', 'entrance', 'storage', 'basement', 'laundry_room', 'garage',
        'workshop', 'balcony', 'terrace', 'garden', 'other'
    ));
