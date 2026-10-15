# HANDOVER

A plain-language account of what this project is, what it depends on, what
breaks, and what a new person would need on their first day.

Written for Sam and for whoever picks this up next. It assumes no technical
background. `docs/OPERATIONS.md` is the technical companion — this document says
*what exists and who needs to know*; that one says *which command to type*.

---

## 1. What this project is, in one paragraph

Five coffee cooperatives in Peru keep records about their farmers — who they
are, what they harvested, what was bought from them, what inspectors found on
their farms. Those records lived in hundreds of inconsistent Excel files, one
format per cooperative per year, and could not be combined or analysed. This
project cleans those files, matches every record to a single farmer identity,
and loads the result into one central database. Dashboards, EU compliance
reporting, and research partnerships all read from that one database instead of
from the spreadsheets.

---

## 2. What exists today

| Asset | What it is | Where it lives |
|---|---|---|
| **The Shared Data Layer (SDL)** | The central database. 26 tables, roughly 290,000 records. | DigitalOcean, managed MySQL |
| **The pipeline** | The Python code that cleans source files and loads them into the SDL | GitHub, public repository |
| **Field data integrations** | Automatic imports from Kobo (field visits, trainings) and two agronomy APIs | Run on demand from the pipeline |
| **EUDR compliance data** | Deforestation alerts, legal due-diligence assessments, buyer contracts | Tables in the SDL |
| **The map viewer** | A small web app letting cooperative leaders view soil and crop maps for their plots | Streamlit Community Cloud |
| **Power BI reports** | Dashboards reading directly from the SDL | Producers Direct's Power BI |

### What is in the database

Roughly, and in order of size:

- **102,786** coffee purchase records across five cooperatives and five years
- **30,105** training attendance records and **2,520** training events
- **28,895** deforestation alerts from satellite monitoring
- **49,334** harvest estimation records (producer and crop level)
- **25,640** farm inspection records
- **8,507** farmers, each with an address record
- **6,646** technical assistance visits by **54** field technicians
- **2,694** plots with soil data
- EUDR legal assessments, plot findings and **46** buyer contracts

Exact current figures are in `docs/OPERATIONS.md`, section 6.2.

---

## 3. What it depends on

Everything below must keep working, and each has an account that someone must
own.

| Service | What it does | If it stops |
|---|---|---|
| **DigitalOcean Managed MySQL** | Hosts the database | Everything stops. Dashboards go blank, no loads possible |
| **GitHub** (public repo) | Holds the code | Work stops until restored; the database is unaffected |
| **Kobo Toolbox** (EU server) | Field data collection forms | New visits and trainings cannot be imported; existing data is safe |
| **Streamlit Community Cloud** | Hosts the map viewer | Cooperative leaders lose the map viewer; nothing else affected |
| **SAGRI API** | Soil nutrient data | No new soil snapshots |
| **CrossEurAsia (CEA) API** | Soil and crop health model outputs | Maps stop rendering |
| **Power BI** | Dashboards | Reporting stops; data is safe |
| **Satelligence / Osapiens** | EUDR data, delivered as file exports by the broker | No new compliance data |

**Costs are not recorded in this repository.** Sam holds the billing
relationships. Before any handover, fill in the monthly cost and the renewal
date for each paid service above — at minimum DigitalOcean and the Power BI
licences — so a successor is not surprised by a lapsed subscription.

### Credentials

The database password, the certificate that secures the connection, and the Kobo
API token are **not** stored in the repository, by design. They live in a local
file called `.env` on the developer's machine and in the password manager.

> **This is the single biggest handover risk.** If those credentials exist only
> on one laptop and that laptop is gone, nobody can reach the database. Confirm
> they are in the organisation's password manager, not just in one person's
> hands.

---

## 4. Who knows what

| Area | Who |
|---|---|
| The whole pipeline, the database, the Power BI reports | Daniela Alvarez, BI Developer — part-time, 3 days a week |
| Project ownership, budgets, infrastructure decisions | Sam, Producers Direct UK |
| EUDR data and provider exports | The EUDR data coordinator |
| Field data and Kobo forms | The Producers Direct Peru team |
| The original database setup | An external consultant, no longer routinely involved |

**Daniela is currently the only person who can run any part of this.** That is
the honest position and the thing worth changing first — not by training a
second developer overnight, but by making sure the documents in `docs/` stay
accurate, because they are what makes a successor possible.

---

## 5. What breaks, and how you would know

Ordinary failures, in rough order of likelihood:

**A loader fails part-way through.** The connection to the database drops during
a long load. Visible immediately — the script stops with an error. Not harmful:
every loader can be re-run safely and picks up where it left off.

**A source file changes shape.** A cooperative renames a column in their
spreadsheet. The pipeline is built to stop loudly rather than load wrong numbers
— several loaders check the file's own totals and refuse to continue if they
disagree. Needs a developer to adjust the mapping.

**A number quietly stops updating.** The hardest failure to see. A script can
appear to succeed while loading nothing. This happened: one table sat with 269
empty rows for months because a file path broke when the script was moved. The
defence is checking that columns are *populated*, not just that rows exist —
documented in `docs/OPERATIONS.md`, section 6.1.

**Access is blocked by the firewall.** The database only accepts connections
from approved internet addresses. A home internet connection changes address
periodically, and then nothing connects. Looks alarming, takes two minutes to
fix.

**A Kobo export gets renamed.** The trainings importer finds its data by looking
for an export named exactly `Trainings` in the Kobo interface. If someone
renames or deletes it, the import fails for no visible reason.

---

## 6. What needs a decision

**The database must be upgraded before 30 October 2026.** MySQL 8.0 reaches end
of life on that date and DigitalOcean will require a move to version 8.4. This
is not optional and it has a deadline. The open question is who performs it —
the original consultant, or Daniela. A full backup must be taken first, and it
should happen outside working hours, because every dashboard and every loader
points at that one database.

**Owner: Sam. Still pending.**

---

## 7. What is unfinished

| Item | Status |
|---|---|
| **Plot polygons** | A unified registry of farm boundaries, needed for EUDR. In design. |
| **EUDR dashboards** | Three Power BI pages for the UK coffee buyer. Designs approved, build not started. |
| **ROTA financial data** | Microloan dataset. Waiting on a Kobo connection. |
| **Convoya plot validations** | One EUDR provider's data, on hold pending a question to the coordinator about whether two columns are swapped in their export. |
| **Open questions with the EUDR coordinator** | Eight, mostly about how to interpret the legal compliance scores. Listed in `src/eudr/eudr_README.md`. |
| **One question for the UK buyer** | Who files the Due Diligence Statement for their Peru shipments, and what they need from the cooperatives to do it. |

None of these block what already works.

---

## 8. If a new person started tomorrow

In order:

1. **Get them the credentials** — the `.env` file contents and the database
   certificate, from the password manager. Nothing works without these.
2. **Add their internet address** to the DigitalOcean database firewall.
3. **Have them read `docs/OPERATIONS.md`** end to end. It is written for exactly
   this moment: section 1 gets them connected, section 7 is every failure this
   project has actually had and how it was fixed.
4. **Have them run one small load** — the SAGRI plot script in preview mode
   writes nothing and proves the whole chain works.
5. **Give them read access** to the Kobo account, the Google Drive folders where
   cooperatives send files, and Power BI.
6. **Introduce them to** the EUDR data coordinator and the Peru field team.
   Most of what is hard here is knowing who to ask about a strange number.

A competent data engineer should be productive within a week using the
documents alone. The parts that would take longer are not technical: knowing
that "Frontera San Ignacio" and "COOPAFSI" are the same cooperative, that a
national ID is not always eight digits, that one provider writes dates
day-first and another month-first. Those are written down in `docs/OPERATIONS.md`
section 7 and in the module documents, because they are the things that would
otherwise have to be learned by breaking something.

---

## 9. Where the documentation lives

| Document | Covers |
|---|---|
| `README.md` | What the project is, its scope and results — the public front door |
| `docs/OPERATIONS.md` | How to run everything, how to verify it, every failure and its fix |
| `docs/HANDOVER.md` | This document |
| `src/eudr/eudr_README.md` | The EUDR module — two providers, the contract link, open questions |
| `src/estimations/README.md` | The harvest estimation module |
| `src/kobo_api/documentation/` | The two Kobo integrations |
| `src/sagri_api/documentation/` | The SAGRI soil integration |
| Shared Data Layer Reference Guide | Every table and field, as a spreadsheet |

---

## 10. Glossary

| Term | Meaning |
|---|---|
| **PO** | Producer Organization — a coffee cooperative |
| **SDL** | Shared Data Layer — the central database |
| **Acopio** | The cooperative's purchase of coffee from its members |
| **DNI** | Peruvian national identity number, eight digits |
| **RUC** | Peruvian tax identifier for a business or cooperative, eleven digits |
| **EUDR** | EU Deforestation Regulation — the law requiring proof that coffee sold in Europe did not come from deforested land |
| **DDS** | Due Diligence Statement — the declaration a company files to comply with EUDR |
| **Ex-socio** | A former cooperative member. Marked, never deleted — their history stays |
| **Kobo** | The mobile app field technicians use to record visits and trainings |
| **Extensionist** | A field technician who visits farms and runs trainings |
| **Pipeline** | The code that moves data from spreadsheets into the database |
| **Loader** | One script that puts one kind of data into the database |
| **Dry run** | Running a script in preview mode — it reports what it would do and changes nothing |

---

*Last updated: October 2026. Review when a service, a cost, or a person on this
page changes.*
