import argparse
import os
import random
import shutil
from pathlib import Path
import yaml
from collections import defaultdict
import json
import imagehash
from PIL import Image

def split_and_prepare_dataset(sources, output_dir, train_ratio=0.8, val_ratio=0.1, test_ratio=0.1, seed=42, dedup_threshold=5):
    """
    Validates image/label pairs, splits them into train/val/test sets,
    copies them to the output directory, writes a data.yaml config, and
    logs a summary of the dataset.
    """
    random.seed(seed)
    output_dir = Path(output_dir)
    
    valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
    all_stems = {}
    
    print("Collecting images and labels from sources...")
    for src in sources:
        src_dir = src['dir']
        src_name = src['name']
        remap = src['remap']
        
        # Convert remap keys to integers
        remap = {int(k): int(v) for k, v in remap.items()}
        src['remap'] = remap
        
        images = [p for p in src_dir.rglob("*") if p.is_file() and p.suffix.lower() in valid_extensions]
        labels = list(src_dir.rglob("*.txt"))
        
        if src_name == 'c2a':
            labels = [lbl for lbl in labels if "All labels with Pose info" not in lbl.parts]
            
        def get_split_stem(p):
            split = 'unknown'
            for part in p.parts:
                if part in ['train', 'val', 'test']:
                    split = part
                    break
            return f"{split}_{p.stem}"
            
        image_paths_by_stem = defaultdict(list)
        for img in images:
            image_paths_by_stem[get_split_stem(img)].append(img)
            
        label_paths_by_stem = defaultdict(list)
        for lbl in labels:
            if lbl.stem != 'classes':
                label_paths_by_stem[get_split_stem(lbl)].append(lbl)
                
        colliding_stems = set()
        for stem, paths in image_paths_by_stem.items():
            if len(paths) > 1:
                colliding_stems.add(stem)
                
        for stem, paths in label_paths_by_stem.items():
            if len(paths) > 1:
                colliding_stems.add(stem)
                
        valid_stems = set(image_paths_by_stem.keys()).intersection(set(label_paths_by_stem.keys())) - colliding_stems
        print(f"Source '{src_name}': Found {len(valid_stems)} valid image-label pairs (ignored {len(colliding_stems)} intra-source collisions).")
        
        for stem in valid_stems:
            prefixed_stem = f"{src_name}_{stem}"
            all_stems[prefixed_stem] = {
                'image': image_paths_by_stem[stem][0],
                'label': label_paths_by_stem[stem][0],
                'source': src_name,
                'remap': remap
            }
            
    print(f"\nTotal valid pairs across all sources: {len(all_stems)}")
    if not all_stems:
        print("No valid pairs found. Exiting.")
        return

    print("\nRunning perceptual hashing deduplication...")
    hashes = {}
    duplicates_removed = defaultdict(int)
    unique_stems = {}
    c2a_c2a_dups = []
    
    for i, (stem, data) in enumerate(all_stems.items()):
        if i > 0 and i % 1000 == 0:
            print(f"  Hashed {i}/{len(all_stems)} images...")
            
        img_path = data['image']
        try:
            img = Image.open(img_path)
            phash = imagehash.phash(img)
        except Exception as e:
            print(f"Warning: Error hashing {img_path}: {e}")
            continue
            
        is_duplicate = False
        for existing_stem, existing_hash in hashes.items():
            if phash - existing_hash <= dedup_threshold:
                src1 = all_stems[existing_stem]['source']
                src2 = data['source']
                pair = tuple(sorted([src1, src2]))
                duplicates_removed[pair] += 1
                is_duplicate = True
                
                if src1 == 'c2a' and src2 == 'c2a':
                    c2a_c2a_dups.append((all_stems[existing_stem]['image'], data['image']))
                    
                break
                
        if not is_duplicate:
            hashes[stem] = phash
            unique_stems[stem] = data

    print(f"Deduplication complete. Retained {len(unique_stems)} unique pairs.")
    
    if c2a_c2a_dups:
        review_dir = output_dir.parent / 'dedup_review'
        review_dir.mkdir(parents=True, exist_ok=True)
        print(f"Saving {min(10, len(c2a_c2a_dups))} c2a-vs-c2a duplicate pairs for review to {review_dir}...")
        for idx, (kept, dropped) in enumerate(c2a_c2a_dups[:10]):
            shutil.copy(kept, review_dir / f"kept_{idx}_a.jpg")
            shutil.copy(dropped, review_dir / f"dropped_{idx}_b.jpg")

    # Shuffle and split
    valid_stems_list = list(unique_stems.keys())
    random.shuffle(valid_stems_list)
    total = len(valid_stems_list)
    train_end = int(total * train_ratio)
    val_end = train_end + int(total * val_ratio)
    
    splits = {
        'train': valid_stems_list[:train_end],
        'val': valid_stems_list[train_end:val_end],
        'test': valid_stems_list[val_end:]
    }
    
    # Prepare output directories
    class_counts = defaultdict(int)
    class_counts_per_source = defaultdict(lambda: defaultdict(int))
    unmapped_drops = 0
    
    print("\nProcessing labels and copying files...")
    for split_name in ['train', 'val', 'test']:
        if not splits[split_name]:
            continue
            
        split_images_dir = output_dir / 'images' / split_name
        split_labels_dir = output_dir / 'labels' / split_name
        split_images_dir.mkdir(parents=True, exist_ok=True)
        split_labels_dir.mkdir(parents=True, exist_ok=True)
        
        for stem in splits[split_name]:
            data = unique_stems[stem]
            img_src = data['image']
            lbl_src = data['label']
            src_name = data['source']
            remap = data['remap']
            
            img_dst = split_images_dir / f"{stem}{img_src.suffix}"
            lbl_dst = split_labels_dir / f"{stem}.txt"
            
            shutil.copy(img_src, img_dst)
            
            remapped_lines = []
            with open(lbl_src, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if not parts:
                        continue
                    try:
                        orig_class = int(parts[0])
                    except ValueError:
                        continue
                        
                    if orig_class in remap:
                        new_class = remap[orig_class]
                        class_counts[new_class] += 1
                        class_counts_per_source[new_class][src_name] += 1
                        remapped_lines.append(f"{new_class} {' '.join(parts[1:])}\n")
                    else:
                        unmapped_drops += 1
                        
            with open(lbl_dst, 'w') as f:
                f.writelines(remapped_lines)
                
    # Write data.yaml
    classes = {0: 'person', 1: 'fire', 2: 'smoke', 3: 'vehicle'}
    
    yaml_path = Path(__file__).resolve().parent.parent / 'configs' / 'data.yaml'
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    
    yaml_data = {
        'path': str(output_dir.resolve().absolute()),
        'train': 'images/train',
        'val': 'images/val',
        'test': 'images/test',
        'names': classes
    }
    
    with open(yaml_path, 'w') as f:
        yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)
        
    print(f"\nWrote configuration to {yaml_path}")
    
    # Log summary
    print("\n--- Deduplication Summary ---")
    if duplicates_removed:
        for pair, count in duplicates_removed.items():
            print(f"  {pair[0]} vs {pair[1]}: {count} duplicates removed")
    else:
        print("  No duplicates found.")
        
    print("\n--- Dataset Summary ---")
    print(f"Train images: {len(splits['train'])}")
    print(f"Val images: {len(splits['val'])}")
    print(f"Test images: {len(splits['test'])}")
    
    if unmapped_drops > 0:
        print(f"\nWarning: Dropped {unmapped_drops} bounding boxes with class IDs not found in source remap tables.")
        
    print("\nClass instance counts (per class and source):")
    for c_id, name in classes.items():
        total_c = class_counts.get(c_id, 0)
        print(f"  {name} (ID {c_id}): {total_c} total")
        for src in sources:
            src_name = src['name']
            src_count = class_counts_per_source.get(c_id, {}).get(src_name, 0)
            print(f"    - from {src_name}: {src_count}")

def main():
    parser = argparse.ArgumentParser(description="Prepare dataset for YOLO training.")
    parser.add_argument("--source", nargs=2, action="append", metavar=('DIR', 'REMAP_JSON'), 
                        help="Source directory and JSON remap dictionary. Can be specified multiple times.")
    parser.add_argument("--output-dir", type=str, default="ml/data/processed", help="Directory to save the split dataset")
    parser.add_argument("--train", type=float, default=0.8, help="Train split ratio (default: 0.8)")
    parser.add_argument("--val", type=float, default=0.1, help="Val split ratio (default: 0.1)")
    parser.add_argument("--test", type=float, default=0.1, help="Test split ratio (default: 0.1)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--dedup-threshold", type=int, default=5, help="Perceptual hash deduplication threshold (default: 5)")
    
    args = parser.parse_args()
    
    if not args.source:
        print("No --source provided. Using default datasets...")
        base_raw_dir = Path(__file__).resolve().parent.parent / 'data' / 'raw'
        args.source = [
            [str(base_raw_dir / "rupankarmajumdar"), '{"0":0, "1":1, "2":2, "3":3, "4":3, "5":3}'],
            [str(base_raw_dir / "c2a"), '{"0":0}']
        ]
        
    sources = []
    for src_dir, remap_json in args.source:
        sources.append({
            'dir': Path(src_dir),
            'remap': json.loads(remap_json),
            'name': Path(src_dir).name
        })
    
    total_ratio = args.train + args.val + args.test
    train_ratio = args.train / total_ratio
    val_ratio = args.val / total_ratio
    test_ratio = args.test / total_ratio
    
    split_and_prepare_dataset(
        sources=sources,
        output_dir=args.output_dir,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        seed=args.seed,
        dedup_threshold=args.dedup_threshold
    )

if __name__ == "__main__":
    main()
