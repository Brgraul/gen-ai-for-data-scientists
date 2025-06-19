# Energy Flexibility Library Architecture Proposals

## Current State Analysis

The existing codebase is a monolithic script with several architectural issues:
- **Global state**: Configuration parameters scattered throughout
- **Mixed concerns**: I/O, business logic, and calculations intertwined
- **Tight coupling**: Functions depend on specific DataFrame structures
- **No abstraction layers**: Direct file operations mixed with domain logic
- **Poor testability**: Hard to unit test individual components
- **Configuration scattered**: Parameters hardcoded in multiple places

---

## Architecture Proposal 1: Layered Domain Architecture

### **Core Philosophy**: Separation by business domains with clear layered boundaries

```
energy_flexibility/
├── __init__.py
├── config/
│   ├── __init__.py
│   ├── settings.py           # Configuration management
│   └── validation.py         # Parameter validation
├── data/
│   ├── __init__.py
│   ├── loaders.py            # Data loading abstractions
│   ├── processors.py         # Data transformation utilities
│   └── exporters.py          # Export functionality
├── market/
│   ├── __init__.py
│   ├── pricing.py            # Price forecasting & analysis
│   ├── volatility.py         # Volatility calculations
│   └── spreads.py            # Market spread analysis
├── optimization/
│   ├── __init__.py
│   ├── boundary_optimizer.py # Economic boundary calculations
│   └── strategies.py         # Different optimization strategies
├── financial/
│   ├── __init__.py
│   ├── options.py            # Black-Scholes option pricing
│   └── cost_models.py        # Production cost calculations
├── flexibility/
│   ├── __init__.py
│   ├── calculator.py         # Core flexibility cost engine
│   ├── redispatch.py         # Redispatch scenario handling
│   └── asset_valuation.py    # Asset depreciation models
├── reporting/
│   ├── __init__.py
│   ├── tso_reports.py        # TSO-specific reporting
│   └── compliance.py         # Regulatory compliance tools
└── orchestrator.py           # Main pipeline orchestration
```

### **Key Classes & Usage**:

```python
from energy_flexibility import FlexibilityCalculator
from energy_flexibility.config import FlexibilityConfig

# Configuration-driven approach
config = FlexibilityConfig(
    delivery_date="2023-04-30",
    efficiency=0.9,
    discharge_power=15,
    pump_power=15,
    data_paths={
        'prices': 'input/prices.xlsx',
        'schedule': 'input/fahrplan.xls'
    }
)

# Main calculator
calculator = FlexibilityCalculator(config)
result = calculator.calculate_flexibility_costs()

# Individual components accessible
market_analyzer = calculator.market_analyzer
boundary_prices = market_analyzer.find_optimal_boundaries()
```

### **Advantages**:
- **Domain clarity**: Each module has a clear business purpose
- **Testability**: Easy to mock dependencies and test domains in isolation
- **Maintainability**: Changes in one domain don't affect others
- **Extensibility**: Easy to add new market models or cost calculation methods

### **Trade-offs**:
- **Complexity**: More files and structure to navigate
- **Over-engineering risk**: Might be overkill for simple use cases

---

## Architecture Proposal 2: Pipeline Architecture with Functional Composition

### **Core Philosophy**: Immutable data transformations through composable pipeline stages

```
energy_flexibility/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── types.py              # Type definitions & data classes
│   ├── config.py             # Configuration dataclasses
│   └── exceptions.py         # Custom exceptions
├── stages/
│   ├── __init__.py
│   ├── data_ingestion.py     # Stage 1: Data loading
│   ├── price_forecasting.py  # Stage 2: Price prediction
│   ├── boundary_analysis.py  # Stage 3: Economic boundaries
│   ├── volatility_analysis.py # Stage 4: Risk assessment
│   ├── option_pricing.py     # Stage 5: Financial modeling
│   ├── cost_calculation.py   # Stage 6: Cost computation
│   └── reporting.py          # Stage 7: Output generation
├── pipeline.py               # Pipeline builder & executor
├── transforms/
│   ├── __init__.py
│   ├── market_data.py        # Market data transformations
│   ├── time_series.py        # Time series utilities
│   └── financial.py          # Financial calculations
└── utils/
    ├── __init__.py
    ├── validation.py          # Data validation utilities
    └── io.py                  # I/O abstractions
```

### **Key Classes & Usage**:

```python
from energy_flexibility import FlexibilityPipeline
from energy_flexibility.core import FlexibilityConfig, MarketData
from energy_flexibility.stages import *

# Functional pipeline construction
pipeline = (FlexibilityPipeline()
    .add_stage(DataIngestionStage())
    .add_stage(PriceForecastingStage(lookback_days=90))
    .add_stage(BoundaryAnalysisStage())
    .add_stage(VolatilityAnalysisStage(window_days=30))
    .add_stage(OptionPricingStage())
    .add_stage(CostCalculationStage())
    .add_stage(ReportingStage(output_format='excel'))
)

# Execute with configuration
config = FlexibilityConfig(delivery_date="2023-04-30", ...)
result = pipeline.execute(config)

# Individual stage execution for testing/debugging
forecasting_stage = PriceForecastingStage()
market_data = MarketData.from_excel('prices.xlsx')
forecasted_prices = forecasting_stage.process(market_data, config)
```

### **Advantages**:
- **Composability**: Easy to reorder, skip, or replace pipeline stages
- **Immutability**: Each stage returns new data, preventing side effects
- **Debugging**: Can inspect intermediate results at any stage
- **Parallelization**: Independent stages can run in parallel
- **Testing**: Each stage is a pure function, easy to test

### **Trade-offs**:
- **Memory usage**: Creating new data objects at each stage
- **Learning curve**: Functional programming concepts may be unfamiliar

---

## Architecture Proposal 3: Plugin-Based Modular Architecture

### **Core Philosophy**: Extensible plugin system with dependency injection and strategy patterns

```
energy_flexibility/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── engine.py             # Core calculation engine
│   ├── registry.py           # Plugin registry
│   ├── interfaces.py         # Abstract base classes
│   └── context.py            # Execution context
├── plugins/
│   ├── __init__.py
│   ├── data_sources/
│   │   ├── excel_loader.py   # Excel data source plugin
│   │   ├── csv_loader.py     # CSV data source plugin
│   │   └── api_loader.py     # API data source plugin
│   ├── pricing_models/
│   │   ├── historical_spread.py  # Historical spread model
│   │   ├── ml_forecasting.py     # ML-based forecasting
│   │   └── regression_model.py   # Statistical regression
│   ├── optimization/
│   │   ├── greedy_turbine_first.py # Current greedy algorithm
│   │   ├── linear_programming.py   # LP optimization
│   │   └── genetic_algorithm.py    # GA optimization
│   ├── cost_models/
│   │   ├── black_scholes.py       # Current B-S option pricing
│   │   ├── binomial_tree.py       # Binomial option model
│   │   └── monte_carlo.py         # Monte Carlo simulation
│   └── exporters/
│       ├── excel_exporter.py      # Excel output
│       ├── json_exporter.py       # JSON API output
│       └── pdf_exporter.py        # PDF reports
├── factory.py                # Factory for creating configured instances
└── defaults.py              # Default plugin configurations
```

### **Key Classes & Usage**:

```python
from energy_flexibility import FlexibilityEngineFactory
from energy_flexibility.plugins import (
    ExcelDataSource, HistoricalSpreadModel, 
    GreedyTurbineFirstOptimizer, BlackScholesOptions
)

# Factory-based configuration
factory = FlexibilityEngineFactory()

# Register plugins (or use defaults)
factory.register_data_source('excel', ExcelDataSource)
factory.register_pricing_model('historical', HistoricalSpreadModel)
factory.register_optimizer('greedy', GreedyTurbineFirstOptimizer)
factory.register_cost_model('black_scholes', BlackScholesOptions)

# Create configured engine
engine = factory.create_engine({
    'data_source': 'excel',
    'pricing_model': 'historical',
    'optimizer': 'greedy',
    'cost_model': 'black_scholes',
    'delivery_date': '2023-04-30'
})

# Execute calculation
result = engine.calculate()

# Easy to swap implementations
engine_with_ml = factory.create_engine({
    'pricing_model': 'ml_forecasting',  # Different model
    'optimizer': 'linear_programming',  # Different optimizer
    # ... other config same
})
```

### **Advantages**:
- **Extensibility**: Easy to add new algorithms without changing core code
- **A/B Testing**: Can easily compare different models/algorithms
- **Modularity**: Each plugin is completely independent
- **Backwards compatibility**: New plugins don't break existing functionality
- **Third-party integration**: External developers can create plugins

### **Trade-offs**:
- **Complexity**: Most complex architecture with plugin management overhead
- **Performance**: Plugin abstraction may introduce slight performance overhead
- **Discovery**: Harder to discover available functionality

---

## Architecture Proposal 4: Pragmatic Minimal Refactoring

### **Core Philosophy**: Simplest possible improvement with maximum practical benefit

Sometimes the best architecture is the one that solves real problems without introducing unnecessary complexity. This approach takes the existing functions and organizes them in the minimal way needed to address immediate pain points.

```
energy_flexibility/
├── __init__.py
├── config.py                 # Single configuration class
├── data_loader.py            # All data loading functions
├── market_analysis.py        # Price forecasting & market functions  
├── optimization.py           # Boundary optimization functions
├── cost_calculation.py       # All cost-related calculations
├── reporting.py              # Export and reporting functions
└── calculator.py             # Main facade class
```

### **Key Classes & Usage**:

```python
from energy_flexibility import FlexibilityCalculator, Config

# Simple configuration object
config = Config(
    delivery_date="2023-04-30",
    prices_file="input/prices.xlsx",
    schedule_file="input/fahrplan.xls",
    discharge_power=15,
    pump_power=15,
    efficiency=0.9
)

# Single calculator class that orchestrates everything
calculator = FlexibilityCalculator(config)

# One method that does it all (like the current script)
result = calculator.calculate()

# But individual steps are accessible for testing/debugging
market_data = calculator.load_market_data()
boundary_prices = calculator.find_boundary_prices(market_data)
final_costs = calculator.calculate_costs(market_data, boundary_prices)
```

### **Implementation Strategy**:

```python
# config.py - Dead simple configuration
@dataclass
class Config:
    delivery_date: str
    prices_file: str 
    schedule_file: str
    discharge_power: float = 15
    pump_power: float = 15
    efficiency: float = 0.9
    # ... other parameters with defaults

# calculator.py - Thin facade over existing functions
class FlexibilityCalculator:
    def __init__(self, config: Config):
        self.config = config
    
    def calculate(self):
        """Main method - does everything like current script"""
        # Just calls the existing functions in order
        df = data_loader.load_and_prepare_data(self.config.prices_file)
        average_diff = market_analysis.calculate_average_diff(df, self.config.delivery_date)
        adjusted_prices = market_analysis.adjust_da_prices_for_date(df, self.config.delivery_date, average_diff)
        # ... continue with existing function calls
        return final_result
    
    # Individual methods for testing
    def load_market_data(self): 
        return data_loader.load_and_prepare_data(self.config.prices_file)
    
    def find_boundary_prices(self, market_data):
        return optimization.find_optimal_boundary_prices_turbine_first(...)
```

### **Migration Strategy**:

1. **Step 1**: Move existing functions to appropriate modules (copy-paste, minimal changes)
2. **Step 2**: Create simple Config dataclass 
3. **Step 3**: Create FlexibilityCalculator facade
4. **Step 4**: Add basic tests
5. **Step 5**: Gradually improve individual functions as needed

### **File Organization Logic**:

- **data_loader.py**: `load_and_prepare_data()`, `expand_da_time()`
- **market_analysis.py**: `calculate_average_diff()`, `adjust_da_prices_for_date()`, `calculate_standard_deviation()`
- **optimization.py**: `find_optimal_boundary_prices_turbine_first()`, `calculate_production_cost_prices()`
- **cost_calculation.py**: `calculate_option_prices()`, `calculate_production_flexibility_cost()`, `calculate_deprecation_cost()`, `aggregate_costs()`
- **reporting.py**: `values_to_tso()`

### **Advantages**:
- **Minimal disruption**: Existing functions mostly unchanged
- **Immediate testability**: Can test individual components
- **Configuration centralized**: No more scattered parameters
- **Gradual improvement**: Can enhance piece by piece
- **Low risk**: Easy to understand and validate
- **Fast implementation**: Could be done in a day

### **Trade-offs**:
- **Still tightly coupled**: Functions still depend on specific data structures
- **Limited extensibility**: Hard to swap algorithms or add new features
- **Not future-proof**: May need refactoring again as requirements grow

### **When to Choose This Approach**:
- ✅ **Proof of concept or early stage projects**
- ✅ **Small teams with limited time**
- ✅ **Legacy code that "just needs to work"**
- ✅ **When you're not sure how requirements will evolve**
- ✅ **Need to ship improvements quickly**

### **Evolution Path**:
```python
# Current monolithic script
def main():
    # 756 lines of mixed logic
    pass

# Step 1: Minimal refactoring (Proposal 4)
calculator = FlexibilityCalculator(config)
result = calculator.calculate()

# Step 2: When you need more flexibility (Proposal 2)
pipeline = FlexibilityPipeline.from_calculator(calculator)
result = pipeline.execute()

# Step 3: When you need plugins (Proposal 3)  
engine = FlexibilityEngine.from_pipeline(pipeline)
result = engine.calculate()
```

---

## Updated Recommendation: Start Small, Think Big

For most real-world scenarios, I now recommend:

1. **Start with Proposal 4 (Pragmatic)** - Get immediate benefits with minimal risk
2. **Validate the domain** - Use it for a while, understand what actually needs to change
3. **Evolve strategically** - Move to Pipeline (Proposal 2) when you need composability
4. **Scale when needed** - Add plugins (Proposal 3) only when you have multiple algorithms

### **Decision Matrix**:

| Scenario | Recommended Approach |
|----------|---------------------|
| **MVP/Prototype** | Proposal 4 (Pragmatic) |
| **Production system with known requirements** | Proposal 2 (Pipeline) |
| **Research platform with multiple models** | Proposal 3 (Plugin) |
| **Enterprise system with multiple domains** | Proposal 1 (Domain) |

**Remember**: The best architecture is the one that solves your actual problems without creating new ones. Start simple, evolve when you have real reasons to add complexity. 