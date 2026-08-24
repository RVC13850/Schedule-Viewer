# Schedule-Viewer

A static website that turns the shared Google Sheet timetable into a **live dashboard** and
**per-day schedule** views. No backend — it deploys straight to GitHub Pages.

## Pages

| Page | What it shows |
| --- | --- |
| `index.html` | Live dashboard: every person in the sheet, whether they are in class right now, **when that class ends** and how long is left, plus what is up next. |
| `day.html?day=Monday` | Full timetable grid for one weekday (Monday–Friday), with a "now" marker when you view today. |

The dashboard refreshes every 15 seconds and evaluates the current time in
`America/Chicago`, so it stays correct regardless of the viewer's timezone.

Class end times come from the **merged cells** in the spreadsheet. If a class occupies a
single 30-minute cell, nobody recorded its real length, so the card flags the end time as an
assumption instead of stating it as fact.

## Updating the data

The site reads `data/schedule.json`. Regenerate it whenever the spreadsheet changes:

```sh
python3 tools/build_data.py
```

That downloads the workbook as `.xlsx` (CSV would drop the merged cells that encode class
duration), parses every weekday tab, and rewrites `data/schedule.json`. Commit the result.

To use a local export instead of downloading:

```sh
python3 tools/build_data.py ~/Downloads/Schedule.xlsx
```

The spreadsheet must be shared as **"Anyone with the link can view"** for the download to work.

### Sheet format expected

Each weekday tab needs:

- a column of 30-minute time labels (`8:00 AM`, `8:30 AM`, …),
- a header row above the first time slot listing one person per column,
- classes written as `COURSE` on the first line and the building/room on the second,
- **merged cells** spanning however long the class runs.

Adding a person is just adding a column; adding a day is adding a tab named after the weekday.

## Local preview

ES modules and `fetch` need a real server, so don't open the files directly:

```sh
python3 -m http.server 8000
# then visit http://localhost:8000
```

## Deploying to GitHub Pages

1. Push this repo to GitHub.
2. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
3. Push to `main`. The workflow in `.github/workflows/deploy.yml` publishes the repo root.

Prefer the simpler route? Set **Source: Deploy from a branch → `main` / `(root)`** and delete
the workflow — everything is already static, and `.nojekyll` keeps Jekyll out of the way.

## Layout

```
index.html            live dashboard
day.html              single-day timetable
assets/common.js      data loading, time math, shared rendering
assets/dashboard.js   live dashboard logic
assets/day.js         day grid + mobile list
assets/styles.css     styling
data/schedule.json    generated schedule data
tools/build_data.py   spreadsheet -> schedule.json
```
