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


# =============================================================================
# Load Item Tests
# =============================================================================


def test_load_item_from_key_returns_item():
    """Test loading an item by key."""
    mock_table = MagicMock()
    mock_table.get_item.return_value = {"Item": {"artifact_id": "123", "name": "test"}}

    with patch("src.storage.dynamo_utils.get_ddb_table", return_value=mock_table):
        result = dynamo_utils.load_item_from_key("table", {"artifact_id": "123"})

    assert result == {"artifact_id": "123", "name": "test"}
    mock_table.get_item.assert_called_once_with(Key={"artifact_id": "123"})


def test_load_item_from_key_not_found():
    """Test loading non-existent item returns None."""
    mock_table = MagicMock()
    mock_table.get_item.return_value = {}  # No Item key

    with patch("src.storage.dynamo_utils.get_ddb_table", return_value=mock_table):
        result = dynamo_utils.load_item_from_key("table", {"artifact_id": "nonexistent"})

    assert result is None


# =============================================================================
# Error Handling Tests
# =============================================================================


def test_save_item_raises_on_client_error():
    """Test that save_item_to_table raises on ClientError."""
    from botocore.exceptions import ClientError

    mock_table = MagicMock()
    mock_table.put_item.side_effect = ClientError(
        {"Error": {"Code": "ValidationException"}}, "PutItem"
    )

    with patch("src.storage.dynamo_utils.get_ddb_table", return_value=mock_table):
        import pytest

        with pytest.raises(ClientError):
            dynamo_utils.save_item_to_table("table", {"id": "test"})


def test_load_item_raises_on_client_error():
    """Test that load_item_from_key raises on ClientError."""
    from botocore.exceptions import ClientError

    mock_table = MagicMock()
    mock_table.get_item.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException"}}, "GetItem"
    )

    with patch("src.storage.dynamo_utils.get_ddb_table", return_value=mock_table):
        import pytest

        with pytest.raises(ClientError):
            dynamo_utils.load_item_from_key("table", {"artifact_id": "123"})


# =============================================================================
# Search Table Edge Cases
# =============================================================================


def test_search_table_by_fields_no_matches():
    """Test search with no matching items."""
    items = [
        {"name": "A", "type": "model"},
        {"name": "B", "type": "dataset"},
    ]
    result = dynamo_utils.search_table_by_fields("table", {"type": "code"}, item_list=items)
    assert result == []


def test_search_table_by_fields_multiple_fields():
    """Test search with multiple field conditions."""
    items = [
        {"name": "A", "type": "model", "status": "active"},
        {"name": "B", "type": "model", "status": "inactive"},
        {"name": "C", "type": "dataset", "status": "active"},
    ]
    result = dynamo_utils.search_table_by_fields(
        "table", {"type": "model", "status": "active"}, item_list=items
    )
    assert result == [{"name": "A", "type": "model", "status": "active"}]


def test_search_table_by_fields_scans_when_no_item_list():
    """Test that search scans table when no item_list provided."""
    mock_table = MagicMock()
    mock_table.scan.return_value = {
        "Items": [{"name": "A", "type": "model"}, {"name": "B", "type": "dataset"}]
    }

    with patch("src.storage.dynamo_utils.get_ddb_table", return_value=mock_table):
        result = dynamo_utils.search_table_by_fields("table", {"type": "model"})

    assert result == [{"name": "A", "type": "model"}]


# =============================================================================
# Batch Delete Edge Cases
# =============================================================================


def test_batch_delete_skips_missing_key():
    """Test that batch_delete skips items without the key."""
    mock_table = MagicMock()
    items = [
        {"artifact_id": "1"},
        {"other_field": "value"},  # Missing artifact_id
        {"artifact_id": "2"},
    ]

    with patch("src.storage.dynamo_utils.get_ddb_table", return_value=mock_table):
        count = dynamo_utils.batch_delete("table", items, "artifact_id")

    assert count == 2  # Only items with the key are deleted


def test_batch_delete_empty_list():
    """Test batch_delete with empty list."""
    mock_table = MagicMock()

    with patch("src.storage.dynamo_utils.get_ddb_table", return_value=mock_table):
        count = dynamo_utils.batch_delete("table", [], "artifact_id")

    assert count == 0
