import argparse
import os
import random
import shutil
from pathlib import Path
import yaml
from collections import defaultdict

def parse_yolo_labels(label_path):
    """Parses a YOLO format label file and returns a list of class IDs."""
    class_ids = []
    if not label_path.exists():
        return class_ids
    with open(label_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if parts:
                try:
                    class_ids.append(int(parts[0]))
                except ValueError:
                    continue
    return class_ids

def split_and_prepare_dataset(source_dir, output_dir, train_ratio=0.8, val_ratio=0.1, test_ratio=0.1, seed=42):
    """
    Validates image/label pairs, splits them into train/val/test sets,
    copies them to the output directory, writes a data.yaml config, and
    logs a summary of the dataset.
    """
    random.seed(seed)
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    
    # Define valid image extensions
    valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
    
    # Find all images and labels
    images = [p for p in source_dir.rglob("*") if p.is_file() and p.suffix.lower() in valid_extensions]
    
    labels = list(source_dir.rglob("*.txt"))
    
    image_paths_by_stem = defaultdict(list)
    for img in images:
        image_paths_by_stem[img.stem].append(img)
        
    label_paths_by_stem = defaultdict(list)
    for lbl in labels:
        if lbl.stem != 'classes':
            label_paths_by_stem[lbl.stem].append(lbl)
            
    image_stems = {}
    label_stems = {}
    colliding_stems = set()
    
    for stem, paths in image_paths_by_stem.items():
        if len(paths) > 1:
            colliding_stems.add(stem)
            print(f"Warning: Collision detected for image stem '{stem}':")
            for p in paths:
                print(f"  - {p}")
        else:
            image_stems[stem] = paths[0]
            
    for stem, paths in label_paths_by_stem.items():
        if len(paths) > 1:
            colliding_stems.add(stem)
            print(f"Warning: Collision detected for label stem '{stem}':")
            for p in paths:
                print(f"  - {p}")
        else:
            label_stems[stem] = paths[0]
    
    # Find orphaned images and labels
    orphaned_images = set(image_stems.keys()) - set(label_stems.keys())
    orphaned_labels = set(label_stems.keys()) - set(image_stems.keys())
    
    if orphaned_images:
        print(f"Warning: Found {len(orphaned_images)} orphaned images (no corresponding label).")
    if orphaned_labels:
        print(f"Warning: Found {len(orphaned_labels)} orphaned labels (no corresponding image).")
        
    # Valid pairs
    valid_stems = sorted(list(set(image_stems.keys()).intersection(set(label_stems.keys()))))
    print(f"Found {len(valid_stems)} valid image-label pairs.")
    
    if not valid_stems:
        print("No valid pairs found. Exiting.")
        return
        
    # Shuffle and split
    random.shuffle(valid_stems)
    total = len(valid_stems)
    train_end = int(total * train_ratio)
    val_end = train_end + int(total * val_ratio)
    
    splits = {
        'train': valid_stems[:train_end],
        'val': valid_stems[train_end:val_end],
        'test': valid_stems[val_end:]
    }
    
    # Prepare output directories
    class_counts = defaultdict(int)
    
    for split_name in ['train', 'val', 'test']:
        if not splits[split_name]:
            continue
            
        split_images_dir = output_dir / 'images' / split_name
        split_labels_dir = output_dir / 'labels' / split_name
        split_images_dir.mkdir(parents=True, exist_ok=True)
        split_labels_dir.mkdir(parents=True, exist_ok=True)
        
        for stem in splits[split_name]:
            img_src = image_stems[stem]
            lbl_src = label_stems[stem]
            
            # Copy files
            shutil.copy(img_src, split_images_dir / img_src.name)
            shutil.copy(lbl_src, split_labels_dir / lbl_src.name)
            
            # Count classes
            classes_in_file = parse_yolo_labels(lbl_src)
            for c_id in classes_in_file:
                class_counts[c_id] += 1
                
    # Write data.yaml
    classes = {0: 'person', 1: 'fire', 2: 'smoke', 3: 'vehicle'}
    
    unexpected_classes = {c_id: count for c_id, count in class_counts.items() if c_id not in classes}
    if unexpected_classes:
        print("\n" + "!" * 50)
        print("WARNING: Unexpected class IDs found in labels!")
        print("These likely indicate a taxonomy mismatch.")
        for c_id, count in unexpected_classes.items():
            print(f"  - Class ID {c_id}: {count} instances")
        print("!" * 50 + "\n")
    yaml_path = Path(__file__).resolve().parent.parent / 'configs' / 'data.yaml'
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    
    yaml_data = {
        'path': str(output_dir.absolute()),
        'train': 'images/train',
        'val': 'images/val',
        'test': 'images/test',
        'names': classes
    }
    
    with open(yaml_path, 'w') as f:
        yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)
        
    print(f"Wrote configuration to {yaml_path}")
    
    # Log summary
    print("\n--- Dataset Summary ---")
    print(f"Train images: {len(splits['train'])}")
    print(f"Val images: {len(splits['val'])}")
    print(f"Test images: {len(splits['test'])}")
    print(f"Colliding stems skipped: {len(colliding_stems)}")
    print("\nClass instance counts:")
    for c_id, name in classes.items():
        print(f"  {name} (ID {c_id}): {class_counts.get(c_id, 0)}")

def main():
    parser = argparse.ArgumentParser(description="Prepare dataset for YOLO training.")
    parser.add_argument("--source-dir", type=str, required=True, help="Directory containing raw images and labels")
    parser.add_argument("--output-dir", type=str, required=True, help="Directory to save the split dataset")
    parser.add_argument("--train", type=float, default=0.8, help="Train split ratio (default: 0.8)")
    parser.add_argument("--val", type=float, default=0.1, help="Val split ratio (default: 0.1)")
    parser.add_argument("--test", type=float, default=0.1, help="Test split ratio (default: 0.1)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    
    args = parser.parse_args()
    
    total_ratio = args.train + args.val + args.test
    train_ratio = args.train / total_ratio
    val_ratio = args.val / total_ratio
    test_ratio = args.test / total_ratio
    
    split_and_prepare_dataset(
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        seed=args.seed
    )

if __name__ == "__main__":
    main()
