# Fund Liquidity Risk Monitoring System

An open-source Flask web application for monitoring fund liquidity risk. Features real-time risk warning indicators for bond funds, money market funds, and fixed income plus funds. Includes investor position and transaction queries, holder structure analysis, and redemption scenario modeling.

## Features

- **Liquidity Risk Warning Dashboard** -- multi-fund monitoring with configurable warning thresholds
- **Three Calculation Engines** -- dedicated calculators for Bond, Money Market, and Fixed Income Plus funds
- **Investor Query** -- position and transaction lookup with date, fund, and investor filtering
- **Holder Structure Analysis** -- individual / product / institutional investor breakdown
- **Redemption Scenario Modeling** -- configurable redemption ratios to stress-test fund liquidity
- **Role-Based Access Control** -- admin and regular user roles with per-fund permission grants
- **Excel Data Import** -- bulk upload of fund positions and investor data via `.xlsx` files
- **Pluggable Data Provider** -- swap between a local CSV/JSON demo source and a Wind API production source
- **SMTP Email Alerts** -- configure per-fund email notifications for warning events

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, Flask 3.0, SQLAlchemy, Flask-Login |
| Database | SQLite (default; any SQLAlchemy-supported DB via `DATABASE_URL`) |
| Frontend | Bootstrap 5, Font Awesome 6, Jinja2 templates |
| Calculation | pandas, numpy, openpyxl |
| Deployment | Gunicorn, Docker |

## Quick Start

```bash
git clone https://github.com/<your-org>/fund-risk-monitor.git
cd fund-risk-monitor

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Seed the database with demo data
python seed_data.py

# Start the development server
python run.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

**Default credentials:** `admin` / `admin123`

## Docker

```bash
# Copy and edit the environment file
cp .env.example .env

# Build and run
docker-compose up --build
```

The container runs Gunicorn on port 5000 with a non-root user. The SQLite database is persisted via the `./instance` volume mount.

## Project Structure

```
fund-risk-monitor/
├── app/
│   ├── __init__.py          # Application factory (create_app)
│   ├── config.py            # Dev / Production / Testing configs
│   ├── models.py            # ~20 SQLAlchemy models
│   ├── auth/                # Authentication blueprint (login, users, permissions)
│   ├── dashboard/           # Dashboard & cockpit overview APIs
│   ├── warning/             # Liquidity risk warning calculations
│   ├── query/               # Investor position & transaction queries
│   ├── analysis/            # Holder structure & redemption scenario analysis
│   ├── data_mgmt/           # Data import, management, and system settings
│   ├── calculators/         # Bond, Money Market, Fixed Income Plus engines
│   ├── data_provider/       # Pluggable data source abstraction
│   ├── static/              # CSS, JS, fonts, images
│   └── templates/           # Jinja2 HTML templates
├── seed_data.py             # Database seeder with demo data
├── run.py                   # Development entry point
├── requirements.txt         # Python dependencies
├── Dockerfile               # Production container image
└── docker-compose.yml       # Single-service Compose file
```

## Architecture

- **Flask Blueprint pattern** -- six blueprints (`auth`, `dashboard`, `warning`, `query`, `analysis`, `data_mgmt`) keep the codebase modular.
- **Application factory** -- `create_app()` supports `development`, `production`, and `testing` configurations.
- **DataProvider abstraction** -- Strategy pattern lets you swap data sources without touching business logic.
- **Calculation result caching** -- computed warning indicators and basic-info results are stored in the database so dashboards load instantly.
- **Permission-based fund filtering** -- non-admin users only see funds explicitly granted via `UserPermission`.

## Data Provider

The system uses a pluggable `DataProvider` interface (`app/data_provider/base.py`) to fetch bond and stock market data (maturity dates, duration, YTM, credit ratings, beta, volatility, etc.).

| Provider | Class | Use Case |
|----------|-------|----------|
| **CSV** (default) | `CsvDataProvider` | Demo and development -- reads from bundled JSON/CSV files, no external dependencies |
| **Wind** | `WindDataProvider` | Production -- connects to the Wind financial terminal API (requires a licensed Wind SDK) |

Set the provider via the `DATA_PROVIDER` environment variable:

```bash
# Demo mode (default)
export DATA_PROVIDER=csv

# Production mode (requires Wind terminal)
export DATA_PROVIDER=wind
```

If `wind` is selected but the Wind SDK is not installed, the application falls back to the CSV provider automatically.

## Configuration

Key environment variables (can also be placed in a `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_CONFIG` | `default` | Config profile: `development`, `production`, `testing` |
| `FLASK_SECRET_KEY` | (dev fallback) | Secret key for session signing -- **set in production** |
| `DATABASE_URL` | `sqlite:///risk_monitor.db` | SQLAlchemy database URI |
| `DATA_PROVIDER` | `csv` | Market data source: `csv` or `wind` |

## Screenshots

> Screenshots coming soon.

## Contributing

Contributions are welcome. To get started:

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/my-change`).
3. Write tests where applicable (`pytest`).
4. Open a pull request against `main`.

Please keep pull requests focused on a single change and include a clear description.

## License

This project is released under the [MIT License](LICENSE).
