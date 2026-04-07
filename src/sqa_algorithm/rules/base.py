import numpy as np
from typing import Tuple, Callable, Dict, Any, Protocol

class RulePlugin(Protocol):
    """
    Protocol defining the required function-based interface for all SQA rules/problem domains.
    Rule packages (e.g., `rules.facility_selection`, `rules.path_routing`) MUST provide 
    `adapter.py` and `builder.py` modules exposing the following module-level functions.
    """

    # --- In adapter.py ---
    @staticmethod
    def load_data(data_dir: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Loads domain-specific data from the data directory.
        
        Args:
            data_dir: Path to the directory containing rule-specific datasets.
            config: Configuration dictionary for the rule.

        Returns:
            A dictionary containing processed data needed by the builder.
        """
        ...

    # --- In builder.py ---
    @staticmethod
    def build_qubo(processed_data: Dict[str, Any], config: Dict[str, Any]) -> Tuple[np.ndarray, float, Callable[[np.ndarray], Dict[str, Any]]]:
        """
        Constructs the QUBO matrix and provides a state decoder.

        Args:
            processed_data: The output from the load_data method.
            config: Configuration dictionary for the rule.

        Returns:
            A tuple of (Q, offset, decoder) where:
              - Q: The QUBO matrix (np.ndarray, 2D float64).
              - offset: Constant energy offset (float).
              - decoder: A function that takes a binary state vector 
                         and returns a dictionary of domain-specific interpretation.
        """
        ...
