#!/usr/bin/env python3
"""
Updated main.py that integrates with the new system design.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

try:
    from .logging_utils import setup_logging
except Exception:  # pragma: no cover
    def setup_logging() -> None:
        return

try:
    from .model_manager import ModelManager
    from .authorization import Authorization, Permission
    from .model import Model
except Exception:
    from model_manager import ModelManager
    from authorization import Authorization, Permission
    from model import Model


def iter_urls(path: Path):
    """Yield non-empty, non-comment lines as URLs."""
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            yield line


def _name_from_url(url: str) -> str:
    """Extract model name from URL."""
    base = url.rstrip("/").split("/")[-1]
    return (base or "artifact").lower()


def create_model_from_url(url: str) -> Model:
    """
    Create a Model instance from a URL.
    
    Args:
        url: URL to create model from
        
    Returns:
        Model instance
    """
    name = _name_from_url(url)
    
    # Generate S3 keys (placeholder for now)
    model_key = f"models/{name}/model"
    code_key = f"models/{name}/code"
    dataset_key = f"models/{name}/dataset"
    
    # Create model instance
    model = Model(
        name=name,
        model_key=model_key,
        code_key=code_key,
        dataset_key=dataset_key,
        size=0.0,  # TODO: Calculate actual size
        license="unknown"  # TODO: Extract from URL or metadata
    )
    
    return model


def process_urls_with_system(path: Path) -> List[Dict[str, Any]]:
    """
    Process URLs using the new system design.
    
    Args:
        path: Path to file containing URLs
        
    Returns:
        List of processed model records
    """
    # Initialize the system components
    model_manager = ModelManager()
    authorization = Authorization()
    
    # For now, we'll use a default user ID
    # TODO: Implement proper user authentication
    user_id = "default_user"
    
    rows: List[Dict[str, Any]] = []
    
    for url in iter_urls(path):
        try:
            # Create model from URL
            model = create_model_from_url(url)
            
            # Score the model using all available metrics
            model_manager._score_model(model)
            
            # Check if user has permission to access this model
            if not authorization.can_search(user_id):
                # Skip this model if user doesn't have search permission
                continue
            
            # Convert model to record format
            record = {
                "url": url,
                "name": model.name,
                "category": "MODEL" if "model" in url.lower() else "CODE",
                "net_score": 0.0,  # TODO: Calculate net score
                "net_score_latency": 0,
            }
            
            # Add individual metric scores
            for metric_name, score in model.scores.items():
                record[metric_name] = score
                record[f"{metric_name}_latency"] = model.scores_latency.get(metric_name, 0)
            
            # Add size score details (placeholder)
            record["size_score"] = {
                "raspberry_pi": 0.0,
                "jetson_nano": 0.0,
                "desktop_pc": 0.0,
                "aws_server": 0.0,
            }
            record["size_score_latency"] = 0
            
            rows.append(record)
            
        except Exception as e:
            # Emit a safe placeholder for failed URLs
            print(f"Error processing URL {url}: {e}", file=sys.stderr)
            rows.append({
                "url": url,
                "name": _name_from_url(url),
                "category": "CODE",
                "net_score": 0.0,
                "net_score_latency": 0,
                "ramp_up_time": 0.0,
                "ramp_up_time_latency": 0,
                "bus_factor": 0.0,
                "bus_factor_latency": 0,
                "performance_claims": 0.0,
                "performance_claims_latency": 0,
                "license": 0.0,
                "license_latency": 0,
                "size_score": {
                    "raspberry_pi": 0.0,
                    "jetson_nano": 0.0,
                    "desktop_pc": 0.0,
                    "aws_server": 0.0,
                },
                "size_score_latency": 0,
                "dataset_and_code_score": 0.0,
                "dataset_and_code_score_latency": 0,
                "dataset_quality": 0.0,
                "dataset_quality_latency": 0,
                "code_quality": 0.0,
                "code_quality_latency": 0,
            })
    
    return rows


def _print_ndjson(rows: List[Dict[str, Any]]) -> None:
    """Print rows as NDJSON."""
    for row in rows:
        print(json.dumps(row, separators=(",", ":")))


def main(argv: List[str]) -> int:
    """Main entry point."""
    try:
        setup_logging()
    except Exception:
        pass  # do not fail if LOG_FILE is bad

    if len(argv) != 2:
        print("Usage: python -m src.main_new <url_file>", file=sys.stderr)
        return 2

    path = Path(argv[1]).resolve()
    if not path.exists():
        print(f"Error: URL file not found: {path}", file=sys.stderr)
        return 2

    try:
        rows = process_urls_with_system(path)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    _print_ndjson(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
