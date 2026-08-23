import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from booking.booking_codes import book_accas, render_codes

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", nargs="+", required=True)
    parser.add_argument("--date", default="2026-08-22")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    # Load full payload
    path = Path("output/boards") / f"acca_{args.date}.json"
    if not path.exists():
        print(f"Error: {path} not found")
        sys.exit(1)

    payload = json.loads(path.read_text(encoding="utf-8"))

    # Filter accas
    filtered_accas = [a for a in payload["accas"] if a["label"] in args.labels]

    if not filtered_accas:
        print(f"No accas found matching labels: {args.labels}")
        sys.exit(1)

    # Run booking
    subset_payload = {
        "date": payload["date"],
        "n_accas": len(filtered_accas),
        "accas": filtered_accas
    }

    print(f"Booking {len(filtered_accas)} accas: {args.labels}")
    result = book_accas(subset_payload, headless=True)

    # Save output
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # Print rendered codes
    print(render_codes(result))

if __name__ == "__main__":
    main()