# Panel Cutting & Pricing Optimizer API

A stateless FastAPI backend that implements 2D panel cutting layout optimization and pricing calculation for board cutting services.

## Features

- **2D Bin-Packing Optimization**: Uses guillotine/shelf algorithm to minimize board waste
- **Flexible Pricing**: Supports both client-supplied and company-supplied boards
- **Edging Calculation**: Computes total edging requirements per panel side
- **Stateless Design**: No database, authentication, or sessions - pure computational API
- **Full Type Safety**: Pydantic v2 models with comprehensive validation

## Tech Stack

- Python 3.11
- FastAPI
- Uvicorn
- Pydantic v2
- NumPy

## Quick Start

### Prerequisites

- Python 3.11 or higher

### Installation

1. Create and activate a virtual environment:

```bash
python -m venv venv

# On Linux/Mac:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

### Running the Server

Option 1 - Using the run script:
```bash
python run.py
```

Option 2 - Using uvicorn directly:
```bash
uvicorn app.main:app --reload
```

The API will be available at:
- **API Base**: http://127.0.0.1:8000
- **Interactive Docs**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

## API Endpoints

### Health Check

```
GET /health
```

Returns server status.

**Response:**
```json
{
  "status": "ok"
}
```

### Optimize Panel Cutting

```
POST /api/optimize
```

Optimizes panel placement on boards and calculates pricing.

**Request Body:**

```json
{
  "client_supply": false,
  "client_board_qty": null,
  "board_type": "Timsales",
  "color": "White Oak",
  "panels": [
    {
      "width": 400,
      "length": 600,
      "quantity": 5,
      "edge_left": true,
      "edge_right": true,
      "edge_top": false,
      "edge_bottom": false
    }
  ]
}
```

**Parameters:**

- `client_supply` (bool): True if client brings their own boards
- `client_board_qty` (int, optional): Number of boards client supplies (required if `client_supply` is true)
- `board_type` (string, optional): "Timsales", "Comply", or "Waterproof" (required if `client_supply` is false)
- `color` (string, optional): Board color (informational)
- `panels` (array): List of panels to cut
  - `width` (int): Panel width in mm (must be > 0)
  - `length` (int): Panel length in mm (must be > 0)
  - `quantity` (int): Number of identical panels (must be >= 1)
  - `edge_left/right/top/bottom` (bool): Apply edging to each side

**Response:**

```json
{
  "input": { ... },
  "layout": {
    "boards_used": 2,
    "boards": [
      {
        "index": 0,
        "panels": [
          {
            "panel_index": 0,
            "x": 0,
            "y": 0,
            "width": 400,
            "length": 600,
            "rotation": 0
          }
        ]
      }
    ],
    "board_width": 1220,
    "board_length": 2440,
    "total_piece_area": 1200000,
    "total_board_area": 5954400,
    "total_waste_area": 4754400,
    "wastage_percent": 79.85
  },
  "edging": {
    "total_edging_meters": 6.0
  },
  "pricing": {
    "material_cost": 8400,
    "cutting_cost": 700,
    "edging_cost": 450,
    "total_cost": 9550,
    "currency": "KES"
  }
}
```

## Configuration

Default settings in `app/config.py`:

- **Board Size**: 1220mm × 2440mm
- **Board Prices** (KES):
  - Timsales: 4,200
  - Comply: 3,400
  - Waterproof: 5,100
- **Cutting Cost**: 350 KES per board
- **Edging Cost**: 75 KES per meter

## Algorithm

The optimizer uses a guillotine bin-packing algorithm with shelf packing:

1. Expand panels by quantity into individual pieces
2. Sort pieces by area (largest first)
3. For each piece:
   - Try to place in current row (with/without rotation)
   - If no fit, try new row on same board
   - If still no fit, create new board
4. Calculate waste and statistics

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app and endpoints
│   ├── config.py         # Configuration constants
│   ├── schemas.py        # Pydantic models
│   └── core/
│       ├── __init__.py
│       ├── optimizer.py  # 2D bin-packing algorithm
│       └── pricing.py    # Pricing calculation logic
├── requirements.txt
├── run.py               # Application entry point
└── README.md
```

## Error Handling

The API returns HTTP 400 errors for:
- Invalid board type
- Missing required fields based on `client_supply`
- Non-positive dimensions or quantities
- Panels too large for board size
- Insufficient client-supplied boards

All errors include clear, user-friendly messages.

## Development Notes

This is a **stateless backend** designed for:
- Pure computational tasks
- Easy horizontal scaling
- Simple integration with any frontend
- Future extensibility (database, auth, payments)

No data persistence is implemented. All computation is done in memory per request.

## Future Enhancements

This version is intentionally minimal. Future versions may add:
- Database integration for storing quotes/orders
- User authentication
- Payment processing
- Email notifications
- Order management
- Historical optimization data

## License

Proprietary
