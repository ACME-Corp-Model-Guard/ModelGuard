import pytest
from unittest.mock import patch, MagicMock

import src.storage.dynamo_utils as dynamo_utils

class DummyArtifact:
	def __init__(self, artifact_id, artifact_type, name):
		self.artifact_id = artifact_id
		self.artifact_type = artifact_type
		self.name = name
	def to_dict(self):
		return {
			"artifact_id": self.artifact_id,
			"artifact_type": self.artifact_type,
			"name": self.name,
		}

def test_scan_table_returns_items():
	mock_table = MagicMock()
	mock_table.scan.side_effect = [
		{"Items": [{"id": 1}], "LastEvaluatedKey": "k"},
		{"Items": [{"id": 2}]}
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
	with patch("src.storage.dynamo_utils.scan_table", return_value=[{"artifact_id": "1"}]), \
		 patch("src.storage.dynamo_utils.batch_delete", return_value=1) as mock_delete:
		count = dynamo_utils.clear_table("table", "artifact_id")
	assert count == 1
	mock_delete.assert_called_once()

def test_save_artifact_metadata_puts_item():
	dummy = DummyArtifact("id1", "model", "foo")
	mock_table = MagicMock()
	with patch("src.storage.dynamo_utils.get_ddb_table", return_value=mock_table), \
		 patch("src.storage.dynamo_utils.ARTIFACTS_TABLE", "table"):
		dynamo_utils.save_artifact_metadata(dummy)
	mock_table.put_item.assert_called_once_with(Item=dummy.to_dict())