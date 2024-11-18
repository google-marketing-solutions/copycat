# Copyright 2024 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for mock_gspread.

These test that the mock behaves like the real gspread client.
"""

from absl.testing import absltest
from absl.testing import parameterized
import gspread

from copycat.data import mock_gspread


class PatchEmbeddingsModelTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()
    self.gspread_patcher = mock_gspread.PatchGspread()
    self.gspread_patcher.start()

  def tearDown(self):
    super().tearDown()
    self.gspread_patcher.stop()

  def test_create_makes_an_empty_sheet(self):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")

    self.assertListEqual(
        [sheet.title for sheet in spreadsheet.worksheets()], ["Sheet1"]
    )
    self.assertListEqual(spreadsheet.worksheet("Sheet1").get_all_records(), [])

  def test_get_url_loads_the_sheet_from_the_url(self):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")

    retrieved_spreadsheet = client.open_by_url(spreadsheet.url)

    self.assertIs(retrieved_spreadsheet, spreadsheet)

  def test_get_url_raises_exception_if_url_is_not_found(self):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")

    with self.assertRaises(gspread.SpreadsheetNotFound):
      client.open_by_url("invalid url")

  def test_add_worksheet_adds_an_empty_worksheet_with_default_rows_and_columns(
      self,
  ):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")

    spreadsheet.add_worksheet("new worksheet")

    worksheet = spreadsheet.worksheet("new worksheet")
    self.assertListEqual(worksheet.get_all_records(), [])
    self.assertEqual(worksheet.row_count, 1000)
    self.assertEqual(worksheet.col_count, 26)

  def test_add_worksheet_adds_an_empty_worksheet_with_specified_rows_and_columns(
      self,
  ):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")

    spreadsheet.add_worksheet("new worksheet", rows=10, cols=2)

    worksheet = spreadsheet.worksheet("new worksheet")
    self.assertListEqual(worksheet.get_all_records(), [])
    self.assertEqual(worksheet.row_count, 10)
    self.assertEqual(worksheet.col_count, 2)

  def test_del_worksheet_deletes_the_worksheet(
      self,
  ):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")
    spreadsheet.add_worksheet("new worksheet")

    self.assertListEqual(
        [sheet.title for sheet in spreadsheet.worksheets()],
        ["Sheet1", "new worksheet"],
    )

    spreadsheet.del_worksheet(spreadsheet.worksheet("new worksheet"))
    self.assertListEqual(
        [sheet.title for sheet in spreadsheet.worksheets()], ["Sheet1"]
    )

  def test_worksheets_returns_all_worksheets_in_the_spreadsheet(self):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")
    spreadsheet.add_worksheet("new worksheet 1")
    spreadsheet.add_worksheet("new worksheet 2")

    self.assertListEqual(
        [worksheet.title for worksheet in spreadsheet.worksheets()],
        ["Sheet1", "new worksheet 1", "new worksheet 2"],
    )

  def test_get_all_records_returns_expected_records(self):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")
    worksheet = spreadsheet.worksheet("Sheet1")

    worksheet.update([["a", "b"], [1, 2], [3, 4]])

    self.assertListEqual(
        worksheet.get_all_records(),
        [{"a": 1, "b": 2}, {"a": 3, "b": 4}],
    )

  @parameterized.named_parameters([
      {
          "testcase_name": "freeze_rows",
          "rows": 1,
          "cols": None,
          "expected_frozen_rows": 1,
          "expected_frozen_cols": 0,
      },
      {
          "testcase_name": "freeze_cols",
          "rows": None,
          "cols": 2,
          "expected_frozen_rows": 0,
          "expected_frozen_cols": 2,
      },
      {
          "testcase_name": "freeze_both",
          "rows": 1,
          "cols": 2,
          "expected_frozen_rows": 1,
          "expected_frozen_cols": 2,
      },
  ])
  def test_can_freeze_rows_and_columns(
      self, rows, cols, expected_frozen_rows, expected_frozen_cols
  ):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")
    worksheet = spreadsheet.worksheet("Sheet1")

    worksheet.freeze(rows=rows, cols=cols)

    self.assertEqual(worksheet.frozen_row_count, expected_frozen_rows)
    self.assertEqual(worksheet.frozen_col_count, expected_frozen_cols)

  @parameterized.named_parameters([
      {
          "testcase_name": "single_range",
          "cell_range": "A1:B2",
          "expected_cells_with_formatting": [(0, 0), (0, 1), (1, 0), (1, 1)],
      },
      {
          "testcase_name": "single_cell",
          "cell_range": "A1",
          "expected_cells_with_formatting": [(0, 0)],
      },
      {
          "testcase_name": "complete_column",
          "cell_range": "A:A",
          "expected_cells_with_formatting": [(0, 0), (1, 0), (2, 0)],
      },
      {
          "testcase_name": "complete_row",
          "cell_range": "1:1",
          "expected_cells_with_formatting": [(0, 0), (0, 1), (0, 2)],
      },
  ])
  def test_format_adds_formatting_to_expected_cells(
      self, cell_range, expected_cells_with_formatting
  ):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")
    worksheet = spreadsheet.add_worksheet("Sheet2", rows=3, cols=3)

    target_format = {"textFormat": {"bold": True}}
    worksheet.format(cell_range, target_format)

    for i in range(worksheet.row_count):
      for j in range(worksheet.col_count):
        if (i, j) in expected_cells_with_formatting:
          self.assertDictEqual(worksheet._formatting[i][j], target_format)
        else:
          self.assertDictEqual(worksheet._formatting[i][j], {})

  @parameterized.named_parameters([
      {
          "testcase_name": "single_range",
          "cell_range": "B2:C3",
          "values": [[1, 2], [3, 4]],
          "expected_data": [["", "", ""], ["", 1, 2], ["", 3, 4]],
      },
      {
          "testcase_name": "single_cell",
          "cell_range": "A1",
          "values": [[1]],
          "expected_data": [[1, "", ""], ["", "", ""], ["", "", ""]],
      },
      {
          "testcase_name": "no range specified",
          "cell_range": None,
          "values": [[1, 2], [3, 4]],
          "expected_data": [[1, 2, ""], [3, 4, ""], ["", "", ""]],
      },
  ])
  def test_update_can_update_specific_cell_range(
      self, cell_range, values, expected_data
  ):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")
    worksheet = spreadsheet.add_worksheet("Sheet2", rows=3, cols=3)

    worksheet.update(values, cell_range)

    self.assertListEqual(worksheet._data, expected_data)

  @parameterized.named_parameters([
      {
          "testcase_name": "too many cols for range",
          "cell_range": "A1:A2",
          "values": [[1, 2], [3, 4]],
      },
      {
          "testcase_name": "too many rows for range",
          "cell_range": "A1:B1",
          "values": [[1, 2], [3, 4]],
      },
      {
          "testcase_name": "too many cols for sheet",
          "cell_range": "A1:D1",
          "values": [[1, 2, 3, 4]],
      },
      {
          "testcase_name": "too many rows for sheet",
          "cell_range": "A1:A4",
          "values": [[1], [2], [3], [4]],
      },
      {
          "testcase_name": "too many cols for sheet no range specified",
          "cell_range": None,
          "values": [[1, 2, 3, 4]],
      },
      {
          "testcase_name": "too many rows for sheet no range specified",
          "cell_range": None,
          "values": [[1], [2], [3], [4]],
      },
  ])
  def test_update_raises_value_error_if_out_of_range(self, cell_range, values):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")
    worksheet = spreadsheet.add_worksheet("Sheet2", rows=3, cols=3)

    with self.assertRaises(ValueError):
      worksheet.update(values, cell_range)

  def test_batch_update_applies_all_updates(self):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")
    worksheet = spreadsheet.add_worksheet("Sheet2", rows=4, cols=4)

    updates_list = [
        {"range": "A1:A2", "values": [["1"], ["2"]]},
        {"range": "B3:C4", "values": [["3", "4"], ["5", "6"]]},
    ]

    worksheet.batch_update(updates_list)

    expected_data = [
        ["1", "", "", ""],
        ["2", "", "", ""],
        ["", "3", "4", ""],
        ["", "5", "6", ""],
    ]
    self.assertListEqual(worksheet._data, expected_data)

  def test_add_rows_adds_rows_to_the_worksheet(self):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")
    worksheet = spreadsheet.add_worksheet("Sheet2", rows=4, cols=4)

    worksheet.add_rows(2)

    self.assertEqual(worksheet.row_count, 6)

  def test_add_cols_adds_cols_to_the_worksheet(self):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")
    worksheet = spreadsheet.add_worksheet("Sheet2", rows=4, cols=4)

    worksheet.add_cols(2)

    self.assertEqual(worksheet.col_count, 6)

  @parameterized.named_parameters([
      {
          "testcase_name": "no_end_index",
          "start_index": 1,
          "end_index": None,
          "expected_data": [
              ["1", "2", "", ""],
              ["5", "6", "", ""],
              ["7", "8", "", ""],
          ],
      },
      {
          "testcase_name": "with_end_index",
          "start_index": 1,
          "end_index": 2,
          "expected_data": [
              ["1", "2", "", ""],
              ["7", "8", "", ""],
          ],
      },
  ])
  def test_delete_rows_deletes_rows_from_the_worksheet(
      self, start_index, end_index, expected_data
  ):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")
    worksheet = spreadsheet.add_worksheet("Sheet2", rows=4, cols=4)
    worksheet.update([
        ["1", "2"],
        ["3", "4"],
        ["5", "6"],
        ["7", "8"],
    ])

    worksheet.delete_rows(start_index=start_index, end_index=end_index)

    self.assertListEqual(worksheet._data, expected_data)

  @parameterized.named_parameters([
      {
          "testcase_name": "no_end_index",
          "start_index": 1,
          "end_index": None,
          "expected_data": [
              ["1", "3", "4"],
              ["5", "7", "8"],
              ["", "", ""],
              ["", "", ""],
          ],
      },
      {
          "testcase_name": "with_end_index",
          "start_index": 1,
          "end_index": 2,
          "expected_data": [
              ["1", "4"],
              ["5", "8"],
              ["", ""],
              ["", ""],
          ],
      },
  ])
  def test_delete_columns_deletes_columns_from_the_worksheet(
      self, start_index, end_index, expected_data
  ):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")
    worksheet = spreadsheet.add_worksheet("Sheet2", rows=4, cols=4)
    worksheet.update([
        ["1", "2", "3", "4"],
        ["5", "6", "7", "8"],
    ])

    worksheet.delete_columns(start_index=start_index, end_index=end_index)

    self.assertListEqual(worksheet._data, expected_data)

  def test_clear_removes_all_data_and_formatting_from_the_worksheet(self):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")
    worksheet = spreadsheet.add_worksheet("Sheet2", rows=4, cols=4)
    worksheet.update([
        ["1", "2", "3", "4"],
        ["5", "6", "7", "8"],
    ])
    worksheet.format("A1:A2", {"textFormat": {"bold": True}})

    worksheet.clear()

    self.assertListEqual(worksheet._data, [[""] * 4] * 4)
    self.assertListEqual(worksheet._formatting, [[{}] * 4] * 4)

  def test_insert_row_inserts_a_row_at_the_given_index(self):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")
    worksheet = spreadsheet.add_worksheet("Sheet2", rows=2, cols=4)
    worksheet.update([
        ["1", "2", "3", "4"],
        ["5", "6", "7", "8"],
    ])

    worksheet.insert_row(["9", "10", "11", "12"], index=2)

    self.assertListEqual(
        worksheet._data,
        [
            ["1", "2", "3", "4"],
            ["9", "10", "11", "12"],
            ["5", "6", "7", "8"],
        ],
    )
    self.assertListEqual(
        worksheet._formatting,
        [
            [{}] * 4,
            [{}] * 4,
            [{}] * 4,
        ],
    )

  def test_insert_row_adds_columns_if_needed(self):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")
    worksheet = spreadsheet.add_worksheet("Sheet2", rows=2, cols=4)
    worksheet.update([
        ["1", "2", "3", "4"],
        ["5", "6", "7", "8"],
    ])

    worksheet.insert_row(["9", "10", "11", "12", "13"], index=2)

    self.assertEqual(worksheet.col_count, 5)
    self.assertListEqual(
        worksheet._data,
        [
            ["1", "2", "3", "4", ""],
            ["9", "10", "11", "12", "13"],
            ["5", "6", "7", "8", ""],
        ],
    )
    self.assertListEqual(
        worksheet._formatting,
        [
            [{}] * 5,
            [{}] * 5,
            [{}] * 5,
        ],
    )

  def test_row_values_returns_the_values_in_the_given_row(self):
    client = gspread.authorize(None)
    spreadsheet = client.create("test_spreadsheet")
    worksheet = spreadsheet.add_worksheet("Sheet2", rows=2, cols=4)
    worksheet.update([
        ["1", "2", "3", "4"],
        ["5", "6", "7", "8"],
    ])

    self.assertListEqual(worksheet.row_values(1), ["1", "2", "3", "4"])
    self.assertListEqual(worksheet.row_values(2), ["5", "6", "7", "8"])


if __name__ == "__main__":
  absltest.main()
