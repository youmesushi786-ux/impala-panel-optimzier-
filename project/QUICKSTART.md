# Quick Start Guide

## Installation

1. Create and activate a virtual environment:

```bash
# On Linux/Mac
python3 -m venv venv
source venv/bin/activate

# On Windows
python -m venv venv
venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the Server

Start the server:

```bash
python run.py
```

Or using uvicorn directly:

```bash
uvicorn app.main:app --reload
```

The server will start at: **http://127.0.0.1:8000**

## Testing the API

### Interactive Documentation

Open your browser and go to:
- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

### Using cURL

Test the health endpoint:

```bash
curl http://127.0.0.1:8000/health
```

Test the optimization endpoint (company supplies boards):

```bash
curl -X POST http://127.0.0.1:8000/api/optimize \
  -H "Content-Type: application/json" \
  -d @example_request.json
```

Test with client-supplied boards:

```bash
curl -X POST http://127.0.0.1:8000/api/optimize \
  -H "Content-Type: application/json" \
  -d @example_client_supply.json
```

### Using Python requests

```python
import requests
import json

# Read example request
with open('example_request.json', 'r') as f:
    data = json.load(f)

# Make request
response = requests.post(
    'http://127.0.0.1:8000/api/optimize',
    json=data
)

# Print response
print(json.dumps(response.json(), indent=2))
```

## Example Requests

The project includes two example request files:

1. **example_request.json** - Company supplies boards
   - Uses "Timsales" board type
   - Company provides materials
   - Multiple panels with different edging requirements

2. **example_client_supply.json** - Client supplies boards
   - Client brings 3 boards
   - No material cost charged
   - Only cutting and edging costs apply

## API Endpoints

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "ok"
}
```

### POST /api/optimize

Optimize panel cutting layout and calculate pricing.

**Request Body Fields:**

- `client_supply` (boolean, required): True if client brings boards
- `client_board_qty` (integer, optional): Number of boards client supplies
  - Required when `client_supply` is true
- `board_type` (string, optional): "Timsales", "Comply", or "Waterproof"
  - Required when `client_supply` is false
- `color` (string, optional): Board color (informational)
- `panels` (array, required): List of panels to cut
  - `width` (integer, required): Panel width in mm (> 0)
  - `length` (integer, required): Panel length in mm (> 0)
  - `quantity` (integer, required): Number of identical panels (≥ 1)
  - `edge_left` (boolean, optional): Apply edging to left side
  - `edge_right` (boolean, optional): Apply edging to right side
  - `edge_top` (boolean, optional): Apply edging to top side
  - `edge_bottom` (boolean, optional): Apply edging to bottom side

**Response Fields:**

- `input`: Echo of the request
- `layout`: Cutting layout optimization
  - `boards_used`: Number of boards required
  - `boards`: Array of board layouts with panel placements
  - `board_width`, `board_length`: Board dimensions in mm
  - `total_piece_area`: Sum of all panel areas (mm²)
  - `total_board_area`: Total area of all boards (mm²)
  - `total_waste_area`: Unused board area (mm²)
  - `wastage_percent`: Percentage of waste
- `edging`: Edging summary
  - `total_edging_meters`: Total edging length in meters
- `pricing`: Cost breakdown
  - `material_cost`: Cost of boards (0 if client supplies)
  - `cutting_cost`: Cost of cutting service
  - `edging_cost`: Cost of edging service
  - `total_cost`: Total cost
  - `currency`: "KES"

## Configuration

Default settings in `app/config.py`:

- Board size: 1220mm × 2440mm
- Board prices (KES):
  - Timsales: 4,200
  - Comply: 3,400
  - Waterproof: 5,100
- Cutting cost: 350 KES per board
- Edging cost: 75 KES per meter

## Testing Logic

Run the logic test script (doesn't require dependencies):

```bash
python3 test_logic.py
```

This validates the core calculations without starting the server.

## Troubleshooting

### ModuleNotFoundError

Make sure you've activated the virtual environment and installed dependencies:

```bash
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Port Already in Use

If port 8000 is already in use, you can specify a different port:

```bash
uvicorn app.main:app --reload --port 8001
```

### Import Errors

Ensure you're running the server from the project root directory where the `app` folder is located.
