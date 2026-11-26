# Legacy load (descriptive)

The legacy-load reader of study 3 (PLAN.md section 10): requests to Missions, Personnel and Assets per run and arm. Descriptive only; it supports no confirmatory claim.

## Mean requests per scored run of the core set (95 percent interval)

| System | Direct Access | Guided Direct Access | GraphQL Adapters | Apollo Federation | Cosmo Federation |
| --- | --- | --- | --- | --- | --- |
| missions | 8.21 (7.49 to 8.95) | 2.35 (1.76 to 3.00) | 7.13 (3.40 to 14.47) | 3.47 (3.10 to 3.88) | 3.75 (3.35 to 4.19) |
| personnel | 15.80 (13.69 to 18.00) | 2.34 (1.65 to 3.14) | 4.49 (2.64 to 6.74) | 1.99 (1.37 to 2.67) | 2.05 (1.49 to 2.66) |
| assets | 7.17 (6.13 to 8.32) | 0.50 (0.35 to 0.65) | 0.91 (0.65 to 1.20) | 2.74 (1.68 to 3.87) | 3.07 (1.89 to 4.32) |
| all | 31.18 (28.30 to 34.11) | 5.18 (4.22 to 6.24) | 12.54 (7.74 to 19.99) | 8.20 (7.10 to 9.31) | 8.88 (7.73 to 10.08) |

## Ratios of the means (95 percent interval)

| System | federation/gamma | federation/beta | beta/alpha | gamma/alpha | delta/alpha | epsilon/alpha |
| --- | --- | --- | --- | --- | --- | --- |
| missions | 0.51 (0.25 to 1.03) | 1.54 (1.25 to 1.96) | 0.29 (0.22 to 0.36) | 0.87 (0.41 to 1.75) | 0.42 (0.38 to 0.48) | 0.46 (0.40 to 0.52) |
| personnel | 0.45 (0.29 to 0.73) | 0.86 (0.66 to 1.10) | 0.15 (0.11 to 0.19) | 0.28 (0.17 to 0.43) | 0.13 (0.09 to 0.16) | 0.13 (0.10 to 0.16) |
| assets | 3.17 (2.19 to 4.36) | 5.86 (3.79 to 8.43) | 0.07 (0.05 to 0.10) | 0.13 (0.08 to 0.18) | 0.38 (0.22 to 0.57) | 0.43 (0.25 to 0.64) |
| all | 0.68 (0.42 to 1.11) | 1.65 (1.35 to 2.04) | 0.17 (0.14 to 0.20) | 0.40 (0.25 to 0.63) | 0.26 (0.22 to 0.31) | 0.28 (0.24 to 0.33) |

## Block initialization load (requests before the first scored run of each stack start, countable blocks)

| System | Direct Access | Guided Direct Access | GraphQL Adapters | Apollo Federation | Cosmo Federation |
| --- | --- | --- | --- | --- | --- |
| missions | 0 | 0 | 0 (0.00 per stack start) | 12 (3.00 per stack start) | 12 (3.00 per stack start) |
| personnel | 0 | 0 | 0 (0.00 per stack start) | 52 (13.00 per stack start) | 52 (13.00 per stack start) |
| assets | 0 | 0 | 0 (0.00 per stack start) | 0 (0.00 per stack start) | 0 (0.00 per stack start) |
| stack starts | 0 | 0 | 4 | 4 | 4 |

## Total with initialization, core set (per scored run of the core set in a countable block)

The requests of the scored runs of the core set in the countable blocks, with the block initialization and the unattributed requests of those blocks, over those runs. A run of a block that is not countable is not in it (see the blocks that are not countable, below). The ambiguity set and the vendor errors are not in it; their counts follow below.

| System | Direct Access | Guided Direct Access | GraphQL Adapters | Apollo Federation | Cosmo Federation |
| --- | --- | --- | --- | --- | --- |
| missions | 8.21 (1757 requests) | 2.34 (500 requests) | 7.29 (1561 requests) | 3.55 (760 requests) | 3.84 (821 requests) |
| personnel | 15.80 (3382 requests) | 2.33 (499 requests) | 4.49 (961 requests) | 2.27 (485 requests) | 2.33 (499 requests) |
| assets | 7.17 (1534 requests) | 0.50 (106 requests) | 0.96 (205 requests) | 2.79 (597 requests) | 3.13 (669 requests) |
| core runs in countable blocks | 214 | 214 | 214 | 214 | 214 |

## Unattributed requests (outside every run window, after the first)

| System | Direct Access | Guided Direct Access | GraphQL Adapters | Apollo Federation | Cosmo Federation |
| --- | --- | --- | --- | --- | --- |
| missions | 0 | 0 | 8 | 8 | 8 |
| personnel | 0 | 0 | 10 | 10 | 10 |
| assets | 0 | 0 | 10 | 10 | 10 |

## Apart: the ambiguity set (runs in countable blocks and their requests, not in the figures or the total)

| System | Direct Access | Guided Direct Access | GraphQL Adapters | Apollo Federation | Cosmo Federation |
| --- | --- | --- | --- | --- | --- |
| missions | 63 | 10 | 10 | 11 | 13 |
| personnel | 102 | 11 | 12 | 9 | 6 |
| assets | 60 | 5 | 11 | 39 | 20 |
| runs in countable blocks | 12 | 12 | 12 | 12 | 12 |

Their raw arms' requests by kind:

| Kind | Direct Access | Guided Direct Access |
| --- | --- | --- |
| status | missions 63, personnel 102, assets 60 | missions 10, personnel 11, assets 5 |
| timeout | missions 0, personnel 0, assets 0 | missions 0, personnel 0, assets 0 |
| connected | missions 0, personnel 0, assets 0 | missions 0, personnel 0, assets 0 |
| refused | missions 0, personnel 0, assets 0 | missions 0, personnel 0, assets 0 |
| noConnection | missions 0, personnel 0, assets 0 | missions 0, personnel 0, assets 0 |
| unclassified | missions 0, personnel 0, assets 0 | missions 0, personnel 0, assets 0 |
| unplaced | 13 | 0 |

## Apart: the core runs that failed at the vendor twice (runs in countable blocks and their requests, not in the figures or the total)

| System | Direct Access | Guided Direct Access | GraphQL Adapters | Apollo Federation | Cosmo Federation |
| --- | --- | --- | --- | --- | --- |
| missions | 0 | 0 | 0 | 0 | 0 |
| personnel | 0 | 0 | 0 | 0 | 0 |
| assets | 0 | 0 | 0 | 0 | 0 |
| runs in countable blocks | 0 | 0 | 0 | 0 | 0 |

Their raw arms' requests by kind:

| Kind | Direct Access | Guided Direct Access |
| --- | --- | --- |
| status | missions 0, personnel 0, assets 0 | missions 0, personnel 0, assets 0 |
| timeout | missions 0, personnel 0, assets 0 | missions 0, personnel 0, assets 0 |
| connected | missions 0, personnel 0, assets 0 | missions 0, personnel 0, assets 0 |
| refused | missions 0, personnel 0, assets 0 | missions 0, personnel 0, assets 0 |
| noConnection | missions 0, personnel 0, assets 0 | missions 0, personnel 0, assets 0 |
| unclassified | missions 0, personnel 0, assets 0 | missions 0, personnel 0, assets 0 |
| unplaced | 0 | 0 |

## The raw arms' requests by kind, core set (vendor errors missing)

| Kind | Direct Access | Guided Direct Access |
| --- | --- | --- |
| status | missions 1757, personnel 3382, assets 1534 | missions 500, personnel 499, assets 106 |
| timeout | missions 0, personnel 0, assets 0 | missions 0, personnel 0, assets 0 |
| connected | missions 0, personnel 0, assets 0 | missions 0, personnel 0, assets 0 |
| refused | missions 0, personnel 0, assets 0 | missions 0, personnel 0, assets 0 |
| noConnection | missions 13, personnel 19, assets 14 | missions 8, personnel 36, assets 23 |
| unclassified | missions 4, personnel 8, assets 0 | missions 0, personnel 0, assets 0 |
| unplaced | 280 | 0 |

## Requests near a boundary, per block

- r1-delta: 4
- r1-epsilon: 6
- r1-gamma: 3
- r2-delta: 7
- r2-epsilon: 6
- r2-gamma: 4
- r3-delta: 5
- r3-epsilon: 6
- r3-gamma: 4
- r4-delta: 7
- r4-epsilon: 5
- r4-gamma: 4

## Blocks that are not countable

- none
