-- ═══════════════════════════════════════════════════════════════════════════
-- All 32 charge codes observed across the 25 rent rolls, with the category
-- that gives each one meaning.
--
-- Note that base_rent spans five codes. Residential uses RENT, affordable
-- adds RENTAFF, and commercial uses RENTRETL / RNTPROF and has no RENT code
-- at all. Only AMENITY appears in every property type.
--
-- An unmapped code is a load-time error, not a silent 'other'.
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO charge_code (charge_code, description, category) VALUES
    -- base rent, by property type
    ('RENT',     'Base rent (residential)',              'base_rent'),
    ('RENTAFF',  'Base rent (affordable)',               'base_rent'),
    ('RENTHAP',  'Housing assistance payment portion',   'base_rent'),
    ('RENTRETL', 'Base rent (retail)',                   'base_rent'),
    ('RNTPROF',  'Base rent (professional suite)',       'base_rent'),

    -- subsidy / credits
    ('SUBSIDY',  'Housing subsidy',                      'subsidy'),
    ('SEC8CRD',  'Section 8 credit',                     'subsidy'),

    -- concessions (negative amounts)
    ('CONRENT',  'Rent concession',                      'concession'),
    ('CONAMEN',  'Amenity concession',                   'concession'),
    ('CONEMP',   'Employee concession',                  'concession'),
    ('CONGAR',   'Garage concession',                    'concession'),
    ('CONPARK',  'Parking concession',                   'concession'),
    ('CONPETM',  'Pet rent concession',                  'concession'),
    ('CONSTOR',  'Storage concession',                   'concession'),

    -- amenity / ancillary income
    ('PARKING',  'Parking',                              'amenity'),
    ('GARAGE',   'Garage',                               'amenity'),
    ('STORAGE',  'Storage',                              'amenity'),
    ('AMENITY',  'Amenity fee',                          'amenity'),
    ('BIKE',     'Bike storage',                         'amenity'),
    ('W/D',      'Washer/dryer',                         'amenity'),

    -- utility recovery
    ('TRASH',    'Trash',                                'utility'),
    ('WATER',    'Water',                                'utility'),
    ('UTILCOM',  'Utilities (commercial)',               'utility'),
    ('HOMEPCKG', 'Home package service',                 'utility'),

    -- fees
    ('PETFEE',   'Pet fee',                              'fee'),
    ('PETFEEM',  'Pet rent (monthly)',                   'fee'),
    ('SDFEE',    'Security deposit fee',                 'fee'),
    ('SALESTX',  'Sales tax',                            'fee'),
    ('MTM',      'Month-to-month premium',               'fee'),

    -- commercial recoveries: revenue, but NOT rent. Including these in
    -- rent-per-square-foot would overstate it.
    ('CAMEST',   'CAM estimate',                         'recovery'),
    ('CAMINSR',  'CAM insurance',                        'recovery'),
    ('RETXEST',  'Real estate tax estimate',             'recovery');