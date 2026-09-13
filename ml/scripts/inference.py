import argparse
import sys
from ultralytics import YOLO
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Test YOLO on an input image")
    parser.add_argument("image", type=str, help="Path to the input image")
    parser.add_argument("--model", type=str, help="Path to YOLO model weights (e.g., runs/detect/train-3/weights/best.pt)")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold (default: 0.25)")
    parser.add_argument("--output", type=str, default="inference_output.jpg", help="Path to save the output image")
    parser.add_argument("--show", action="store_true", help="Display the output image in a window")
    args = parser.parse_args()

    if not args.model:
        print("Error: You must explicitly specify a trained model using the --model argument.")
        print("Example: --model runs/detect/train-3/weights/best.pt")
        print("Do not use the stock yolo11n.pt unless you want generic COCO classes!")
        sys.exit(1)

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: Image '{args.image}' not found.")
        return

    print(f"Loading model: {args.model}")
    try:
        model = YOLO(args.model)
    except Exception as e:
        print(f"Failed to load model. Error: {e}")
        return

    print(f"Running inference on {args.image}...")
    results = model(args.image, conf=args.conf)
    
    # YOLO results is a list of Results objects (one per image)
    res = results[0]
    
    # Save the plotted image
    res.save(filename=args.output)
    print(f"Result saved to {args.output}")
    
    if args.show:
        res.show()

if __name__ == "__main__":
    main()
