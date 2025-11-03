from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import os
import re

app = FastAPI()

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend HTML
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return FileResponse(os.path.join("..", "frontend", "index.html"))

@app.post("/boarding-sequence/")
async def generate_sequence(file: UploadFile = File(...)):
    try:
        # Read and clean CSV manually
        raw = file.file.read().decode("utf-8").strip().split("\n")
        rows = []
        for line in raw[1:]:  # skip header
            parts = [p.strip() for p in line.split(",") if p.strip()]
            if len(parts) >= 2:
                booking_id = parts[0]
                seats = parts[1:]
                rows.append({"Booking_ID": booking_id, "Seats": ",".join(seats)})

        df = pd.DataFrame(rows)
        df["Booking_ID"] = df["Booking_ID"].astype(int)

        # ✅ Seat distance calculator (Row + Seat number)
        def seat_distance(seat):
            seat = seat.strip().upper()
            if not seat:
                return 0
            letter = seat[0]
            num_match = re.findall(r"\d+", seat)
            num = int(num_match[0]) if num_match else 0
            # Weighting rows (A=front → D=back)
            row_weight = {"A": 1, "B": 2, "C": 3, "D": 4}.get(letter, 0)
            return row_weight * 100 + num

        # Calculate distance stats
        def analyze_seats(seat_str):
            seats = str(seat_str).split(",")
            distances = [seat_distance(s) for s in seats]
            max_seat = max(distances)
            total = sum(distances)
            # Determine reason text
            farthest_seat = seats[distances.index(max_seat)]
            reason = f"Farthest seat {farthest_seat} (Row weight={max_seat//100})"
            return pd.Series({"MaxSeatValue": max_seat, "TotalSeatScore": total, "Reason": reason})

        df = pd.concat([df, df["Seats"].apply(analyze_seats)], axis=1)

        # Sort by farthest seat, then booking ID
        df = df.sort_values(by=["MaxSeatValue", "Booking_ID"], ascending=[False, True]).reset_index(drop=True)
        df["Seq"] = df.index + 1

        # Return enriched data
        return df[["Seq", "Booking_ID", "Seats", "TotalSeatScore", "Reason"]].to_dict(orient="records")

    except Exception as e:
        return {"error": str(e)}
