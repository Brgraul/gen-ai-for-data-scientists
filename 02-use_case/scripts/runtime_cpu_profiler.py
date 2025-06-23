#!/usr/bin/env python3
"""
Runtime CPU Profiler for FlexibilityCalculator

This script instruments the FlexibilityCalculator to measure CPU usage
and identify hot paths during actual calculations using cProfile.
"""

import cProfile
import pstats
import time
import pandas as pd
import functools
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from contextlib import contextmanager
import sys
import io

# Add the project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from energy_flexibility.core.calculator import FlexibilityCalculator
from energy_flexibility.core.config import Config


class CPUProfiler:
    """Context manager and decorator for CPU profiling using cProfile."""
    
    def __init__(self):
        self.measurements: List[Dict[str, Any]] = []
        self.profiles: Dict[str, cProfile.Profile] = {}
        self.start_time = 0
        
    @contextmanager
    def measure(self, operation_name: str, details: Optional[str] = None):
        """Context manager to measure CPU usage of an operation."""
        profiler = cProfile.Profile()
        start_time = time.time()
        
        print(f"Starting CPU profiling: {operation_name}")
        profiler.enable()
        
        try:
            yield
        finally:
            profiler.disable()
            end_time = time.time()
            duration = end_time - start_time
            
            # Store the profiler for detailed analysis
            self.profiles[operation_name] = profiler
            
            # Get quick stats
            stats = pstats.Stats(profiler)
            total_calls = stats.total_calls
            total_time = stats.total_tt
            
            measurement = {
                'operation': operation_name,
                'details': details or '',
                'duration_seconds': duration,
                'profile_total_time': total_time,
                'total_calls': total_calls,
                'calls_per_second': total_calls / duration if duration > 0 else 0,
                'timestamp': time.time()
            }
            
            self.measurements.append(measurement)
            print(f"{operation_name:30} | Duration: {duration:6.2f}s | Calls: {total_calls:8} | Profile Time: {total_time:6.2f}s")
    
    def cpu_profile_method(self, method_name: str = None):
        """Decorator to profile CPU usage of methods."""
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
        return df.sort_values('duration_seconds', ascending=False)
    
    def print_hotpaths(self, operation_name: str, top_n: int = 20):
        """Print the top CPU hotpaths for a specific operation."""
        if operation_name not in self.profiles:
            print(f"No profile data found for: {operation_name}")
            return
            
        print(f"\n{'='*80}")
        print(f"HOT PATHS ANALYSIS: {operation_name}")
        print(f"{'='*80}")
        
        profiler = self.profiles[operation_name]
        stats = pstats.Stats(profiler)
        
        # Print different views of the hot paths
        print(f"\nTOP {top_n} FUNCTIONS BY CUMULATIVE TIME:")
        print("-" * 80)
        stats.sort_stats('cumulative').print_stats(top_n)
        
        print(f"\nTOP {top_n} FUNCTIONS BY TOTAL TIME (excluding subcalls):")
        print("-" * 80)
        stats.sort_stats('tottime').print_stats(top_n)
        
        print(f"\nTOP {top_n} MOST CALLED FUNCTIONS:")
        print("-" * 80)
        stats.sort_stats('ncalls').print_stats(top_n)
    
    def print_summary(self):
        """Print a formatted summary of CPU usage."""
        if not self.measurements:
            print("No measurements recorded.")
            return
            
        df = self.get_summary()
        
        print("\n" + "="*80)
        print("RUNTIME CPU PROFILING SUMMARY")
        print("="*80)
        
        print(f"\nTotal measurements: {len(df)}")
        print(f"Total runtime: {df['duration_seconds'].sum():.2f} seconds")
        print(f"Total function calls: {df['total_calls'].sum():,}")
        print(f"Average calls per second: {df['calls_per_second'].mean():.0f}")
        
        print(f"\nTOP 10 TIME CONSUMERS:")
        print("-" * 80)
        print(f"{'Operation':<35} {'Duration (s)':<12} {'Calls':<10} {'Calls/sec':<10} {'Details':<20}")
        print("-" * 80)
        
        for _, row in df.head(10).iterrows():
            print(f"{row['operation']:<35} {row['duration_seconds']:8.2f}     {row['total_calls']:8,}   {row['calls_per_second']:8.0f}   {row['details']:<20}")
    
    def export_detailed_stats(self, output_dir: Path):
        """Export detailed profiling stats to files."""
        output_dir.mkdir(exist_ok=True)
        
        for operation_name, profiler in self.profiles.items():
            # Create filename-safe operation name
            safe_name = "".join(c for c in operation_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_name = safe_name.replace(' ', '_')
            
            # Export binary .prof file for analysis tools
            prof_file = output_dir / f"cpu_profile_{safe_name}.prof"
            profiler.dump_stats(str(prof_file))
            print(f"Binary profile exported to: {prof_file}")
            
            # Export detailed stats to text file
            stats_file = output_dir / f"cpu_profile_{safe_name}.txt"
            with open(stats_file, 'w') as f:
                stats = pstats.Stats(profiler, stream=f)
                f.write(f"CPU Profile for: {operation_name}\n")
                f.write("="*60 + "\n\n")
                
                f.write("TOP 50 FUNCTIONS BY CUMULATIVE TIME:\n")
                f.write("-"*60 + "\n")
                stats.sort_stats('cumulative').print_stats(50)
                
                f.write("\n\nTOP 50 FUNCTIONS BY TOTAL TIME:\n")
                f.write("-"*60 + "\n")
                stats.sort_stats('tottime').print_stats(50)
                
                f.write("\n\nTOP 50 MOST CALLED FUNCTIONS:\n")
                f.write("-"*60 + "\n")
                stats.sort_stats('ncalls').print_stats(50)
            
            print(f"Detailed stats exported to: {stats_file}")

    def dump_hotpaths_to_file(self, operation_name: str, output_dir: Path, top_n: int = 20):
        """Dump the top CPU hotpaths for a specific operation to a file."""
        if operation_name not in self.profiles:
            print(f"No profile data found for: {operation_name}")
            return
            
        output_dir.mkdir(exist_ok=True)
        
        # Create filename-safe operation name
        safe_name = "".join(c for c in operation_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        
        hotpaths_file = output_dir / f"hotpaths_{safe_name}.txt"
        
        with open(hotpaths_file, 'w') as f:
            f.write(f"{'='*80}\n")
            f.write(f"HOT PATHS ANALYSIS: {operation_name}\n")
            f.write(f"{'='*80}\n\n")
            
            profiler = self.profiles[operation_name]
            stats = pstats.Stats(profiler, stream=f)
            
            # Write different views of the hot paths
            f.write(f"TOP {top_n} FUNCTIONS BY CUMULATIVE TIME:\n")
            f.write("-" * 80 + "\n")
            stats.sort_stats('cumulative').print_stats(top_n)
            
            f.write(f"\n\nTOP {top_n} FUNCTIONS BY TOTAL TIME (excluding subcalls):\n")
            f.write("-" * 80 + "\n")
            stats.sort_stats('tottime').print_stats(top_n)
            
            f.write(f"\n\nTOP {top_n} MOST CALLED FUNCTIONS:\n")
            f.write("-" * 80 + "\n")
            stats.sort_stats('ncalls').print_stats(top_n)
        
        print(f"Hot paths analysis exported to: {hotpaths_file}")


class InstrumentedFlexibilityCalculator(FlexibilityCalculator):
    """FlexibilityCalculator with CPU profiling instrumentation."""
    
    def __init__(self, config: Config, profiler: CPUProfiler):
        super().__init__(config)
        self.profiler = profiler
        self.comprehensive_profiler = None
        
    def calculate(self) -> pd.DataFrame:
        """Instrumented version of the main calculation method."""
        print("Starting comprehensive flexibility cost calculation profiling...")
        print("="*60)
        
        # Create comprehensive profiler for the entire execution  
        self.comprehensive_profiler = cProfile.Profile()
        self.comprehensive_profiler.enable()
        
        try:
            # Run the actual calculation - this will be captured by comprehensive profiler
            return self._run_calculation_direct()
        finally:
            self.comprehensive_profiler.disable()
            # Store the comprehensive profiler
            self.profiler.profiles["COMPREHENSIVE_EXECUTION"] = self.comprehensive_profiler
    
    def _run_calculation_direct(self) -> pd.DataFrame:
        """Direct calculation without measurement wrappers for comprehensive profiling."""
        
        # Load market data
        print("Loading market data...")
        self._market_data = self.load_market_data()
        
        # Price adjustments
        print("Calculating price adjustments...")
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
        
        # Boundary prices
        print("Finding boundary prices...")
        self._boundary_prices = self.find_boundary_prices(self._adjusted_prices)
        
        # Flexibility costs
        print("Calculating flexibility costs...")
        self._flexibility_service_costs = self.calculate_flexibility_costs(
            self._adjusted_prices, 
            self._boundary_prices
        )
        
        # Volatility calculation
        print("Calculating volatility...")
        from energy_flexibility.core.market_analysis import calculate_standard_deviation
        self._standard_deviations = calculate_standard_deviation(
            self._market_data, 
            self.config.delivery_date, 
            lookback_days=self.config.volatility_analysis_days
        )
        
        # Option prices
        print("Calculating option prices...")
        from energy_flexibility.core.cost_calculation import calculate_option_prices
        self._option_prices = calculate_option_prices(
            market_data_df=self._adjusted_prices.copy(),
            charging_strike_price=self._boundary_prices[1],
            discharging_strike_price=self._boundary_prices[0],
            historical_volatilities=self._standard_deviations,
            day_ahead_prices=self._adjusted_prices["da_prices"],
            expected_intraday_prices=self._adjusted_prices["adjusted_da_prices"]
        )
        
        # Load schedule data
        print("Loading schedule data...")
        self._operational_schedule_data = self._load_schedule_data()
        
        # Production costs
        print("Calculating production costs...")
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
        
        # Deprecation costs
        print("Calculating deprecation costs...")
        from energy_flexibility.core.cost_calculation import calculate_deprecation_cost
        cost_depreciation = calculate_deprecation_cost(
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
        
        # Aggregate costs
        print("Aggregating costs...")
        from energy_flexibility.core.cost_calculation import aggregate_costs
        # Use absolute path for output
        script_dir = Path(__file__).parent
        project_dir = script_dir.parent
        excel_output_path = str(project_dir / "output" / "cost_values_mit_ex_ante_kostenwerte.xlsx")
        aggregated_costs = aggregate_costs(
            cost_depreciation, 
            excel_export_path=excel_output_path
        )
        
        # Generate TSO report
        print("Generating TSO report...")
        self._generate_tso_report()
        
        return aggregated_costs
    
    def _run_calculation_with_measurements(self) -> pd.DataFrame:
        """The calculation logic with individual measurements for timing analysis."""
        
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
            cost_depreciation = calculate_deprecation_cost(
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
                cost_depreciation, 
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
    """Profile specific CPU-intensive operations in detail."""
    print("\n" + "="*60)
    print("DETAILED OPERATION PROFILING")
    print("="*60)
    
    profiler = CPUProfiler()
    
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
    
    # Show hot paths for the slowest operation
    slowest_op = max(profiler.measurements, key=lambda x: x['duration_seconds'])
    profiler.print_hotpaths(slowest_op['operation'], top_n=10)

    # Dump hot paths for the slowest operation to file
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    output_dir = project_dir / "output" / "cpu_profiles"
    
    slowest_op = max(profiler.measurements, key=lambda x: x['duration_seconds'])
    profiler.dump_hotpaths_to_file(slowest_op['operation'], output_dir, top_n=10)


def run_full_calculation_profile():
    """Run the full calculation with CPU profiling."""
    print("RUNTIME CPU PROFILING - FlexibilityCalculator")
    print("="*60)
    
    profiler = CPUProfiler()
    
    try:
        # Create configuration
        config = create_test_config()
        
        # Create instrumented calculator
        calculator = InstrumentedFlexibilityCalculator(config, profiler)
        
        # Run the calculation
        result = calculator.calculate()
        
        # Print detailed summary
        profiler.print_summary()
        
        # Export detailed results and hot paths
        script_dir = Path(__file__).parent
        project_dir = script_dir.parent
        output_dir = project_dir / "output" / "cpu_profiles"
        profiler.export_detailed_stats(output_dir)
        
        # Dump hot paths for the most time-consuming operations to files
        print(f"\nDETAILED HOT PATH ANALYSIS")
        print("="*60)
        
        # Get top 3 most time-consuming operations
        top_operations = sorted(profiler.measurements, key=lambda x: x['duration_seconds'], reverse=True)[:3]
        
        for measurement in top_operations:
            profiler.dump_hotpaths_to_file(measurement['operation'], output_dir, top_n=15)
        
        # Also dump comprehensive execution hot paths
        if "COMPREHENSIVE_EXECUTION" in profiler.profiles:
            profiler.dump_hotpaths_to_file("COMPREHENSIVE_EXECUTION", output_dir, top_n=20)
        
        # Export detailed results focused on comprehensive execution
        script_dir = Path(__file__).parent
        project_dir = script_dir.parent
        output_dir = project_dir / "output" / "cpu_profiles"
        profiler.export_detailed_stats(output_dir)
        
        # Focus on comprehensive execution hot paths - this captures the real application bottlenecks
        print(f"\nCOMPREHENSIVE EXECUTION HOT PATH ANALYSIS")
        print("="*60)
        
        if "COMPREHENSIVE_EXECUTION" in profiler.profiles:
            profiler.dump_hotpaths_to_file("COMPREHENSIVE_EXECUTION", output_dir, top_n=50)
            print("✅ Comprehensive hot paths analysis saved to file")
            
            # Print basic stats about the comprehensive profile
            comp_profiler = profiler.profiles["COMPREHENSIVE_EXECUTION"]
            stats = pstats.Stats(comp_profiler)
            print(f"📊 Comprehensive profile contains:")
            print(f"   • Total function calls: {stats.total_calls:,}")
            print(f"   • Total execution time: {stats.total_tt:.3f} seconds")
            print(f"   • Unique functions profiled: {len(stats.stats):,}")
        else:
            print("❌ No comprehensive execution profile found")
        
        # Save timing summary for reference
        summary_df = profiler.get_summary()
        if not summary_df.empty:
            output_file = project_dir / "output" / "runtime_cpu_profile.csv"
            summary_df.to_csv(output_file, index=False)
            print(f"📄 Timing summary saved to: {output_file}")
        
        return result, profiler
        
    except Exception as e:
        print(f"Error during profiling: {e}")
        import traceback
        traceback.print_exc()
        profiler.print_summary()
        return None, profiler


if __name__ == "__main__":
    # Create output directory if it doesn't exist
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    output_dir = project_dir / "output"
    output_dir.mkdir(exist_ok=True)
    
    print("Starting Runtime CPU Profiling...")
    print("This will instrument the FlexibilityCalculator to identify CPU hot paths during calculations.\n")
    
    # Run detailed operation profiling first
    profile_detailed_operations()
    
    # Run full calculation profiling
    result, profiler = run_full_calculation_profile()
    
    if result is not None:
        print(f"\nCalculation completed successfully!")
        print(f"Result shape: {result.shape}")
        print(f"Total CPU measurements: {len(profiler.measurements)}")
        
        # Highlight the comprehensive profiler
        print(f"\n{'='*80}")
        print("🎯 COMPREHENSIVE EXECUTION PROFILE GENERATED")
        print(f"{'='*80}")
        
        comp_prof_file = project_dir / "output" / "cpu_profiles" / "cpu_profile_COMPREHENSIVE_EXECUTION.prof"
        print(f"✅ MAIN COMPREHENSIVE .PROF FILE:")
        print(f"   📁 {comp_prof_file}")
        print(f"\nThis .prof file contains the COMPLETE execution profile with full call stack depth.")
        print(f"Analyze it with:")
        print(f"   • snakeviz {comp_prof_file}")
        print(f"   • python -m pstats {comp_prof_file}")
        
        # Show comprehensive profile stats
        if "COMPREHENSIVE_EXECUTION" in profiler.profiles:
            comp_profiler = profiler.profiles["COMPREHENSIVE_EXECUTION"]
            stats = pstats.Stats(comp_profiler)
            print(f"\nCOMPREHENSIVE PROFILE STATS:")
            print(f"   • Total function calls: {stats.total_calls:,}")
            print(f"   • Total execution time: {stats.total_tt:.2f} seconds")
            print(f"   • Functions profiled: {len(stats.stats):,}")
        
        print(f"\nHOT PATH DETECTION COMPLETE")
        print("Check the detailed profile files in output/cpu_profiles/ for function-level analysis")
    else:
        print("\nCalculation failed - see error details above") 