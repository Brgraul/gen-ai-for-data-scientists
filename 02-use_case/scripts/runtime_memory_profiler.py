#!/usr/bin/env python3
"""
Runtime Memory Profiler for FlexibilityCalculator

This script instruments the FlexibilityCalculator to measure memory usage
during actual calculations, identifying the biggest memory consumption points.
"""

import psutil
import time
import gc
import pandas as pd
import functools
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from contextlib import contextmanager
import sys

# Add the project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from energy_flexibility.core.calculator import FlexibilityCalculator
from energy_flexibility.core.config import Config


class MemoryProfiler:
    """Context manager and decorator for memory profiling."""
    
    def __init__(self):
        self.measurements: List[Dict[str, Any]] = []
        self.baseline_memory = 0
        self.start_time = 0
        
    def get_memory_mb(self) -> float:
        """Get current RSS memory usage in MB."""
        return psutil.Process().memory_info().rss / 1024 / 1024
    
    def get_memory_details(self) -> Dict[str, float]:
        """Get detailed memory information."""
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,
            'vms_mb': memory_info.vms / 1024 / 1024,
            'percent': process.memory_percent(),
        }
    
    @contextmanager
    def measure(self, operation_name: str, details: Optional[str] = None):
        """Context manager to measure memory usage of an operation."""
        gc.collect()  # Clean up before measurement
        start_memory = self.get_memory_mb()
        start_time = time.time()
        
        try:
            yield
        finally:
            gc.collect()  # Clean up after operation
            end_memory = self.get_memory_mb()
            end_time = time.time()
            
            measurement = {
                'operation': operation_name,
                'details': details or '',
                'start_memory_mb': start_memory,
                'end_memory_mb': end_memory,
                'memory_delta_mb': end_memory - start_memory,
                'duration_seconds': end_time - start_time,
                'timestamp': time.time()
            }
            
            self.measurements.append(measurement)
            print(f"{operation_name:30} | Memory: {end_memory:6.1f} MB ({measurement['memory_delta_mb']:+6.1f} MB) | Time: {measurement['duration_seconds']:6.2f}s")
    
    def memory_profile_method(self, method_name: str = None):
        """Decorator to profile memory usage of methods."""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                name = method_name or f"{func.__module__}.{func.__name__}"
                with self.measure(name):
                    return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def get_summary(self) -> pd.DataFrame:
        """Get summary of all measurements."""
        if not self.measurements:
            return pd.DataFrame()
            
        df = pd.DataFrame(self.measurements)
        return df.sort_values('memory_delta_mb', ascending=False)
    
    def print_summary(self):
        """Print a formatted summary of memory usage."""
        if not self.measurements:
            print("No measurements recorded.")
            return
            
        df = self.get_summary()
        
        print("\n" + "="*80)
        print("RUNTIME MEMORY PROFILING SUMMARY")
        print("="*80)
        
        print(f"\nTotal measurements: {len(df)}")
        print(f"Total runtime: {df['duration_seconds'].sum():.2f} seconds")
        print(f"Peak memory delta: {df['memory_delta_mb'].max():+.1f} MB")
        print(f"Total memory change: {df['memory_delta_mb'].sum():+.1f} MB")
        
        print(f"\nTOP 10 MEMORY CONSUMERS:")
        print("-" * 80)
        print(f"{'Operation':<35} {'Memory Δ (MB)':<15} {'Duration (s)':<12} {'Details':<20}")
        print("-" * 80)
        
        for _, row in df.head(10).iterrows():
            print(f"{row['operation']:<35} {row['memory_delta_mb']:+8.1f}       {row['duration_seconds']:8.2f}     {row['details']:<20}")


class InstrumentedFlexibilityCalculator(FlexibilityCalculator):
    """FlexibilityCalculator with memory profiling instrumentation."""
    
    def __init__(self, config: Config, profiler: MemoryProfiler):
        super().__init__(config)
        self.profiler = profiler
        
    def calculate(self) -> pd.DataFrame:
        """Instrumented version of the main calculation method."""
        with self.profiler.measure("TOTAL_CALCULATION", "Complete calculation"):
            print("Starting instrumented flexibility cost calculation...")
            print("="*60)
            
            with self.profiler.measure("load_market_data", f"Loading {self.config.prices_file}"):
                self._market_data = self.load_market_data()
                data_size = f"{len(self._market_data)} rows"
                
            with self.profiler.measure("price_adjustments", data_size):
                from energy_flexibility.core.market_analysis import calculate_average_diff, adjust_da_prices_for_date
                average_diff = calculate_average_diff(
                    self._market_data, 
                    self.config.delivery_date, 
                    lookback_days=self.config.price_analysis_days
                )
                self._adjusted_prices = adjust_da_prices_for_date(
                    self._market_data, 
                    self.config.delivery_date, 
                    average_diff
                )
            
            with self.profiler.measure("boundary_prices", "Optimization algorithm"):
                self._boundary_prices = self.find_boundary_prices(self._adjusted_prices)
            
            with self.profiler.measure("flexibility_costs", "Service cost calculation"):
                self._flexibility_service_costs = self.calculate_flexibility_costs(
                    self._adjusted_prices, 
                    self._boundary_prices
                )
            
            with self.profiler.measure("volatility_calculation", data_size):
                from energy_flexibility.core.market_analysis import calculate_standard_deviation
                self._standard_deviations = calculate_standard_deviation(
                    self._market_data, 
                    self.config.delivery_date, 
                    lookback_days=self.config.volatility_analysis_days
                )
            
            with self.profiler.measure("option_prices", "Black-Scholes calculation"):
                from energy_flexibility.core.cost_calculation import calculate_option_prices
                self._option_prices = calculate_option_prices(
                    market_data_df=self._adjusted_prices.copy(),
                    charging_strike_price=self._boundary_prices[1],
                    discharging_strike_price=self._boundary_prices[0],
                    historical_volatilities=self._standard_deviations,
                    day_ahead_prices=self._adjusted_prices["da_prices"],
                    expected_intraday_prices=self._adjusted_prices["adjusted_da_prices"]
                )
            
            with self.profiler.measure("load_schedule_data", f"Loading {self.config.schedule_file}"):
                self._operational_schedule_data = self._load_schedule_data()
                schedule_size = f"{len(self._operational_schedule_data)} rows"
            
            with self.profiler.measure("production_costs", schedule_size):
                from energy_flexibility.core.cost_calculation import calculate_production_flexibility_cost
                costs_production_opportunity = calculate_production_flexibility_cost(
                    self._operational_schedule_data.copy(deep=True),
                    self.config.discharge_power, 
                    self.config.charge_power,
                    self._option_prices['discharge_option_price'],
                    self._option_prices['charge_option_price'],
                    self._flexibility_service_costs[0],
                    self._flexibility_service_costs[1],
                    self._flexibility_service_costs[2],
                    self._flexibility_service_costs[3]
                )
            
            with self.profiler.measure("deprecation_costs", schedule_size):
                from energy_flexibility.core.cost_calculation import calculate_deprecation_cost
                cost_deprecation = calculate_deprecation_cost(
                    costs_production_opportunity, 
                    self.config.discharge_power, 
                    self.config.charge_power,
                    self.config.residual_value_of_battery, 
                    self.config.remaining_useful_life,
                    self.config.planned_operating_hour,
                    self._boundary_prices[1],
                    self._boundary_prices[0],
                    day_ahead_market_prices=self._adjusted_prices["da_prices"]
                )
            
            with self.profiler.measure("aggregate_costs", "Final aggregation"):
                from energy_flexibility.core.cost_calculation import aggregate_costs
                # Use absolute path for output
                script_dir = Path(__file__).parent
                project_dir = script_dir.parent
                excel_output_path = str(project_dir / "output" / "cost_values_mit_ex_ante_kostenwerte.xlsx")
                aggregated_costs = aggregate_costs(
                    cost_deprecation, 
                    excel_export_path=excel_output_path
                )
            
            with self.profiler.measure("tso_report", "Report generation"):
                self._generate_tso_report()
            
            return aggregated_costs


def create_test_config() -> Config:
    """Create a test configuration."""
    # Get absolute paths to data files
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    
    return Config(
        prices_file=str(project_dir / "data" / "preise.parquet"),
        schedule_file=str(project_dir / "data" / "fahrplan.parquet"), 
        delivery_date="2023-02-15",
        price_analysis_days=30,
        volatility_analysis_days=90,
        discharge_power=100.0,
        charge_power=80.0,
        efficiency=0.85,
        network_charges=5.0,
        max_discharge_hours=8.0,
        residual_value_of_battery=1000000.0,
        remaining_useful_life=15.0,
        planned_operating_hour=4000.0
    )


def profile_detailed_operations():
    """Profile specific memory-intensive operations in detail."""
    print("\n" + "="*60)
    print("DETAILED OPERATION PROFILING")
    print("="*60)
    
    profiler = MemoryProfiler()
    
    # Test DataFrame operations
    with profiler.measure("create_large_dataframe", "10,000 rows"):
        df = pd.DataFrame({
            'A': range(10000),
            'B': range(10000),
            'C': [f"string_{i}" for i in range(10000)]
        })
    
    with profiler.measure("dataframe_copy_deep", "10,000 rows"):
        df_copy = df.copy(deep=True)
    
    with profiler.measure("dataframe_copy_shallow", "10,000 rows"):
        df_copy_shallow = df.copy(deep=False)
    
    with profiler.measure("iterrows_operation", "10,000 iterations"):
        results = []
        for idx, row in df.iterrows():
            results.append(row['A'] + row['B'])
    
    with profiler.measure("vectorized_operation", "10,000 elements"):
        results_vectorized = df['A'] + df['B']
    
    with profiler.measure("list_comprehension", "10,000 elements"):
        results_list = [a + b for a, b in zip(df['A'], df['B'])]
    
    profiler.print_summary()


def run_full_calculation_profile():
    """Run the full calculation with memory profiling."""
    print("RUNTIME MEMORY PROFILING - FlexibilityCalculator")
    print("="*60)
    
    profiler = MemoryProfiler()
    
    # Check initial memory
    initial_memory = profiler.get_memory_mb()
    print(f"Initial memory usage: {initial_memory:.1f} MB")
    
    try:
        # Create configuration
        config = create_test_config()
        
        # Create instrumented calculator
        calculator = InstrumentedFlexibilityCalculator(config, profiler)
        
        # Run the calculation
        result = calculator.calculate()
        
        # Final memory check
        final_memory = profiler.get_memory_mb()
        print(f"\nFinal memory usage: {final_memory:.1f} MB")
        print(f"Total memory change: {final_memory - initial_memory:+.1f} MB")
        
        # Print detailed summary
        profiler.print_summary()
        
        # Save detailed results
        summary_df = profiler.get_summary()
        if not summary_df.empty:
            script_dir = Path(__file__).parent
            project_dir = script_dir.parent
            output_file = project_dir / "output" / "runtime_memory_profile.csv"
            summary_df.to_csv(output_file, index=False)
            print(f"\nDetailed results saved to: {output_file}")
        
        return result, profiler
        
    except Exception as e:
        print(f"Error during profiling: {e}")
        import traceback
        traceback.print_exc()
        profiler.print_summary()
        return None, profiler


if __name__ == "__main__":
    try:
        # Check if psutil is available
        import psutil
    except ImportError:
        print("Error: psutil is required for memory measurement")
        print("Install with: pip install psutil")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    output_dir = project_dir / "output"
    output_dir.mkdir(exist_ok=True)
    
    print("Starting Runtime Memory Profiling...")
    print("This will instrument the FlexibilityCalculator to measure memory usage during calculations.\n")
    
    # Run detailed operation profiling first
    profile_detailed_operations()
    
    # Run full calculation profiling
    result, profiler = run_full_calculation_profile()
    
    if result is not None:
        print(f"\nCalculation completed successfully!")
        print(f"Result shape: {result.shape}")
        print(f"Total memory measurements: {len(profiler.measurements)}")
    else:
        print("\nCalculation failed - see error details above") 