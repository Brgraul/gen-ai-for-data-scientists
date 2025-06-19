# Battery Grid Service Compensation Calculator

A Python library that calculates **how much money a battery owner loses** when the electricity grid operator asks them to change their planned charging/discharging schedule. It figures out the **exact compensation amount** the battery owner should charge the grid operator for providing this service, ensuring they don't lose money by helping stabilize the grid.

## Installation

**Prerequisites**: Python 3.8+ is required.

1. **Clone the repository** (if not already done):
   ```bash
   git clone <repository-url>
   cd energy_flexibility
   ```

2. **Install the package in development mode**:
   ```bash
   pip install -e .
   ```
   
   This command will:
   - Install all required dependencies (pandas, numpy, scipy, openpyxl)
   - Install the `energy_flexibility` package in development mode
   - Make the package importable from anywhere in your Python environment

**Note**: The development installation (`pip install -e .`) is **required** for the package imports to work correctly. Simply installing the dependencies is not sufficient.

### Alternative: Install with optional development dependencies
```bash
pip install -e ".[dev]"
```

This includes additional tools for testing and development (pytest, black, flake8, mypy).

## Quick Start

```python
from energy_flexibility import FlexibilityCalculator, Config

# Configure your system
config = Config(
    delivery_date="2023-04-30",
    prices_file="data/prices.xlsx",
    schedule_file="data/fahrplan.xls",
    discharge_power=15.0,  # MW
    charge_power=15.0,     # MW
    efficiency=0.9
)****

# Run analysis
calculator = FlexibilityCalculator(config)
results = calculator.calculate()
```


## What It Does

**Problem**: When grid operators ask battery owners to change their planned charging/discharging schedules to help stabilize the grid, the battery owners lose money from their original profitable trading strategy. Without proper cost calculation, battery operators would essentially be **giving away expensive grid services for free** instead of running a profitable business.

**Solution**: This library calculates the exact compensation amount battery owners should charge by:
- Determining what the battery would have earned with its original optimal schedule
- Calculating what it actually earns with the grid operator's requested schedule  
- Computing the difference as the fair compensation amount
- Using sophisticated financial models (including Black-Scholes option pricing) to ensure accurate valuation
- Generating TSO-compliant reports for regulatory submission

## Core Features

- **Economic Optimization**: Find optimal charge/discharge schedules to maximize revenue
- **Option Pricing**: Calculate flexibility service values using financial models
- **Market Analysis**: Forecast intraday prices from day-ahead data
- **TSO Reporting**: Generate regulatory-compliant Excel reports
- **Sample Data**: Built-in realistic test data generation

## Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `discharge_power` | 15.0 MW | Maximum discharge power |
| `charge_power` | 15.0 MW | Maximum charge power |
| `efficiency` | 0.9 | Round-trip efficiency |
| `network_charges` | 1.5 €/MWh | Network charges |
| `max_discharge_hours` | 3.0 hours | Maximum full load hours |

## Data Requirements

**Required Input Files:**
1. **Price Data** (Excel): Day-ahead and intraday prices with 90+ days history
2. **Schedule File** (Excel): Operational plan with 15-minute intervals

**Generate Sample Data:**
```python
python energy_flexibility/generate_sample_data.py
```

## Advanced Usage

```python
# Access individual components
market_data = calculator.load_market_data()
boundary_prices = calculator.find_boundary_prices()
production_costs = calculator.calculate_production_costs(market_data, boundary_prices)

# Test different scenarios
for efficiency in [0.85, 0.90, 0.95]:
    # Run analysis with different parameters
    pass
```

## Architecture

```
energy_flexibility/
├── calculator.py         # Main facade
├── optimization.py       # Economic algorithms  
├── market_analysis.py    # Price forecasting
├── cost_calculation.py   # Financial models
├── reporting.py          # TSO compliance
├── data_loader.py        # Data processing
├── config.py            # Configuration
└── tests/               # Unit tests
```

## Output

- **Economic metrics**: Boundary prices, option values, production costs
- **TSO reports**: Excel files with regulatory compliance
- **Analysis data**: Volatility patterns, forecast accuracy

## Testing

```bash
python -m pytest energy_flexibility/tests/
```

## Use Cases

- **Battery Operators**: Calculate fair compensation when providing grid services to avoid losing money
- **Grid Operators (TSOs)**: Understand the true cost of flexibility services and budget appropriately
- **Regulators**: Audit grid service compensation calculations to ensure fair market practices
- **Energy Traders**: Optimize battery operations while accounting for grid service obligations

---

*Ensuring battery operators get fairly compensated for grid services instead of giving them away for free.* 