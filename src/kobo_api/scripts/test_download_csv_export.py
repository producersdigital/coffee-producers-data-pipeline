"""
Download Kobo form submissions as CSV using synchronous export URLs
Requires a named export to be set up first through the Kobo UI
"""

import requests
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
project_root = Path(__file__).parent.parent.parent.parent
load_dotenv(os.path.join(project_root, '.env'), override=True)


class KoboCSVExporter:
    """Client for downloading CSV exports from Kobo"""

    def __init__(self, server_url=None, api_token=None):
        self.server_url = server_url or os.getenv('KOBO_SERVER_URL', 'https://eu.kobotoolbox.org')
        self.api_token = api_token or os.getenv('KOBO_API_TOKEN')

        if not self.api_token:
            raise ValueError("KOBO_API_TOKEN not found in environment variables")

        self.headers = {
            'Authorization': f'Token {self.api_token}'
        }

        print(f"Initialized Kobo CSV Exporter for: {self.server_url}")

    def list_export_settings(self, asset_uid):
        """
        List all named export settings for a form

        Args:
            asset_uid: Form UID

        Returns:
            List of export settings
        """
        url = f"{self.server_url}/api/v2/assets/{asset_uid}/export-settings/"

        print(f"\nFetching export settings from: {url}")
        response = requests.get(url, headers=self.headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])

            print(f"✓ Found {len(results)} export settings")

            if results:
                print("\nAvailable exports:")
                for i, export in enumerate(results, 1):
                    name = export.get('name', 'Unnamed')
                    uid = export.get('uid', 'N/A')
                    csv_url = export.get('data_url_csv', 'N/A')
                    xlsx_url = export.get('data_url_xlsx', 'N/A')

                    print(f"\n{i}. {name} (UID: {uid})")
                    print(f"   CSV URL: {csv_url}")
                    print(f"   XLSX URL: {xlsx_url}")

            return results
        else:
            print(f"✗ Failed to fetch export settings: {response.status_code}")
            print(f"  Response: {response.text}")
            return []

    def download_csv_export(self, data_url, output_dir=None):
        """
        Download CSV from a synchronous export URL

        Args:
            data_url: The data_url_csv from export settings
            output_dir: Directory to save file

        Returns:
            Path to downloaded file
        """
        # Create output directory
        if output_dir is None:
            output_dir = project_root / 'data' / 'kobo_exports'
        else:
            output_dir = Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\nDownloading CSV from: {data_url}")
        response = requests.get(data_url, headers=self.headers, timeout=120)

        if response.status_code == 200:
            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"kobo_export_{timestamp}.csv"
            filepath = output_dir / filename

            # Save file
            with open(filepath, 'wb') as f:
                f.write(response.content)

            print(f"✓ CSV saved to: {filepath}")
            print(f"  File size: {filepath.stat().st_size / 1024 / 1024:.2f} MB")

            return filepath
        else:
            print(f"✗ Failed to download: {response.status_code}")
            print(f"  Response: {response.text}")
            return None


def main():
    """Main function"""
    print("=" * 80)
    print("KOBO CSV SYNCHRONOUS EXPORT")
    print("=" * 80)

    try:
        # Initialize exporter
        exporter = KoboCSVExporter()

        # Form UID
        asset_uid = "aH5cqApoTcJcK3MLrxKxn2"
        print(f"\nForm UID: {asset_uid}")
        print(f"Form: Visitas Asistencia Tecnica")

        # List available export settings
        exports = exporter.list_export_settings(asset_uid)

        if not exports:
            print("\n" + "=" * 80)
            print("NO NAMED EXPORTS FOUND")
            print("=" * 80)
            print("\nYou need to create a named export first:")
            print("1. Go to your form in Kobo UI")
            print("2. Navigate to DATA > Downloads tab")
            print("3. Configure export settings (check 'Include labels')")
            print("4. Click 'Save selection as...' and give it a name")
            print("5. Click 'Export' to save")
            print("\nThen run this script again.")
            return

        # Find the "Asistencia Tecnica" export
        export = None
        for exp in exports:
            if exp.get('name') == 'Asistencia Tecnica':
                export = exp
                break

        if not export:
            print("\n✗ 'Asistencia Tecnica' export not found")
            print("Available exports:")
            for exp in exports:
                print(f"  - {exp.get('name', 'Unnamed')}")
            return

        csv_url = export.get('data_url_csv')

        if not csv_url:
            print("\n✗ No CSV URL found in export settings")
            return

        print(f"\n{'=' * 80}")
        print(f"Using export: {export.get('name', 'Unnamed')}")
        print(f"{'=' * 80}")

        # Download the CSV
        filepath = exporter.download_csv_export(csv_url)

        if filepath:
            print("\n" + "=" * 80)
            print("DOWNLOAD COMPLETED SUCCESSFULLY!")
            print("=" * 80)
            print(f"\nCSV file saved to: {filepath}")
            print("\nYou can now:")
            print("1. Open the CSV in Excel/LibreOffice to view the data")
            print("2. Import this CSV into your MySQL database")
            print("3. Process it with pandas in Python")
        else:
            print("\n✗ Download failed")

    except ValueError as e:
        print(f"\n✗ Configuration error: {e}")
        print("\nPlease make sure you have set KOBO_API_TOKEN in your .env file")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
