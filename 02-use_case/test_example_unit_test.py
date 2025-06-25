"""
EXEMPLARY UNIT TEST - Best Practices Demo
=========================================

This test demonstrates all key unit testing best practices:
1. Testing BEHAVIOR rather than implementation
2. Comprehensive mocking with pytest
3. Clear test scenarios anyone can understand
4. No domain knowledge required

Function under test: expand_da_time()
- Converts hourly price data to 15-minute intervals  
- Simple, pure function with clear input/output
- Perfect for teaching unit testing fundamentals
"""

import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import Mock, patch, call
from energy_flexibility.core.data_loader import expand_da_time


def test_expand_da_time_behavior():
    """Test that hourly prices expand to 4 quarter-hourly entries"""
    # Arrange
    input_data = pd.DataFrame({
        'hour_time': [datetime(2023, 4, 30, 14, 0)],
        'price': [50.0]
    })
    
    # Act
    result = expand_da_time(input_data, 'hour_time', 'price')
    
    # Assert
    assert len(result) == 4  # 1 hour → 4 quarters
    assert all(result['da_prices'] == 50.0)  # Same price
    # Test specific minute values: 00, 15, 30, 45 