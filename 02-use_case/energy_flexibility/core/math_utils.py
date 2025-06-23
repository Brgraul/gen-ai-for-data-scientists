"""
Lightweight mathematical functions to replace scipy dependencies.

This module provides standard normal distribution functions using built-in
math operations, eliminating the 30MB scipy import overhead.
"""

import math
import numpy as np
import pandas as pd
from typing import Union


def norm_cdf(x: Union[float, pd.Series, np.ndarray]) -> Union[float, pd.Series, np.ndarray]:
    """
    Standard normal cumulative distribution function.
    
    Uses built-in math.erf() for high accuracy without scipy dependency.
    Equivalent to scipy.stats.norm.cdf(x) for standard normal distribution.
    
    Args:
        x: Input value (scalar, pandas Series, or numpy array)
        
    Returns:
        P(X <= x) where X ~ N(0,1)
    """
    if isinstance(x, (pd.Series, np.ndarray)):
        # Vectorized version for arrays
        if isinstance(x, pd.Series):
            return x.apply(lambda val: 0.5 * (1.0 + math.erf(val / math.sqrt(2.0))))
        else:  # numpy array
            return np.array([0.5 * (1.0 + math.erf(val / math.sqrt(2.0))) for val in x])
    else:
        # Scalar version
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: Union[float, pd.Series, np.ndarray]) -> Union[float, pd.Series, np.ndarray]:
    """
    Standard normal probability density function.
    
    Uses built-in math functions for high performance without scipy dependency.
    Equivalent to scipy.stats.norm.pdf(x) for standard normal distribution.
    
    Args:
        x: Input value (scalar, pandas Series, or numpy array)
        
    Returns:
        Probability density at x for N(0,1)
    """
    if isinstance(x, (pd.Series, np.ndarray)):
        # Vectorized version for arrays
        if isinstance(x, pd.Series):
            return x.apply(lambda val: math.exp(-0.5 * val * val) / math.sqrt(2.0 * math.pi))
        else:  # numpy array
            return np.array([math.exp(-0.5 * val * val) / math.sqrt(2.0 * math.pi) for val in x])
    else:
        # Scalar version
        return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi) 