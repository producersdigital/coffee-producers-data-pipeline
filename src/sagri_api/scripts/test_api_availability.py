"""
Test API availability for all codes_sagri farmland IDs
Checks which farmland IDs return valid data from the TENSOR API
"""

import csv
import requests
import json
from pathlib import Path
from datetime import datetime
import time


class APIAvailabilityTester:
    """Test API data availability for farmland codes"""

    def __init__(self, month="Aug-2025"):
        self.base_url = "https://7yhb1ez8y7.execute-api.ap-south-1.amazonaws.com/S1/nutrients"
        self.month = month
        self.results = {
            'successful': [],
            'failed': [],
            'errors': []
        }

    def load_sagri_codes(self):
        """Load codes_sagri from CSV"""
        csv_path = Path(__file__).parent / "sagri_codes.csv"
        codes = []

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['codes_sagri'].strip():
                    codes.append(row['codes_sagri'].strip())

        return sorted(codes)

    def test_farmland_code(self, farmland_id):
        """
        Test if a specific farmland code returns valid data

        Returns:
            dict: Result with status, farmland_id, and details
        """
        params = {
            "farmland_id": farmland_id,
            "month": self.month
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=15)
            data = response.json()

            if data.get('status') == 'success':
                # Check if there are actual nutrients (not just empty)
                nutrients_count = len(data.get('nutrients', {}))
                return {
                    'status': 'success',
                    'farmland_id': farmland_id,
                    'nutrients_count': nutrients_count,
                    'nutrients': list(data.get('nutrients', {}).keys())
                }
            else:
                return {
                    'status': 'error',
                    'farmland_id': farmland_id,
                    'message': data.get('message', 'Unknown error'),
                    'details': data.get('details', '')
                }

        except requests.exceptions.Timeout:
            return {
                'status': 'timeout',
                'farmland_id': farmland_id,
                'message': 'Request timeout after 15 seconds'
            }
        except Exception as e:
            return {
                'status': 'exception',
                'farmland_id': farmland_id,
                'message': str(e)
            }

    def run_test(self, max_codes=None, delay=0.5):
        """
        Run API test for all codes_sagri

        Args:
            max_codes (int): Optional limit for testing (for quick tests)
            delay (float): Delay between requests in seconds to avoid rate limiting
        """
        codes = self.load_sagri_codes()

        if max_codes:
            codes = codes[:max_codes]
            print(f"Testing first {max_codes} codes only (quick test)")

        total = len(codes)

        print("="*70)
        print(f"TESTING API AVAILABILITY FOR {total} FARMLAND CODES")
        print(f"Month: {self.month}")
        print("="*70)

        for i, code in enumerate(codes, 1):
            print(f"\n[{i}/{total}] Testing {code}...", end=" ")

            result = self.test_farmland_code(code)

            if result['status'] == 'success':
                print(f"✅ SUCCESS ({result['nutrients_count']} nutrients)")
                self.results['successful'].append(result)
            elif result['status'] == 'error':
                print(f"❌ ERROR: {result['message']}")
                self.results['failed'].append(result)
            else:
                print(f"⚠️  {result['status'].upper()}: {result['message']}")
                self.results['errors'].append(result)

            # Delay to avoid rate limiting
            if i < total:
                time.sleep(delay)

        self.print_summary()
        self.save_results()

    def print_summary(self):
        """Print summary of test results"""
        total = len(self.results['successful']) + len(self.results['failed']) + len(self.results['errors'])

        print("\n" + "="*70)
        print("TEST RESULTS SUMMARY")
        print("="*70)

        print(f"\nTotal codes tested: {total}")
        print(f"✅ Successful: {len(self.results['successful'])} ({len(self.results['successful'])/total*100:.1f}%)")
        print(f"❌ Failed: {len(self.results['failed'])} ({len(self.results['failed'])/total*100:.1f}%)")
        print(f"⚠️  Errors: {len(self.results['errors'])} ({len(self.results['errors'])/total*100:.1f}%)")

        # Show nutrient breakdown for successful codes
        if self.results['successful']:
            all_nutrients = set()
            for result in self.results['successful']:
                all_nutrients.update(result['nutrients'])

            print(f"\nNutrients found across successful codes:")
            for nutrient in sorted(all_nutrients):
                count = sum(1 for r in self.results['successful'] if nutrient in r['nutrients'])
                print(f"  {nutrient}: {count} farmlands")

        # Show common error messages
        if self.results['failed']:
            error_messages = {}
            for result in self.results['failed']:
                msg = result['message']
                error_messages[msg] = error_messages.get(msg, 0) + 1

            print(f"\nCommon error messages:")
            for msg, count in sorted(error_messages.items(), key=lambda x: x[1], reverse=True):
                print(f"  [{count}x] {msg}")

        print("="*70)

    def save_results(self):
        """Save test results to JSON file"""
        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"api_availability_test_{timestamp}.json"
        filepath = output_dir / filename

        report = {
            'test_date': datetime.now().isoformat(),
            'month_tested': self.month,
            'total_tested': len(self.results['successful']) + len(self.results['failed']) + len(self.results['errors']),
            'successful_count': len(self.results['successful']),
            'failed_count': len(self.results['failed']),
            'error_count': len(self.results['errors']),
            'successful': self.results['successful'],
            'failed': self.results['failed'],
            'errors': self.results['errors']
        }

        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n📄 Full results saved to: {filepath}")

        # Also save a simple CSV of working codes
        csv_path = output_dir / f"working_codes_{timestamp}.csv"
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['farmland_id', 'nutrients_count', 'nutrients'])
            for result in self.results['successful']:
                writer.writerow([
                    result['farmland_id'],
                    result['nutrients_count'],
                    ', '.join(result['nutrients'])
                ])

        print(f"📄 Working codes CSV saved to: {csv_path}")


def main():
    """Main execution"""
    import sys

    # Check if quick test mode
    quick_test = '--quick' in sys.argv or '-q' in sys.argv
    max_codes = 20 if quick_test else None

    # Check for custom month
    month = "Aug-2025"
    if '--month' in sys.argv:
        idx = sys.argv.index('--month')
        if idx + 1 < len(sys.argv):
            month = sys.argv[idx + 1]

    tester = APIAvailabilityTester(month=month)
    tester.run_test(max_codes=max_codes, delay=0.5)


if __name__ == "__main__":
    print("\nUsage:")
    print("  python test_api_availability.py              # Test all 270 codes")
    print("  python test_api_availability.py --quick      # Test first 20 codes only")
    print("  python test_api_availability.py --month Oct-2025  # Test different month")
    print()

    main()
