import argparse
import sys
import cv2
from ultralytics import YOLO

def main():
    parser = argparse.ArgumentParser(description="Run YOLO inference on a live webcam feed.")
    parser.add_argument("--model", type=str, help="Path to the YOLO model weights (e.g., runs/detect/train-3/weights/best.pt)")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold for detections (default: 0.25)")
    parser.add_argument("--camera", type=int, default=0, help="Camera index to use (default: 0 for default webcam)")
    parser.add_argument("--width", type=int, default=640, help="Webcam capture width")
    parser.add_argument("--height", type=int, default=480, help="Webcam capture height")
    
    args = parser.parse_args()

    if not args.model:
        print("Error: You must explicitly specify a trained model using the --model argument.")
        print("Example: --model runs/detect/train-3/weights/best.pt")
        print("Do not use the stock yolo11n.pt unless you want generic COCO classes!")
        sys.exit(1)

    print(f"Loading YOLO model from: {args.model}")
    model = YOLO(args.model)

    print(f"Opening webcam (index {args.camera})...")
    cap = cv2.VideoCapture(args.camera)
    
    if not cap.isOpened():
        print(f"Error: Could not open webcam at index {args.camera}.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    
    print("Webcam started. Press 'q' in the video window to quit.")
    
    try:
        while True:
            # Read a frame from the webcam
            ret, frame = cap.read()
            if not ret:
                print("Failed to grab frame from webcam. Exiting...")
                break
                
            # Run YOLO inference on the frame
            results = model.predict(source=frame, conf=args.conf, verbose=False)
            
            # The results object contains the annotated frame (boxes, labels, etc.)
            # Plot the predictions on the frame
            annotated_frame = results[0].plot()
            
            # Display the annotated frame
            cv2.imshow("Overlord Live Webcam Inference", annotated_frame)
            
            # Break the loop if 'q' is pressed
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        # Clean up resources
        cap.release()
        cv2.destroyAllWindows()
        print("Webcam released and windows closed.")

if __name__ == "__main__":
    main()
