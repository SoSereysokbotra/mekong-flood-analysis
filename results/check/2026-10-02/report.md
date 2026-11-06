# Flood check: Banteay Meanchey, 2026-10-02

## NORMAL FOR THE SEASON

Flooded cropland: **1,234 km²**. The same dates in the previous 3 years had a median of **938 km²** (1.3×). Rule: 'unusual' means more than 2× the usual amount and more than 50 km². 1 of 3 methods give this verdict.

![map](map.png)

| | 2026-10-02 | 2025 | 2024 | 2023 |
| --- | --- | --- | --- | --- |
| VH threshold: flooded cropland, km² | 1,336 | 985 | 202 | 517 |
| U-Net VV only: flooded cropland, km² | 1,450 | 900 | 240 | 712 |
| U-Net VV+VH (selected): flooded cropland, km² | 1,234 | 938 | 446 | 989 |

**Flooded cropland by district** (selected model):

| District | km² | share of district's cropland |
| --- | --- | --- |
| Preah Netr Preah | 563 | 61 % |
| Phnum Srok | 290 | 46 % |
| Mongkol Borei | 168 | 24 % |
| Serei Saophoan | 93 | 43 % |
| Ou Chrov | 66 | 14 % |
| Svay Chek | 23 | 3 % |
| Thma Puok | 18 | 2 % |
| Malai | 9 | 2 % |
| Paoy Paet | 2 | 1 % |

## Read before using

- Radar passes: 2026-09-14 (before) and 2026-10-02, track 164 descending. The radar saw 100 % of the province.
- 'Flood' = water on the date that was not water on the 'before' date. Water that was already there before is not counted, so a flood that started before the 'before' date is under-counted.
- Accuracy was measured once, on the October 2020 flood: on cropland the selected model found 74 % of the flood water people could see in photos, and 89 % of what it called flood was flood. Forest and grassland numbers are not reliable. Water hidden under tall rice was not checked. See `docs/level7_report.md`.
- These passes include sentinel-1c, sentinel-1d. The models were trained and tested on Sentinel-1A/1B only. The newer satellites carry the same radar design, but this project has not measured them, so treat the numbers with extra caution.
