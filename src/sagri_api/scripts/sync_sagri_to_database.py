"""
SAGRI Soil Data Sync Script
Fetches soil nutrient data from SAGRI API and stores in database

Usage:
    python sync_sagri_to_database.py                    # Sync all plots
    python sync_sagri_to_database.py --test NORCAJ2338  # Test mode for single plot
    python sync_sagri_to_database.py --month Oct-2025   # Custom month
"""

import sys
import os
import time
import requests
import argparse
from datetime import datetime

# Add project root to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))  # scripts/
sagri_api_dir = os.path.dirname(script_dir)  # sagri_api/
src_dir = os.path.dirname(sagri_api_dir)  # src/
project_root = os.path.dirname(src_dir)  # coffee-producers-data-pipeline/
sys.path.append(project_root)
from src.database.connection import create_connection


class SagriDatabaseSync:
    """Sync SAGRI API data to MySQL database"""

    def __init__(self, month="Aug-2025", test_mode=False):
        self.base_url = "https://7yhb1ez8y7.execute-api.ap-south-1.amazonaws.com/S1/nutrients"
        self.month = month
        self.test_mode = test_mode
        self.connection = None
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }

    def connect_db(self):
        """Connect to database"""
        try:
            self.connection = create_connection()
            if self.connection:
                print(f"✅ Connected to database")
                return True
            else:
                print(f"❌ Database connection failed")
                return False
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False

    def get_plot_codes(self, single_plot=None):
        """Get plot codes from database or use single plot for testing"""
        if single_plot:
            return [single_plot]

        cursor = self.connection.cursor()
        cursor.execute("SELECT plot_code FROM sagri_plots ORDER BY plot_code")
        plots = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return plots

    def fetch_nutrient_data(self, plot_code):
        """Fetch nutrient data from SAGRI API"""
        params = {
            "farmland_id": plot_code,
            "month": self.month
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get('status') != 'success':
                return None, f"API returned status: {data.get('status')}"

            return data, None
        except requests.exceptions.Timeout:
            return None, "Request timeout"
        except Exception as e:
            return None, str(e)

    def insert_soil_data(self, plot_code, nutrient_type, nutrient_data):
        """Insert nutrient data into database"""
        sql = """
        INSERT INTO sagri_soil_data
        (plot_code, month, nutrient_type, min_value, max_value, mean_value, median_value, std_value, map_html)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        values = (
            plot_code,
            self.month,
            nutrient_type,
            nutrient_data['min'],
            nutrient_data['max'],
            nutrient_data['mean'],
            nutrient_data['median'],
            nutrient_data['std'],
            nutrient_data['map_html']
        )

        if self.test_mode:
            # In test mode, just show what would be inserted
            print(f"\n  📊 Would insert {nutrient_type}:")
            print(f"     Min:    {nutrient_data['min']:.6f}")
            print(f"     Max:    {nutrient_data['max']:.6f}")
            print(f"     Mean:   {nutrient_data['mean']:.6f}")
            print(f"     Median: {nutrient_data['median']:.6f}")
            print(f"     Std:    {nutrient_data['std']:.6f}")
            print(f"     Map HTML: {len(nutrient_data['map_html'])} characters")
            return True

        try:
            cursor = self.connection.cursor()
            cursor.execute(sql, values)
            cursor.close()
            return True
        except Exception as e:
            # Check if it's a duplicate entry error
            if "Duplicate entry" in str(e):
                return "duplicate"
            return False

    def process_plot(self, plot_code):
        """Process a single plot: fetch API data and insert into database"""
        print(f"\n[{self.stats['total'] + 1}] Processing {plot_code}...", end=" ")

        # Fetch data from API
        data, error = self.fetch_nutrient_data(plot_code)

        if error:
            print(f"❌ FAILED: {error}")
            self.stats['failed'] += 1
            self.stats['errors'].append({
                'plot_code': plot_code,
                'error': error
            })
            return

        if not data or 'nutrients' not in data:
            print(f"❌ FAILED: No nutrient data")
            self.stats['failed'] += 1
            return

        print(f"✅ API Success ({len(data['nutrients'])} nutrients)")

        # Insert each nutrient
        inserted = 0
        duplicates = 0

        for nutrient_type, nutrient_data in data['nutrients'].items():
            result = self.insert_soil_data(plot_code, nutrient_type, nutrient_data)

            if result is True:
                inserted += 1
            elif result == "duplicate":
                duplicates += 1

        if not self.test_mode:
            if duplicates > 0:
                print(f"   ⚠️  {duplicates} duplicate(s) skipped, {inserted} inserted")
                self.stats['skipped'] += duplicates
            else:
                print(f"   💾 Stored {inserted} nutrient measurement(s)")

        self.stats['success'] += 1

    def run_sync(self, single_plot=None):
        """Run the sync process"""
        print("="*70)
        if self.test_mode:
            print(f"🧪 TEST MODE - SAGRI DATA SYNC SIMULATION")
        else:
            print(f"📡 SAGRI DATA SYNC TO DATABASE")
        print("="*70)
        print(f"Month: {self.month}")

        if not self.connect_db():
            return

        # Get plot codes
        plots = self.get_plot_codes(single_plot)
        total_plots = len(plots)

        print(f"Plots to process: {total_plots}")
        if self.test_mode:
            print(f"⚠️  TEST MODE: No data will be inserted")
        print("="*70)

        # Process each plot
        for plot_code in plots:
            self.stats['total'] += 1
            self.process_plot(plot_code)

            # Rate limiting: 0.5s delay between requests
            if self.stats['total'] < total_plots:
                time.sleep(0.5)

        # Commit changes if not in test mode
        if not self.test_mode and self.connection:
            self.connection.commit()
            print(f"\n✅ Database changes committed")

        # Print summary
        self.print_summary()

        # Close connection
        if self.connection:
            self.connection.close()

    def print_summary(self):
        """Print sync summary statistics"""
        print("\n" + "="*70)
        print("SYNC SUMMARY")
        print("="*70)
        print(f"Total plots processed: {self.stats['total']}")
        print(f"✅ Successful: {self.stats['success']}")
        print(f"❌ Failed: {self.stats['failed']}")
        if self.stats['skipped'] > 0:
            print(f"⚠️  Duplicates skipped: {self.stats['skipped']}")

        if self.stats['errors']:
            print(f"\nErrors encountered:")
            for err in self.stats['errors'][:10]:  # Show first 10 errors
                print(f"  - {err['plot_code']}: {err['error']}")
            if len(self.stats['errors']) > 10:
                print(f"  ... and {len(self.stats['errors']) - 10} more")

        print("="*70)


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Sync SAGRI soil data to database')
    parser.add_argument('--test', type=str, help='Test mode with single plot code')
    parser.add_argument('--month', type=str, default='Aug-2025', help='Month to fetch (default: Aug-2025)')

    args = parser.parse_args()

    # Determine if test mode
    test_mode = args.test is not None
    single_plot = args.test if test_mode else None

    # Run sync
    sync = SagriDatabaseSync(month=args.month, test_mode=test_mode)
    sync.run_sync(single_plot=single_plot)


if __name__ == "__main__":
    main()
