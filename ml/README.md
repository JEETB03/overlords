# OVERLORD ML Pipeline 🚀

This repository houses the Machine Learning pipeline for the OVERLORD project. It is responsible for training the object detection models that will eventually replace the simulated detections in `app/services/simulator.py`. 

The pipeline automates the entire workflow: from downloading raw Kaggle datasets, preparing and deduplicating them into a YOLO-compatible format, to running YOLO object detection training and live inference.

---

## 🛠️ Setup & Installation

It is highly recommended to use a separate virtual environment for the ML pipeline to avoid dependency conflicts with the main application.

```bash
# 1. Create a new virtual environment from the project root
python -m venv ml/.venv

# 2. Activate the virtual environment
# On Windows:
ml\.venv\Scripts\activate
# On Linux/macOS:
source ml/.venv/bin/activate

# 3. Install the required dependencies
pip install -r ml/requirements.txt
```
> [!NOTE]
> `ultralytics` will automatically install `PyTorch` as a dependency.

---

## 🗄️ Dataset Management

We consolidate data from multiple sources into a unified **4-class taxonomy**: 
`{0: person, 1: fire, 2: smoke, 3: vehicle}`.

### Dataset Sources & Class Mapping

| Dataset | Purpose | Class Mapping (Raw ID ➡️ New ID) | Notes |
|---------|---------|---------------------------------|-------|
| **[C2A](https://github.com/Ragib-Amin-Nihal/C2A)** | Primary `person` class source for disaster-scene human detection. | `{0:0}` | Extracts only the person class. Directories named `All labels with Pose info` are ignored. |
| **[Disaster Response](https://www.kaggle.com/datasets/rupankarmajumdar/disaster-response-object-detection-dataset)** | Secondary `person` source. Primary `fire/smoke/vehicle` source. | `{0:0, 1:1, 2:2, 3:3, 4:3, 5:3}` | Maps various vehicle types (car, truck, etc.) into a single `vehicle` class (ID 3). |
| **[xView2 Challenge](https://www.kaggle.com/datasets/tunguz/xview2-challenge-dataset-train-and-test)** | Satellite pre/post disaster imagery pairs. | N/A | Used exclusively in `src/prescan` for unsupervised anomaly detection (not part of the YOLO object detector). |

### 1. Download Data
If you don't have the raw datasets locally, use the download script to fetch them into `ml/data/raw/`.

```bash
python ml/scripts/download_data.py
```

### 2. Prepare & Deduplicate
The `prepare_dataset.py` script validates image/label pairs across multiple sources, resolves filename collisions, runs **perceptual hashing deduplication** to remove visually identical images, and shuffles the unique images into a unified `train/val/test` split.

```bash
python ml/scripts/prepare_dataset.py \
  --source ml/data/raw/rupankarmajumdar '{"0":0, "1":1, "2":2, "3":3, "4":3, "5":3}' \
  --source ml/data/raw/c2a '{"0":0}' \
  --output-dir ml/data/processed
```

**Available Options:**
- `--source`: Path to a raw dataset directory and its JSON remap dictionary (can be specified multiple times).
- `--output-dir`: Path where the split dataset will be saved.
- `--train`, `--val`, `--test`: Ratios for splitting the dataset (default: `0.8`, `0.1`, `0.1`).
- `--dedup-threshold`: Threshold for perceptual hash deduplication (default: `5`).
- `--seed`: Random seed for reproducible splits (default: `42`).

*The script will automatically generate the `ml/configs/data.yaml` file required for YOLO training.*

---

## 🧠 Training & Inference

### Training the YOLO Model
Once the dataset is prepared, you can train a YOLO model using the generated configuration file. You can run this directly using the Ultralytics CLI:

```bash
# Train YOLOv11 nano model for 100 epochs
yolo detect train data=ml/configs/data.yaml model=yolo11n.pt epochs=100 imgsz=640
```

### Static Image Inference
To test the trained model (or a pre-trained base model) on a single image, use the provided inference script.

```bash
# Test with custom trained weights and a specific confidence threshold
python ml/scripts/inference.py path/to/your/image.jpg --model runs/detect/train-3/weights/best.pt --conf 0.5 --show
```

### Live Webcam Inference
To run real-time object detection on a connected webcam feed, use the `webcam_inference.py` script. It will open a live video window with bounding boxes drawn in real-time.

```bash
# Run with custom model, specific confidence, and specific camera index
python ml/scripts/webcam_inference.py --model runs/detect/train-3/weights/best.pt --conf 0.5 --camera 0
```

---

## ⚠️ Known Limitations
- **Person Detection:** Underperforms (mAP50 ~0.665) despite abundant training data. This is likely due to a domain gap from the C2A dataset's synthetic pose-overlay images.
- **Smoke Detection:** Has the least amount of training data and currently demonstrates the weakest performance (mAP50 ~0.602).

---

## 🗺️ Roadmap

- [x] **1. ML pipeline scaffolding**
- [x] **2. Dataset consolidation** (C2A + rupankarmajumdar, deduplicated, unified classes)
- [x] **3. Baseline multi-class detector training** (person/fire/smoke/vehicle) - *Completed! `runs/detect/train-3/weights/best.pt` validated at mAP50 ~0.756 (vehicle: 0.989, fire: 0.767, person: 0.665, smoke: 0.602)*
- [ ] **4. Satellite pre-scan module** (xView2, unsupervised autoencoder anomaly detection)
- [ ] **5. Evaluation and error analysis**
- [ ] **6. Alive-signal layer** (thermal/motion — pending hardware confirmation)
- [ ] **7. Flood/scene-context module** (AIDER/FloodNet — deferred)
- [ ] **8. Integration into app/** (replace simulator.py's fake detections with real model inference)
- [ ] **9. Edge optimization / export** (for onboard inference)
