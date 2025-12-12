"""
Soil Nutrient Analytics API Client
Fetches soil nutrient data from Sagri's API and saves the results
"""

import requests
import json
from datetime import datetime
import os


class SoilNutrientAPI:
    """Client for fetching soil nutrient data from Sagri's API"""

    def __init__(self):
        self.base_url = "https://7yhb1ez8y7.execute-api.ap-south-1.amazonaws.com/S1/nutrients"

    def fetch_nutrients(self, farmland_id, month):
        """
        Fetch soil nutrient statistics for a specific farmland and month

        Args:
            farmland_id (str): Unique farmland ID (e.g., 'NORCAJ2338')
            month (str): Month folder name (e.g., 'Aug-2025')

        Returns:
            dict: JSON response containing nutrient statistics and maps
        """
        params = {
            "farmland_id": farmland_id,
            "month": month
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            return None

    def save_to_json(self, data, output_dir="output"):
        """
        Save API response to a JSON file

        Args:
            data (dict): API response data
            output_dir (str): Directory to save the output file

        Returns:
            str: Path to saved file
        """
        if data is None:
            print("No data to save")
            return None

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Generate filename with timestamp
        farmland_id = data.get('farmland_id', 'unknown')
        month = data.get('month', 'unknown')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{farmland_id}_{month}_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)

        # Save to file
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"Data saved to: {filepath}")
        return filepath

    def save_maps_to_html(self, data, output_dir="output/maps"):
        """
        Extract and save HTML maps from API response

        Args:
            data (dict): API response data
            output_dir (str): Directory to save HTML map files

        Returns:
            list: Paths to saved HTML files
        """
        if data is None or 'nutrients' not in data:
            print("No nutrient data to extract maps from")
            return []

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        farmland_id = data.get('farmland_id', 'unknown')
        month = data.get('month', 'unknown')
        saved_files = []

        # Extract and save each nutrient map
        for nutrient_name, nutrient_data in data['nutrients'].items():
            if 'map_html' in nutrient_data:
                filename = f"{farmland_id}_{month}_{nutrient_name}.html"
                filepath = os.path.join(output_dir, filename)

                with open(filepath, 'w') as f:
                    f.write(nutrient_data['map_html'])

                print(f"Map saved to: {filepath}")
                saved_files.append(filepath)

        return saved_files

    def print_summary(self, data):
        """
        Print a summary of the nutrient data

        Args:
            data (dict): API response data
        """
        if data is None:
            return

        print("\n" + "="*60)
        print(f"Soil Nutrient Report")
        print("="*60)
        print(f"Farmland ID: {data.get('farmland_id')}")
        print(f"Month: {data.get('month')}")
        print(f"Status: {data.get('status')}")
        print("-"*60)

        if 'nutrients' in data:
            print("\nNutrient Statistics:")
            for nutrient_name, stats in data['nutrients'].items():
                print(f"\n  {nutrient_name}:")
                print(f"    Min:    {stats.get('min', 'N/A'):.4f}")
                print(f"    Max:    {stats.get('max', 'N/A'):.4f}")
                print(f"    Mean:   {stats.get('mean', 'N/A'):.4f}")
                print(f"    Median: {stats.get('median', 'N/A'):.4f}")
                print(f"    Std:    {stats.get('std', 'N/A'):.4f}")

        if data.get('errors'):
            print("\nErrors:")
            for nutrient, error in data['errors'].items():
                print(f"  {nutrient}: {error}")

        print("="*60 + "\n")


def main():
    """Main execution function"""

    # Initialize API client
    api = SoilNutrientAPI()

    # Example: Fetch data for farmland NORCAJ2338 in Aug-2025
    farmland_id = "NORCAJ2338"
    month = "Aug-2025"

    print(f"Fetching soil nutrient data for {farmland_id} ({month})...")

    # Fetch data from API
    data = api.fetch_nutrients(farmland_id, month)

    if data:
        # Print summary
        api.print_summary(data)

        # Save full JSON response
        json_file = api.save_to_json(data, output_dir="output")

        # Save HTML maps
        map_files = api.save_maps_to_html(data, output_dir="output/maps")

        print(f"\nSaved {len(map_files)} HTML maps")
        print(f"Total files created: {1 + len(map_files)}")
    else:
        print("Failed to fetch data from API")


if __name__ == "__main__":
    main()
