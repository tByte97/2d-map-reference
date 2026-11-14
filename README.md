# Aion Varve — Trend Detective (prototype)

NASA Space Apps 2026 · *Be An Earth System Trend Detective!*

Pick a variable, a season and a period. The map shows where it is changing and whether the change
is statistically significant. Click a spot for a verdict a student can read: rate, total change,
p-value, 95% range and the year the signal left the noise.

> Space Apps rule: no project work before the hackathon starts. This is reconnaissance. On the
> day, the code gets written again in a new repo.

## Run

```
python3 -m http.server 8010
```
Open http://localhost:8010. State lives in the URL, e.g. `#case=no-snow` or
`#v=T2M&s=JJA&p=1981-2025&pt=30.6,50.4`.

## What it does

- **Cases**: six questions that open the evidence and fly the globe there (MapLibre globe →
  2D map, same flight as the burn calendar). Each one is backed by the data, and one ends
  "not proven" on purpose.
- **Ask**: a plain-language question ("is the soil drying out in Greece in summer?") is matched to
  the measurements worth checking, with a reason for each, plus the season and place it mentions.
  Rule-based for now; an LLM could take its place.
- **Trend map**: Sen's slope per ~50 km cell. Stipple dots mark p < 0.05; unproven cells are
  faded. Rain and snow are shown as % of the usual level, because amounts differ hugely between
  places. The caption compares the share of significant cells with the ~5% expected by chance.
- **Verdict** for the clicked spot. Outside the case map the record is fetched live from the NASA
  POWER point API, so any place on Earth works.
- **Time of emergence**: the same test, run on the record ending in each year. Marks the year from
  which the trend stays significant.
- **Leads**: opposite trends in the current view (one variable rising in one place and falling in
  another, with a possible shared driver), and "places changing like this spot" (correlation of
  the year-to-year record).
- CSV with the series and the statistics; a link to the current case.

## Statistics

The trend is the median of all pairwise slopes (Sen). Significance comes from the Mann–Kendall
test, with the variance inflated by (1 + r₁)/(1 − r₁) when the detrended series has lag-1
autocorrelation r₁ > 0. The 95% range of the slope uses the standard Sen confidence-interval
ranks. Everything runs in the browser, so changing season or period recomputes all ~5,900 cells.

## Data

```
python3 tools/build_grid.py raw data
```
This calls NASA POWER's monthly regional API in 10° tiles, one parameter per call, for 34–64°N,
12°W–48°E, 1981–2025. Responses are cached in `raw/` (~210 MB, safe to delete once `data/`
is built). Per cell and year it stores five seasonal means as int16 (`data/*.bin`, ~11 MB):

| Variable | POWER parameter | Source | Grid |
|---|---|---|---|
| Air temperature | `T2M` | MERRA-2 | 0.5° × 0.625° |
| Precipitation | `PRECTOTCORR` | MERRA-2, gauge-corrected | 0.5° × 0.625° |
| Soil moisture (root zone) | `GWETROOT` | MERRA-2 | 0.5° × 0.625° |
| Snow depth | `SNODP` | MERRA-2 | 0.5° × 0.625° |
| Sunlight at the surface | `ALLSKY_SFC_SW_DWN` | CERES / GEOS, from 1984 | 1° |

## Known limits

- MERRA-2 is a reanalysis: a model steered by observations. Snow and soil moisture are modelled.
- POWER rounds soil moisture to 0.01, so Sen's slope is often exactly 0 where change is slow.
- No field-significance correction (FDR) yet; only the comparison with the 5% expected by chance.
- The "Ask" matching is keyword based.
