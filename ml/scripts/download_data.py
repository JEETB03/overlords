import argparse
import subprocess
import os
import zipfile
from pathlib import Path
import sys

def download_dataset(dataset, target_dir):
    target_path = Path(target_dir)
    
    # Check idempotency
    if target_path.exists() and any(target_path.iterdir()):
        print(f"Skipping download for {dataset}: {target_path} already exists and is not empty.")
        return
        
    print(f"Downloading {dataset} to {target_path}...")
    target_path.mkdir(parents=True, exist_ok=True)
    
    try:
        download_cmd = ["kaggle", "datasets", "download", "-d", dataset, "-p", str(target_path)]
        # We don't use capture_output=True entirely so the user can see progress, but wait
        # kaggle cli can be noisy. Let's capture so we can analyze errors.
        result = subprocess.run(download_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error: kaggle CLI failed to download {dataset}.", file=sys.stderr)
            print(f"Kaggle error output:\n{result.stderr}\n{result.stdout}", file=sys.stderr)
            print("Please ensure kaggle.json is correctly configured.", file=sys.stderr)
            print("See https://github.com/Kaggle/kaggle-api for setup instructions.", file=sys.stderr)
            if not any(target_path.iterdir()):
                target_path.rmdir()
            sys.exit(1)
        else:
            print(result.stdout)
    except FileNotFoundError:
        print("Error: 'kaggle' CLI not found.", file=sys.stderr)
        print("Please install kaggle (pip install kaggle) and configure your kaggle.json.", file=sys.stderr)
        print("See https://github.com/Kaggle/kaggle-api for setup instructions.", file=sys.stderr)
        sys.exit(1)

    # Unzip and clean up
    zip_files = list(target_path.glob("*.zip"))
    if not zip_files:
        print(f"Warning: No zip file found after downloading {dataset}.")
        return
        
    zip_path = zip_files[0]
    print(f"Extracting {zip_path}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(target_path)
        
    zip_path.unlink()
    print(f"Successfully processed {dataset}.")

def main():
    base_raw_dir = Path(__file__).resolve().parent.parent / 'data' / 'raw'
    
    datasets = [
        ("rupankarmajumdar/disaster-response-object-detection-dataset", base_raw_dir / "rupankarmajumdar"),
        ("rgbnihal/c2a-dataset", base_raw_dir / "c2a")
    ]
    
    for dataset, target_dir in datasets:
        download_dataset(dataset, target_dir)

if __name__ == "__main__":
    main()
