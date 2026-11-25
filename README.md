# SHC staff calendar 2027

**Live site:** https://mrclarkeau.github.io/shc-calendar/

This site lets Sacred Heart College staff put school events and assessments into Outlook. Staff can subscribe to a ready-made calendar or build their own selection and download it as an .ics file. It was built by Mr Clarke and is not an official College website.

## How it updates

Every **Sunday at 6pm Perth time**, a GitHub Action (`.github/workflows/update.yml`) does the following:

1. Fetches the College's 14 public Google calendars (All School, School Weeks, and Events and Assessments for Years 7–12).
2. Sorts every event by type, department and year group. Types and departments come from the event's title; year groups come from the calendar it belongs to.
3. Writes `data/events.json` and `data/meta.json`, which the page reads, and rebuilds every ready-made feed in `feeds/`.
4. Commits the changes. `meta.json` changes every week, so the repository never looks inactive and GitHub won't pause the schedule.

If Google can't be reached, the last good data stays in place, and the page shows a "last check failed" notice.

**To update now:** go to the **Actions** tab, choose **Weekly calendar update**, then **Run workflow**.

## Ready-made feeds

| Feed | What's in it |
|---|---|
| `feeds/interruptions.ics` | No-class days, term dates, whole-school Masses, assemblies and services |
| `feeds/no-classes.ics` | Public holidays, pupil free days, holidays, term start and end |
| `feeds/year-7.ics` … `year-12.ics` | That year's events and assessments, plus no-class days |
| `feeds/all-assessments.ics` | Every assessment, Years 7–12 |
| `feeds/dept-*.ics` | Arts, English, Maths, Science, Humanities, RE, Languages, HPE, Technologies |
| `feeds/week-labels.ics` | "Week 3, Term 2" labels, Monday to Friday |

Outlook re-checks subscribed feeds every few hours. The weekly rebuild is the real limit on how fresh they are.

## Annual jobs

- **New school year:** change `YEAR = 2027` in `scripts/build.py`, update the title in `index.html`, then run the workflow.
- **A calendar's address changes:** update its ID in `CALS` in `scripts/build.py`.
- **An event lands in the wrong type:** adjust the matching pattern in `RULES` (first match wins) or `DEPTS`.

## Run it locally

```bash
python3 scripts/build.py          # fetch and rebuild (standard library only)
python3 -m http.server 8000       # then open http://localhost:8000
```
