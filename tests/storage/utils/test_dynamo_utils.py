from decimal import Decimal
from unittest.mock import MagicMock, patch

import src.storage.dynamo_utils as dynamo_utils


def test_scan_table_returns_items():
    mock_table = MagicMock()
    mock_table.scan.side_effect = [
        {"Items": [{"id": 1}], "LastEvaluatedKey": "k"},
        {"Items": [{"id": 2}]},
    ]
    with patch("src.storage.dynamo_utils.get_ddb_table", return_value=mock_table):
        items = dynamo_utils.scan_table("table")
    assert items == [{"id": 1}, {"id": 2}]


def test_search_table_by_fields_matches():
    items = [
        {"name": "A", "type": "model"},
        {"name": "B", "type": "dataset"},
    ]
    result = dynamo_utils.search_table_by_fields("table", {"type": "model"}, item_list=items)
    assert result == [{"name": "A", "type": "model"}]


def test_batch_delete_deletes_items():
    mock_table = MagicMock()
    items = [{"artifact_id": "1"}, {"artifact_id": "2"}]
    with patch("src.storage.dynamo_utils.get_ddb_table", return_value=mock_table):
        count = dynamo_utils.batch_delete("table", items, "artifact_id")
    assert count == 2
    assert mock_table.batch_writer.return_value.__enter__.return_value.delete_item.call_count == 2


def test_clear_table_calls_batch_delete():
    with patch("src.storage.dynamo_utils.scan_table", return_value=[{"artifact_id": "1"}]), patch(
        "src.storage.dynamo_utils.batch_delete", return_value=1
    ) as mock_delete:
        count = dynamo_utils.clear_table("table", "artifact_id")
    assert count == 1
    mock_delete.assert_called_once()


# =============================================================================
# Float to Decimal Conversion Tests
# =============================================================================
def test_convert_floats_to_decimal_simple():
    """Test simple float conversion."""
    result = dynamo_utils._convert_floats_to_decimal(0.85)
    assert isinstance(result, Decimal)
    assert result == Decimal("0.85")


def test_convert_floats_to_decimal_dict():
    """Test float conversion in nested dictionary."""
    obj = {"score": 0.85, "rating": 0.95, "name": "test"}
    result = dynamo_utils._convert_floats_to_decimal(obj)

    assert isinstance(result["score"], Decimal)
    assert isinstance(result["rating"], Decimal)
    assert result["score"] == Decimal("0.85")
    assert result["rating"] == Decimal("0.95")
    assert result["name"] == "test"  # String unchanged


def test_convert_floats_to_decimal_nested_dict():
    """Test float conversion in deeply nested structures."""
    obj = {"metrics": {"net_score": 0.85, "sub": {"value": 0.75}}, "count": 42}
    result = dynamo_utils._convert_floats_to_decimal(obj)

    assert isinstance(result["metrics"]["net_score"], Decimal)
    assert isinstance(result["metrics"]["sub"]["value"], Decimal)
    assert result["count"] == 42  # Integer unchanged


def test_convert_floats_to_decimal_list():
    """Test float conversion in lists."""
    obj = [0.1, 0.2, 0.3, "string", 42]
    result = dynamo_utils._convert_floats_to_decimal(obj)

    assert isinstance(result[0], Decimal)
    assert isinstance(result[1], Decimal)
    assert isinstance(result[2], Decimal)
    assert result[3] == "string"
    assert result[4] == 42


def test_convert_floats_to_decimal_nan():
    """Test NaN handling (converts to None)."""
    result = dynamo_utils._convert_floats_to_decimal(float("nan"))
    assert result is None


def test_convert_floats_to_decimal_infinity():
    """Test infinity handling (converts to None)."""
    result_pos = dynamo_utils._convert_floats_to_decimal(float("inf"))
    result_neg = dynamo_utils._convert_floats_to_decimal(float("-inf"))
    assert result_pos is None
    assert result_neg is None


def test_convert_floats_to_decimal_preserves_types():
    """Test that non-float types are preserved."""
    obj = {
        "int": 42,
        "str": "hello",
        "bool": True,
        "none": None,
        "float": 0.5,
    }
    result = dynamo_utils._convert_floats_to_decimal(obj)

    assert result["int"] == 42
    assert result["str"] == "hello"
    assert result["bool"] is True
    assert result["none"] is None
    assert isinstance(result["float"], Decimal)


def test_save_item_converts_floats():
    """Test that save_item_to_table converts floats before saving."""
    mock_table = MagicMock()
    item = {"score": 0.85, "name": "test"}

    with patch("src.storage.dynamo_utils.get_ddb_table", return_value=mock_table):
        dynamo_utils.save_item_to_table("table", item)

    # Verify put_item was called
    mock_table.put_item.assert_called_once()

    # Get the actual item that was saved
    saved_item = mock_table.put_item.call_args[1]["Item"]

    # Verify float was converted to Decimal
    assert isinstance(saved_item["score"], Decimal)
    assert saved_item["score"] == Decimal("0.85")
    assert saved_item["name"] == "test"
