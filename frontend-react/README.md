# PanelPro - Cutting Optimizer

A modern, professional SaaS web application for optimizing panel cutting layouts. Built with React, TypeScript, and Tailwind CSS.

## Features

### Step 1: Panels & Board Configuration
- **Panel Input**: Add multiple panels with dimensions, quantities, and alignment options
- **Board Selection**: Choose from various core types, thicknesses, companies, and colors
- **Edge Configuration**: Select which edges need banding for each panel
- **Stock Sheets**: Define available stock sheet sizes and quantities
- **Optimization Options**: Configure kerf, labeling, material considerations, and grain direction
- **Supply Mode**: Choose between factory supply or client supply
- **Customer Details**: Capture project information and customer contact details

### Step 2: Results & Payment
- **Interactive Layout Visualization**: Canvas-based rendering of cutting layouts with zoom and pan
- **Multiple Sheet Navigation**: Browse through all optimized sheet layouts
- **Detailed Statistics**: View efficiency metrics, waste percentages, and material usage
- **Bill of Quantities**: Comprehensive breakdown of panels, materials, and services
- **Pricing Breakdown**: Detailed pricing with subtotal, tax, and total calculations
- **M-Pesa Integration**: Secure mobile payment processing with real-time status updates

## Design Features

- **Premium SaaS Aesthetic**: Clean white interface with orange (#f97316) and red (#ef4444) accents
- **3D Hover Effects**: Cards and buttons with subtle elevation changes
- **Responsive Layout**: Optimized for desktop and mobile viewing
- **Dark Navigation**: Professional dark top bar and sidebar
- **Typography**: Inter font family for modern, readable text
- **Real-time Validation**: Inline error messages and form validation
- **Toast Notifications**: User-friendly success and error messages
- **Loading States**: Visual feedback during API operations

## Tech Stack

- **React 18**: Modern React with hooks
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first styling
- **Vite**: Fast build tool and dev server
- **Lucide React**: Beautiful, consistent icons
- **Canvas API**: High-performance layout visualization

## Getting Started

### Prerequisites

- Node.js 16+ and npm
- Backend API server running (see API Configuration)

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   npm install
   ```

3. Create a `.env` file based on `.env.example`:
   ```bash
   cp .env.example .env
   ```

4. Update the `.env` file with your API base URL:
   ```
   VITE_API_BASE=http://localhost:8000
   ```

5. Start the development server:
   ```bash
   npm run dev
   ```

6. Build for production:
   ```bash
   npm run build
   ```

## API Configuration

The application expects a backend API with the following endpoints:

- `GET /health` - API health check
- `GET /api/boards/catalog` - Fetch board catalog
- `POST /api/optimize` - Submit cutting optimization request
- `POST /api/order/create` - Create payment order
- `POST /api/mpesa/initiate` - Initiate M-Pesa payment
- `GET /api/payment/status` - Check payment status
- `POST /api/notify/after-payment` - Send post-payment notification

## Project Structure

```
src/
├── api/
│   └── client.ts           # API client with typed endpoints
├── components/
│   ├── layout/             # Layout components (TopNav, Sidebar, MainLayout)
│   └── ui/                 # Reusable UI components (Card, Button, Input, etc.)
├── pages/
│   ├── StepPanels.tsx     # Step 1: Configuration page
│   └── StepResults.tsx    # Step 2: Results and payment page
├── types/
│   └── index.ts           # TypeScript type definitions
├── App.tsx                # Main application component
├── main.tsx              # Application entry point
└── index.css             # Global styles and animations
```

## Key Components

### StepPanels
Comprehensive panel configuration interface with:
- Panel input form with validation
- Board catalog selection (core, thickness, company, color)
- Edge banding configuration
- Stock sheet management
- Optimization options
- Customer details form

### StepResults
Results visualization and payment interface with:
- Canvas-based layout rendering
- Multi-sheet navigation
- Hover interactions for panel details
- Bill of quantities table
- Pricing breakdown
- M-Pesa payment integration

### MainLayout
Application shell providing:
- Top navigation with API status indicator
- Sidebar with workflow steps
- Project name display
- Responsive container

## Customization

### Colors
Primary colors are defined in Tailwind config and can be customized:
- Primary: Orange (#f97316)
- Accent: Red (#ef4444)
- Success: Green (#16a34a)

### Fonts
The app uses Inter font family. Update in `tailwind.config.js` to change fonts.

### API Base URL
Configure the API endpoint via the `VITE_API_BASE` environment variable.

## Browser Support

- Modern browsers (Chrome, Firefox, Safari, Edge)
- ES2020+ JavaScript features
- Canvas API support required for visualization

## License

This project is proprietary software for PanelPro.

## Support

For support, email support@panelpro.com or contact via WhatsApp.
