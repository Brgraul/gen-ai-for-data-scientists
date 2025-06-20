# Battery Grid Service Compensation Calculator

A Python library that calculates **how much money a battery owner loses** when the electricity grid operator asks them to change their planned charging/discharging schedule. It figures out the **exact compensation amount** the battery owner should charge the grid operator for providing this service, ensuring they don't lose money by helping stabilize the grid.

## Installation

**Prerequisites**: Python 3.8+ is required.

1. **Navigate to the project directory**:
   ```bash
   # Make sure you're in the 02-use_case directory
   cd /path/to/your/repo/02-use_case
   ```
   
   **⚠️ Important**: All commands below must be run from the `02-use_case` directory.

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

## Verification

After installation, verify everything is working correctly:

```bash
# 1. Verify you're in the correct directory
pwd
# Should show: /path/to/your/repo/02-use_case

# 2. Test package import
python -c "from energy_flexibility import FlexibilityCalculator, Config; print('✅ Package import successful!')"

# 3. Run a quick test
python -m pytest tests/test_config.py -v

# 4. Check package structure
ls energy_flexibility/
# Should show: __init__.py and core/
```

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
)

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

**Generate Sample Data** (run from `02-use_case` directory):
```bash
python scripts/generate_sample_data.py
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

## Package Structure

```
02-use_case/
├── energy_flexibility/           # Main package directory
│   ├── __init__.py              # Package interface
│   └── core/                    # Core modules
│       ├── __init__.py          # Core package interface
│       ├── calculator.py        # Main facade
│       ├── optimization.py      # Economic algorithms  
│       ├── market_analysis.py   # Price forecasting
│       ├── cost_calculation.py  # Financial models
│       ├── reporting.py         # TSO compliance
│       ├── data_loader.py       # Data processing
│       ├── config.py           # Configuration
│       └── models.py           # Data models
├── tests/                       # Unit tests
├── examples/                    # Usage examples
├── data/                       # Sample data
├── scripts/                    # Utility scripts
├── pyproject.toml              # Package configuration
└── README.md                   # This file
```

## Output

- **Economic metrics**: Boundary prices, option values, production costs
- **TSO reports**: Excel files with regulatory compliance
- **Analysis data**: Volatility patterns, forecast accuracy

## Testing

**⚠️ Important**: Run all test commands from the `02-use_case` directory.

### Run all tests:
```bash
python -m pytest tests/
```

### Run specific test file:
```bash
python -m pytest tests/test_optimization.py -v
```

### Run with coverage:
```bash
python -m pytest tests/ --cov=energy_flexibility
```

### Run tests with detailed output:
```bash
python -m pytest tests/ -v --tb=short
```

## Development Workflow

1. **Navigate to project directory**:
   ```bash
   cd /path/to/your/repo/02-use_case
   ```

2. **Install in development mode** (if not already done):
   ```bash
   pip install -e .
   ```

3. **Run tests** to verify everything works:
   ```bash
   python -m pytest tests/
   ```

4. **Run examples**:
   ```bash
   python examples/basic_usage.py
   ```

## Use Cases

- **Battery Operators**: Calculate fair compensation when providing grid services to avoid losing money
- **Grid Operators (TSOs)**: Understand the true cost of flexibility services and budget appropriately
- **Regulators**: Audit grid service compensation calculations to ensure fair market practices
- **Energy Traders**: Optimize battery operations while accounting for grid service obligations

---

*Ensuring battery operators get fairly compensated for grid services instead of giving them away for free.* 