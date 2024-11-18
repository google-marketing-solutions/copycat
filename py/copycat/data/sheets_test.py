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

"""Tests for the sheets module."""

import datetime as dt
import logging

from absl.testing import absltest
from absl.testing import parameterized
import gspread
import pandas as pd

from copycat.data import mock_gspread
from copycat.data import sheets


class GoogleSheetTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()
    self.gspread_patcher = mock_gspread.PatchGspread()
    self.gspread_patcher.start()

    dummy_credentials = "dummy_credentials"
    sheets.set_google_auth_credentials(dummy_credentials)
    self.client = gspread.authorize(dummy_credentials)

  def tearDown(self):
    super().tearDown()
    self.gspread_patcher.stop()

  def test_can_instantiate_with_new_sheet(self):
    google_sheet = sheets.GoogleSheet.new("test_sheet")

    expected_str = "\n".join([
        "GoogleSheet:",
        "  URL: https://mock.sheets.com/spreadsheet/test_sheet",
        "  Name: test_sheet",
        "  Worksheet Names: ['Sheet1']",
    ])
    self.assertEqual(str(google_sheet), expected_str)

  def test_can_instantiate_with_existing_sheet(self):
    spreadsheet = self.client.create("test_sheet")
    spreadsheet.add_worksheet("Another Sheet")

    google_sheet = sheets.GoogleSheet.load(spreadsheet.url)

    expected_str = "\n".join([
        "GoogleSheet:",
        "  URL: https://mock.sheets.com/spreadsheet/test_sheet",
        "  Name: test_sheet",
        "  Worksheet Names: ['Sheet1', 'Another Sheet']",
    ])
    self.assertEqual(str(google_sheet), expected_str)

  def test_can_check_if_sheet_exists(self):
    google_sheet = sheets.GoogleSheet.new("test_sheet")

    self.assertIn("Sheet1", google_sheet)
    self.assertNotIn("Another Sheet", google_sheet)

  def test_can_load_data_as_pandas_dataframe(self):
    spreadsheet = self.client.create("test_sheet")
    spreadsheet.worksheet("Sheet1").update([
        ["header 1", "header 2"],
        ["row 1 col 1", "row 1 col 2"],
        ["row 2 col 1", "row 2 col 2"],
    ])

    google_sheet = sheets.GoogleSheet.load(spreadsheet.url)
    data = google_sheet["Sheet1"]

    expected_data = pd.DataFrame({
        "header 1": ["row 1 col 1", "row 2 col 1"],
        "header 2": ["row 1 col 2", "row 2 col 2"],
    })

    pd.testing.assert_frame_equal(data, expected_data)

  def test_can_load_data_with_index_as_pandas_dataframe(self):
    spreadsheet = self.client.create("test_sheet")
    spreadsheet.worksheet("Sheet1").update([
        ["my_index", "header 1", "header 2"],
        ["a", "row 1 col 1", "row 1 col 2"],
        ["b", "row 2 col 1", "row 2 col 2"],
    ])
    spreadsheet.worksheet("Sheet1").freeze(cols=1)  # Indexes are frozen columns

    google_sheet = sheets.GoogleSheet.load(spreadsheet.url)
    data = google_sheet["Sheet1"]

    expected_data = pd.DataFrame({
        "my_index": ["a", "b"],
        "header 1": ["row 1 col 1", "row 2 col 1"],
        "header 2": ["row 1 col 2", "row 2 col 2"],
    }).set_index("my_index")

    pd.testing.assert_frame_equal(data, expected_data)

  def test_loading_data_with_only_column_names_and_empty_row_returns_expected_data(
      self,
  ):
    spreadsheet = self.client.create("test_sheet")
    spreadsheet.add_worksheet("Sheet2", rows=2, cols=3)
    spreadsheet.worksheet("Sheet2").update(
        [["my_index", "header 1", "header 2"]]
    )
    spreadsheet.worksheet("Sheet2").freeze(cols=1)  # Indexes are frozen columns

    google_sheet = sheets.GoogleSheet.load(spreadsheet.url)
    data = google_sheet["Sheet2"]

    expected_data = pd.DataFrame(
        columns=[
            "my_index",
            "header 1",
            "header 2",
        ]
    ).set_index("my_index")

    pd.testing.assert_frame_equal(data, expected_data)

  def test_loading_data_with_only_column_names_returns_expected_data(self):
    spreadsheet = self.client.create("test_sheet")
    spreadsheet.add_worksheet("Sheet2", rows=1, cols=3)
    spreadsheet.worksheet("Sheet2").update(
        [["my_index", "header 1", "header 2"]]
    )
    spreadsheet.worksheet("Sheet2").freeze(cols=1)  # Indexes are frozen columns

    google_sheet = sheets.GoogleSheet.load(spreadsheet.url)
    data = google_sheet["Sheet2"]

    expected_data = pd.DataFrame(
        columns=[
            "my_index",
            "header 1",
            "header 2",
        ]
    ).set_index("my_index")

    pd.testing.assert_frame_equal(data, expected_data)

  def test_writing_data_writes_to_sheet(self):
    google_sheet = sheets.GoogleSheet.new("test_sheet")
    data = pd.DataFrame({
        "my_index": ["a", "b"],
        "header 1": ["row 1 col 1", "row 2 col 1"],
        "header 2": ["row 1 col 2", "row 2 col 2"],
    }).set_index("my_index")

    google_sheet["Sheet1"] = data

    spreadsheet = self.client.open_by_url(google_sheet.url)
    worksheet = spreadsheet.worksheet("Sheet1")
    self.assertListEqual(
        worksheet._data,
        [
            ["my_index", "header 1", "header 2"],
            ["a", "row 1 col 1", "row 1 col 2"],
            ["b", "row 2 col 1", "row 2 col 2"],
        ],
    )

  def test_writing_data_updates_size_of_worksheet_to_match_data(self):
    google_sheet = sheets.GoogleSheet.new("test_sheet")
    spreadsheet = self.client.open_by_url(google_sheet.url)
    worksheet = spreadsheet.worksheet("Sheet1")

    self.assertEqual(worksheet.row_count, 1000)
    self.assertEqual(worksheet.col_count, 26)

    google_sheet["Sheet1"] = pd.DataFrame({
        "my_index": ["a", "b"],
        "header 1": ["row 1 col 1", "row 2 col 1"],
        "header 2": ["row 1 col 2", "row 2 col 2"],
    }).set_index("my_index")

    self.assertEqual(worksheet.row_count, 3)
    self.assertEqual(worksheet.col_count, 3)

  def test_writing_sets_format_of_column_names(self):
    google_sheet = sheets.GoogleSheet.new("test_sheet")

    google_sheet["Sheet1"] = pd.DataFrame({
        "my_index": ["a", "b"],
        "header 1": ["row 1 col 1", "row 2 col 1"],
        "header 2": ["row 1 col 2", "row 2 col 2"],
    }).set_index("my_index")

    spreadsheet = self.client.open_by_url(google_sheet.url)
    worksheet = spreadsheet.worksheet("Sheet1")

    for cell_format in worksheet._formatting[0]:
      # First row should be formatted like the header
      self.assertDictEqual(cell_format, sheets.HEADING_FORMAT)

    for row_format in worksheet._formatting[1:]:
      for cell_format in row_format:
        # All other rows should not be formatted
        self.assertDictEqual(cell_format, {})

  def test_writing_freezes_the_index_and_columns(self):
    google_sheet = sheets.GoogleSheet.new("test_sheet")
    spreadsheet = self.client.open_by_url(google_sheet.url)
    worksheet = spreadsheet.worksheet("Sheet1")

    self.assertEqual(worksheet.frozen_row_count, 0)
    self.assertEqual(worksheet.frozen_col_count, 0)

    google_sheet["Sheet1"] = pd.DataFrame({
        "my_index": ["a", "b"],
        "header 1": ["row 1 col 1", "row 2 col 1"],
        "header 2": ["row 1 col 2", "row 2 col 2"],
    }).set_index("my_index")

    self.assertEqual(worksheet.frozen_row_count, 1)
    self.assertEqual(worksheet.frozen_col_count, 1)

  def test_writing_data_adds_worksheet_if_needed(self):
    google_sheet = sheets.GoogleSheet.new("test_sheet")
    spreadsheet = self.client.open_by_url(google_sheet.url)

    worksheet_names = [sheet.title for sheet in spreadsheet.worksheets()]
    self.assertListEqual(worksheet_names, ["Sheet1"])

    google_sheet["Sheet2"] = pd.DataFrame({
        "my_index": ["a", "b"],
        "header 1": ["row 1 col 1", "row 2 col 1"],
        "header 2": ["row 1 col 2", "row 2 col 2"],
    }).set_index("my_index")

    worksheet_names = [sheet.title for sheet in spreadsheet.worksheets()]
    self.assertListEqual(worksheet_names, ["Sheet1", "Sheet2"])

  def test_writing_changed_data_overwrites_existing_data(self):
    google_sheet = sheets.GoogleSheet.new("test_sheet")
    google_sheet["Sheet1"] = pd.DataFrame({
        "my_index": ["a", "b", "c", "d"],
        "header 1": ["1", "2", "3", "4"],
        "header 2": ["5", "6", "7", "8"],
    }).set_index("my_index")

    # Some rows changed, some rows added, some rows unchanged
    new_data = pd.DataFrame({
        "my_index": ["a", "b change", "c", "d change", "e"],
        "header 1": ["1 change", "2", "3", "4 change", "9"],
        "header 2": ["5", "6 change", "7", "8", "10"],
    }).set_index("my_index")
    google_sheet["Sheet1"] = new_data

    pd.testing.assert_frame_equal(google_sheet["Sheet1"], new_data)

  def test_writing_data_with_different_columns_overwrites_existing_data(self):
    google_sheet = sheets.GoogleSheet.new("test_sheet")
    google_sheet["Sheet1"] = pd.DataFrame({
        "my_index": ["a", "b", "c", "d"],
        "header 1": ["1", "2", "3", "4"],
        "header 2": ["5", "6", "7", "8"],
    }).set_index("my_index")

    # Column name changed
    new_data = pd.DataFrame({
        "my_index": ["a", "b", "c", "d"],
        "header 1 changed": ["1", "2", "3", "4"],
        "header 2": ["5", "6", "7", "8"],
    }).set_index("my_index")
    google_sheet["Sheet1"] = new_data

    pd.testing.assert_frame_equal(google_sheet["Sheet1"], new_data)

  def test_delete_worksheet_deletes_the_worksheet(self):
    google_sheet = sheets.GoogleSheet.new("test_sheet")
    google_sheet["Sheet2"] = pd.DataFrame({
        "my_index": ["a", "b", "c", "d"],
        "header 1": ["1", "2", "3", "4"],
        "header 2": ["5", "6", "7", "8"],
    }).set_index("my_index")

    self.assertIn("Sheet2", google_sheet)
    google_sheet.delete_worksheet("Sheet2")
    self.assertNotIn("Sheet2", google_sheet)


class GoogleSheetLoggerTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()
    self.gspread_patcher = mock_gspread.PatchGspread()
    self.gspread_patcher.start()

    dummy_credentials = "dummy_credentials"
    sheets.set_google_auth_credentials(dummy_credentials)
    self.client = gspread.authorize(dummy_credentials)

  def tearDown(self):
    super().tearDown()
    self.gspread_patcher.stop()

  def test_can_write_logs_if_logs_tab_does_not_exist(self):
    spreadsheet = self.client.create("test_spreadsheet")

    logger = logging.getLogger("test_logger")
    handler = sheets.GoogleSheetsHandler(spreadsheet.url)
    handler.setLevel(logging.INFO)
    logger.handlers = []
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("test info message")
    logger.warning("test warning message")
    logger.error("test error message")
    logger.critical("test critical message")

    worksheet = spreadsheet.worksheet("Logs")
    data_without_timestamp_col = [row[1:] for row in worksheet._data]
    timestamp_col = [row[0] for row in worksheet._data]

    self.assertListEqual(
        data_without_timestamp_col,
        [
            ["Log Level", "Logger Name", "Message"],
            ["CRITICAL", "test_logger", "test critical message"],
            ["ERROR", "test_logger", "test error message"],
            ["WARNING", "test_logger", "test warning message"],
            ["INFO", "test_logger", "test info message"],
            ["", "", ""],
        ],
    )
    self.assertEqual(timestamp_col[0], "UTC Timestamp")
    for timestamp in timestamp_col[1:-1]:
      dt.datetime.strptime(
          timestamp, "%Y-%m-%d %H:%M:%S"
      )  # Will raise if invalid format

  def test_adds_logs_if_logs_tab_exists(self):
    spreadsheet = self.client.create("test_spreadsheet")
    spreadsheet.add_worksheet("Logs", rows=3, cols=4)
    spreadsheet.worksheet("Logs").update(
        values=[
            sheets.GoogleSheetsLogSender.HEADINGS,
            [
                "2024-01-01 00:00:00",
                "INFO",
                "test_logger",
                "existing test info message",
            ],
        ],
    )

    logger = logging.getLogger("test_logger")
    handler = sheets.GoogleSheetsHandler(spreadsheet.url)
    handler.setLevel(logging.INFO)
    logger.handlers = []
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("new info message")

    worksheet = spreadsheet.worksheet("Logs")
    data_without_timestamp_col = [row[1:] for row in worksheet._data]

    self.assertListEqual(
        data_without_timestamp_col,
        [
            ["Log Level", "Logger Name", "Message"],
            ["INFO", "test_logger", "new info message"],
            ["INFO", "test_logger", "existing test info message"],
            ["", "", ""],
        ],
    )

  def test_raises_error_if_logs_tab_has_wrong_headings(self):
    spreadsheet = self.client.create("test_spreadsheet")
    spreadsheet.add_worksheet("Logs", rows=2, cols=4)
    spreadsheet.worksheet("Logs").update(
        values=[["Wrong", "Headings"]],
    )

    with self.assertRaises(ValueError):
      sheets.GoogleSheetsLogSender(spreadsheet.url)


class CreateTemplateCopycatSheetTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()
    self.gspread_patcher = mock_gspread.PatchGspread()
    self.gspread_patcher.start()

    dummy_credentials = "dummy_credentials"
    sheets.set_google_auth_credentials(dummy_credentials)
    self.client = gspread.authorize(dummy_credentials)

  def tearDown(self):
    super().tearDown()
    self.gspread_patcher.stop()

  def test_expected_number_of_rows_are_created_when_include_demo_data_is_true(
      self,
  ):
    url = sheets.create_template_copycat_sheet(include_demo_data=True)
    sheet = sheets.GoogleSheet.load(url)

    self.assertLen(sheet[sheets.TEMPLATE_EXISTING_ADS_WORKSHEET_NAME], 7)
    self.assertLen(sheet[sheets.TEMPLATE_NEW_KEYWORDS_WORKSHEET_NAME], 14)
    self.assertLen(sheet[sheets.TEMPLATE_EXTRA_INSTRUCTIONS_WORKSHEET_NAME], 1)

  def test_no_rows_are_created_when_include_demo_data_is_false(self):
    url = sheets.create_template_copycat_sheet(include_demo_data=False)
    sheet = sheets.GoogleSheet.load(url)

    self.assertEmpty(sheet[sheets.TEMPLATE_EXISTING_ADS_WORKSHEET_NAME])
    self.assertEmpty(sheet[sheets.TEMPLATE_NEW_KEYWORDS_WORKSHEET_NAME])
    self.assertEmpty(sheet[sheets.TEMPLATE_EXTRA_INSTRUCTIONS_WORKSHEET_NAME])

  @parameterized.parameters(True, False)
  def test_expected_columns_and_index_are_created(self, include_demo_data):
    url = sheets.create_template_copycat_sheet(
        include_demo_data=include_demo_data
    )
    sheet = sheets.GoogleSheet.load(url)

    self.assertListEqual(
        sheet[
            sheets.TEMPLATE_EXISTING_ADS_WORKSHEET_NAME
        ].columns.values.tolist(),
        [
            "URL",
            "Ad Strength",
            "Keywords",
            "Headline 1",
            "Headline 2",
            "Headline 3",
            "Headline 4",
            "Headline 5",
            "Headline 6",
            "Headline 7",
            "Headline 8",
            "Headline 9",
            "Headline 10",
            "Headline 11",
            "Headline 12",
            "Headline 13",
            "Headline 14",
            "Headline 15",
            "Description 1",
            "Description 2",
            "Description 3",
            "Description 4",
        ],
    )
    self.assertListEqual(
        sheet[
            sheets.TEMPLATE_NEW_KEYWORDS_WORKSHEET_NAME
        ].columns.values.tolist(),
        [
            "Keyword",
        ],
    )
    self.assertListEqual(
        sheet[
            sheets.TEMPLATE_EXTRA_INSTRUCTIONS_WORKSHEET_NAME
        ].columns.values.tolist(),
        [
            "Extra Instructions",
        ],
    )

    self.assertListEqual(
        sheet[sheets.TEMPLATE_EXISTING_ADS_WORKSHEET_NAME].index.names,
        ["Campaign ID", "Ad Group"],
    )
    self.assertListEqual(
        sheet[sheets.TEMPLATE_NEW_KEYWORDS_WORKSHEET_NAME].index.names,
        ["Campaign ID", "Ad Group"],
    )
    self.assertListEqual(
        sheet[sheets.TEMPLATE_EXTRA_INSTRUCTIONS_WORKSHEET_NAME].index.names,
        ["Campaign ID", "Ad Group", "Version"],
    )


if __name__ == "__main__":
  absltest.main()
