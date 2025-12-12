# SAGRI API Integration Documentation

## Purpose & Context

This integration connects the Producers Direct database with the SAGRI's Peru Soil Nutrient Analytics API. The system automatically fetches and stores soil nutrient data for farmland plots in Peru, which are used for monitoring coffee and sugarcane crops.

**Key Points:**

- The sync script can be run at any time to update soil data
- The script automatically loops through all plots in the `sagri_plots` table
- When new plots are added to `sagri_plots`, simply run the script again to fetch their data
- No manual intervention needed for updates - just execute the script periodically

---

## Database Tables

### 1. `sagri_plots` - Master Plot Registry

**Purpose:** Stores all farmland plot codes that we monitor through the SAGRI API.

**What it contains:**

- 269 active farmland plot codes (as of December 2025)
- Regional breakdown:
  - NORCAJ (Cajamarca): 69 plots
  - NORLAM (Lambayeque): 27 plots
  - NORPIU (Piura): 173 plots
- Timestamp tracking (created_at, updated_at)
- 🚨 IMPORTANT: Missing linkage to farmers (via `farmer_id` foreign key).

**Why it exists:**

- Maintains a single source of truth for which plots we monitor
- Allows easy addition of new plots without modifying code
- Links plots to farmers once farmer mappings are available
- The sync script reads from this table to know which plots to fetch

**Location:** Database table in `shared_data_layer` schema

---

### 2. `sagri_soil_data` - Soil Nutrient Measurements

**Purpose:** Stores all soil nutrient measurements fetched from the SAGRI API.

**What it contains:**

- Soil nutrient measurements for 3 key indicators:
  - **OC30_cog**: Organic Carbon at 30cm depth (%)
  - **OM30_cog**: Organic Matter at 30cm depth (%)
  - **pH_cog**: Soil pH level at 30cm depth
- Statistical data for each nutrient (min, max, mean, median, standard deviation)
- Interactive HTML maps showing nutrient distribution across each plot
- Month tracking (e.g., "Aug-2025", "Oct-2025")
- Timestamp of when data was fetched

**Why it exists:**

- Historical tracking of soil conditions over time
- Enables analysis of soil health trends
- Maps provide visual insight into nutrient distribution
- Data can be used for farmer recommendations and crop planning

**Key Features:**

- **Normalized structure**: One row per nutrient per plot per month
- **Duplicate prevention**: UNIQUE constraint on (plot_code, month, nutrient_type) prevents storing same data twice
- **Cascade deletion**: If a plot is removed from `sagri_plots`, all its measurements are automatically deleted
- **Full HTML storage**: Maps stored directly in database for easy access

**Location:** Database table in `shared_data_layer` schema

---

## Sync Script Flow

**File:** `src/sagri_api/scripts/sync_sagri_to_database.py`

### How It Works

1. **Initialization**

   - Script connects to the database
   - Loads the month to fetch data for (default: "Aug-2025")
   - Can be run in test mode or production mode

2. **Reading Plot Codes**

   - Queries `sagri_plots` table to get all farmland codes
   - If new plots were added to the table, they're automatically included
   - In test mode: can specify a single plot code to test

3. **API Data Fetching** (for each plot)

   - Calls SAGRI API with farmland code and month
   - Rate limiting: 0.5 second delay between requests to avoid overwhelming API
   - Handles errors gracefully (timeout, API failures, etc.)
   - Receives 3 nutrients with statistics and HTML maps

4. **Database Storage** (for each nutrient)

   - Extracts nutrient data (min, max, mean, median, std)
   - Extracts HTML map for visualization
   - Attempts to insert into `sagri_soil_data` table
   - If duplicate exists (same plot + month + nutrient), skips insertion
   - Database transaction committed after all plots processed

5. **Progress Reporting**
   - Shows real-time progress for each plot
   - Reports success/failure counts
   - Lists any errors encountered
   - Final summary statistics

### Expected Outcomes

**Successful Run:**

- All 269 plots fetched (or subset if some fail)
- 807 total records inserted (269 plots × 3 nutrients)
- If re-run for same month: All records skipped as duplicates
- Runtime: ~3-4 minutes for all plots (with rate limiting)

**Partial Success:**

- Some plots may fail (API errors, network issues)
- Script continues processing remaining plots
- Error summary provided at end
- Can re-run to retry failed plots

**Test Mode:**

- No database writes occur
- Shows exactly what would be inserted
- Useful for verifying data before production run
- Single plot testing available

---

## Usage Examples

### Test a Single Plot (No Database Changes)

```bash
python sync_sagri_to_database.py --test NORCAJ2338
```

**Purpose:** Verify script works and see data structure before running full sync

### Sync All Plots for Default Month (Aug-2025)

```bash
python sync_sagri_to_database.py
```

**Purpose:** Production run to fetch and store data for all plots

### Sync for Different Month

```bash
python sync_sagri_to_database.py --month Oct-2025
```

**Purpose:** Fetch data for a different time period

---

## Adding New Plots

To monitor additional farmland plots:

1. Insert new plot codes into `sagri_plots` table:

   ```sql
   INSERT INTO sagri_plots (plot_code, region)
   VALUES ('NORCAJ9999', 'NORCAJ');
   ```

2. Run the sync script as normal:

   ```bash
   python sync_sagri_to_database.py
   ```

3. The script automatically fetches data for all plots including the new ones

**No code changes required** - the script dynamically reads from `sagri_plots`

---

## Data Quality & Reliability

**API Availability:**

- As of December 2025: 99.6% success rate (269/270 codes working)
- Known issue: NORPIU1205 not found in Sagri's API

**Data Consistency:**

- All working plots return the same 3 nutrients consistently
- Maps are included for every successful nutrient reading
- Statistics (min, max, mean, median, std) always present

**Duplicate Handling:**

- Database UNIQUE constraint prevents duplicate entries
- Re-running script for same month is safe - duplicates automatically skipped
- No manual cleanup needed

**Month Availability:**

- **Current Database Status (December 2025):** Complete dataset for Aug-2025 across all 269 plots (807 records total)
- **API Month Limitations:** Testing revealed that the SAGRI API returns 404 errors for months other than Aug-2025 (e.g., Oct-2025, Sep-2025)
- **Implication:** The API only provides data for specific months - always test with `--test` flag before running production sync for new months
- **Recommendation:** Check with SAGRI API provider about which months have available data before attempting bulk syncs

---

## Technical Details

**API Provider:** Sagri
**API Endpoint:** `https://7yhb1ez8y7.execute-api.ap-south-1.amazonaws.com/S1/nutrients`
**API Method:** GET
**API Parameters:** farmland_id, month

**Database Connection:**

- Uses credentials from `.env` file in project root
- Connection settings in `src/database/connection.py`
- SSL certificate required for DigitalOcean MySQL connection

**Related Files:**

- `src/sagri_api/scripts/sync_sagri_to_database.py` - Main sync script
- `src/sagri_api/scripts/test_fetch_soil_nutrients.py` - Manual single-plot fetch tool
- `src/sagri_api/scripts/test_api_availability.py` - API testing utility
- `src/sagri_api/documentation/sagri_codes.csv` - List of 269 working farmland codes
- `src/sagri_api/documentation/api_documentation.pdf` - Full API documentation from SAGRI

---

## Maintenance & Updates

**Monthly Data Collection:**

- Run script monthly to collect ongoing soil measurements
- Each month creates new records (not updates) for trend analysis
- Historical data preserved for longitudinal studies

**Database Backups:**

- DigitalOcean automatic backups enabled
- Point-in-time recovery available
- HTML maps included in backups (stored in database)

**Monitoring:**

- Script provides detailed error reporting
- Failed plots listed in summary for follow-up
- Test mode available for validation before production runs

---

## Future Enhancements

**Potential Additions:**

- Farmer ID mapping once data available
- Automated scheduling (cron job) for monthly runs
- Email notifications on completion/errors
- Dashboard for visualizing nutrient trends
- Export functionality for agronomist reports

---
