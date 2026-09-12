# OVERLORD ML Pipeline

## Purpose
This folder trains the detection model that will eventually replace the simulated detections in `app/services/simulator.py`.

## Setup Steps
It is highly recommended to use a separate virtual environment for the ML pipeline to avoid dependency conflicts with the main application.

```bash
# From the project root, create a new venv for ML
python -m venv ml/.venv

# Activate the venv
# On Windows:
ml\.venv\Scripts\activate
# On Linux/macOS:
source ml/.venv/bin/activate

# Install requirements
pip install -r ml/requirements.txt
```

## How to run `prepare_dataset.py`
The `prepare_dataset.py` script validates image/label pairs, splits the dataset, and generates the `data.yaml` configuration.

```bash
python ml/scripts/prepare_dataset.py --source-dir ml/data/raw --output-dir ml/data/processed
```

Options:
- `--source-dir`: Path to the raw dataset containing images and YOLO-format text files.
- `--output-dir`: Path where the split dataset (train/val/test) will be saved.
- `--train`, `--val`, `--test`: Ratios for splitting the dataset (default: 0.8, 0.1, 0.1).
- `--seed`: Random seed for reproducible splits (default: 42).

## Datasets
- **C2A dataset** (https://github.com/Ragib-Amin-Nihal/C2A)
  - Primary person class source, disaster-scene human detection.
- **Disaster Response Object Detection Dataset** (https://www.kaggle.com/datasets/rupankarmajumdar/disaster-response-object-detection-dataset)
  - Fire/smoke/vehicle classes, secondary person source.
- **xView2 Challenge Dataset** (https://www.kaggle.com/datasets/tunguz/xview2-challenge-dataset-train-and-test)
  - Satellite pre/post pairs, used in `src/prescan` for unsupervised anomaly detection (not part of the object detector).

## Roadmap
- [x] 1. ML pipeline scaffolding
- [ ] 2. Dataset consolidation (C2A + rupankarmajumdar, deduplicated, unified classes)
- [ ] 3. Baseline multi-class detector training (person/fire/smoke/vehicle)
- [ ] 4. Satellite pre-scan module (xView2, unsupervised autoencoder anomaly detection)
- [ ] 5. Evaluation and error analysis
- [ ] 6. Alive-signal layer (thermal/motion — pending hardware confirmation)
- [ ] 7. Flood/scene-context module (AIDER/FloodNet — deferred)
- [ ] 8. Integration into app/ (replace simulator.py's fake detections with real model inference via a new app/services/detector_service.py)
- [ ] 9. Edge optimization / export for onboard inference
