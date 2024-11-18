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

"""A mock gspread client for testing."""

from typing import Any

import gspread
import mock

MOCK_SHEETS_URL_PREFIX = "https://mock.sheets.com/spreadsheet/"


def _empty_formatting(n_rows: int, n_cols: int):
  return [[{} for _ in range(n_cols)] for _ in range(n_rows)]


def _empty_data(n_rows: int, n_cols: int):
  return [["" for _ in range(n_cols)] for _ in range(n_rows)]


class MockWorksheet:
  """A mock gspread worksheet for testing.

  This mock is not comprehensive, it just covers the functionality that is used
  by the Copycat library.
  """

  def __init__(
      self,
      title: str,
      data: list[list[Any]],
      formatting: list[list[dict[str, Any]]],
      frozen_col_count: int = 0,
      frozen_row_count: int = 0,
  ):
    """Initialises the mock worksheet."""
    self.title = title
    self._data = data
    self._formatting = formatting
    self._frozen_col_count = frozen_col_count
    self._frozen_row_count = frozen_row_count

  @property
  def frozen_col_count(self) -> int:
    return self._frozen_col_count

  @property
  def frozen_row_count(self) -> int:
    return self._frozen_row_count

  @property
  def row_count(self) -> int:
    return len(self._data)

  @property
  def col_count(self) -> int:
    return len(self._data[0])

  def get_all_records(self, *args, **kwargs) -> list[dict[str, Any]]:
    """Returns all the records in the worksheet."""
    columns = list(filter(None, self._data[0]))
    rows = list(filter(None, [row[: len(columns)] for row in self._data[1:]]))

    # Find the index of the first non-empty row (counting backwards).
    for i, row in enumerate(rows[::-1]):
      # Start at the end of the worksheet and work backwards.
      if list(filter(None, row)):
        # Stop counting at the first non-empty row.
        break
    else:
      # If there are no non-empty rows, set i to the length of the rows list.
      i = len(rows)

    # Remove the empty rows from the end of the worksheet.
    last_idx = len(rows) - i
    rows = rows[:last_idx]

    return [dict(zip(columns, row)) for row in rows]

  def clear(self) -> None:
    """Clears the worksheet."""
    self._data = _empty_data(self.row_count, self.col_count)
    self._formatting = _empty_formatting(self.row_count, self.col_count)

  def freeze(self, rows: int | None = None, cols: int | None = None) -> None:
    """Freezes the given number of rows and columns."""
    if rows and rows > self.row_count:
      raise ValueError(
          "Cannot freeze more rows than there are in the worksheet"
      )
    if cols and cols > self.col_count:
      raise ValueError(
          "Cannot freeze more columns than there are in the worksheet"
      )

    if rows is not None:
      self._frozen_row_count = rows
    if cols is not None:
      self._frozen_col_count = cols

  def format(self, ranges: str | list[str], format: dict[str, Any]) -> None:
    """Formats the given range with the given format."""
    if isinstance(ranges, str):
      ranges = [ranges]

    for range_str in ranges:
      grid_range = gspread.utils.a1_range_to_grid_range(range_str)
      default_grid_range = {
          "startRowIndex": 0,
          "endRowIndex": self.row_count,
          "startColumnIndex": 0,
          "endColumnIndex": self.col_count,
      }
      grid_range = default_grid_range | grid_range

      start_row = grid_range["startRowIndex"]
      end_row = grid_range["endRowIndex"]
      start_col = grid_range["startColumnIndex"]
      end_col = grid_range["endColumnIndex"]

      for row in range(start_row, end_row):
        for col in range(start_col, end_col):
          self._formatting[row][col].update(format)

  def add_rows(self, rows: int) -> None:
    """Adds empty rows to the worksheet."""
    self._data.extend(_empty_data(rows, self.col_count))
    self._formatting.extend(_empty_formatting(rows, self.col_count))

  def delete_rows(self, start_index: int, end_index: int | None = None) -> None:
    """Deletes rows from the worksheet."""
    if end_index is None:
      end_index = start_index

    self._data = self._data[:start_index] + self._data[end_index + 1 :]
    self._formatting = (
        self._formatting[:start_index] + self._formatting[end_index + 1 :]
    )

  def add_cols(self, n_cols: int) -> None:
    """Adds n_cols to the worksheet."""
    new_cols_data = _empty_data(self.row_count, n_cols)
    new_cols_formatting = _empty_formatting(self.row_count, n_cols)

    for i in range(self.row_count):
      self._data[i].extend(new_cols_data[i])
      self._formatting[i].extend(new_cols_formatting[i])

  def delete_columns(
      self, start_index: int, end_index: int | None = None
  ) -> None:
    """Deletes columns from the worksheet."""
    if end_index is None:
      end_index = start_index

    for i in range(self.row_count):
      self._data[i] = (
          self._data[i][:start_index] + self._data[i][end_index + 1 :]
      )
      self._formatting[i] = (
          self._formatting[i][:start_index]
          + self._formatting[i][end_index + 1 :]
      )

  def update(
      self,
      values: list[list[Any]],
      range_name: str | None = None,
      *args,
      **kwargs
  ) -> None:
    """Updates the data in the worksheet."""
    if range_name is None:
      start_row = 0
      start_col = 0
      target_rows = self.row_count
      target_cols = self.col_count
    else:
      grid_range = gspread.utils.a1_range_to_grid_range(range_name)
      default_grid_range = {
          "startRowIndex": 0,
          "endRowIndex": self.row_count,
          "startColumnIndex": 0,
          "endColumnIndex": self.col_count,
      }
      grid_range = default_grid_range | grid_range

      grid_range["endRowIndex"] = min(grid_range["endRowIndex"], self.row_count)
      grid_range["endColumnIndex"] = min(
          grid_range["endColumnIndex"], self.col_count
      )
      target_rows = grid_range["endRowIndex"] - grid_range["startRowIndex"]
      target_cols = (
          grid_range["endColumnIndex"] - grid_range["startColumnIndex"]
      )

      start_row = grid_range["startRowIndex"]
      start_col = grid_range["startColumnIndex"]

    if target_rows < len(values):
      raise ValueError(
          "Cannot update more rows than there are in the worksheet / range"
      )
    if target_cols < len(values[0]):
      raise ValueError(
          "Cannot update more columns than there are in the worksheet / range"
      )

    for i, row in enumerate(values):
      for j, cell in enumerate(row):
        self._data[start_row + i][start_col + j] = cell

  def batch_update(
      self, batches: list[dict[str, str | list[list[Any]]]]
  ) -> None:
    """Updates the data in the worksheet in batches."""
    for batch in batches:
      self.update(batch["values"], range_name=batch["range"])

  def insert_row(self, values: list[Any], index: int) -> None:
    """Inserts a row at the given index.

    Args:
      values: The values to insert into the row.
      index: The index to insert the row at. The index starts at 1, so the first
        row is row 1.
    """
    if len(values) > self.col_count:
      self.add_cols(len(values) - self.col_count)
    if len(values) < self.col_count:
      values.extend(_empty_data(1, self.col_count - len(values))[0])

    self._data.insert(index - 1, values)
    self._formatting.insert(index, _empty_formatting(1, self.col_count)[0])

  def row_values(self, index: int) -> list[Any]:
    """Returns the values in the given row.

    Args:
      index: The index of the row to return. The index starts at 1, so the first
        row is row 1.
    """
    return self._data[index - 1]


class MockSpreadsheet:
  """A mock gspread spreadsheet for testing.

  This mock is not comprehensive, it just covers the functionality that is used
  by the Copycat library.
  """

  def __init__(self, title: str):
    self.title = title
    self.url = MOCK_SHEETS_URL_PREFIX + title
    self._worksheets = {}

    self.add_worksheet("Sheet1")

  def worksheet(self, title: str) -> MockWorksheet:
    """Returns the worksheet with the given name."""
    return self._worksheets[title]

  def worksheets(self) -> list[MockWorksheet]:
    """Returns the worksheets in the spreadsheet."""
    return list(self._worksheets.values())

  def add_worksheet(
      self, title: str, rows: int = 1000, cols: int = 26
  ) -> MockWorksheet:
    """Adds an empty worksheet to the spreadsheet."""
    data = _empty_data(rows, cols)
    formatting = _empty_formatting(rows, cols)
    self._worksheets[title] = MockWorksheet(
        title, data=data, formatting=formatting
    )
    return self.worksheet(title)

  def del_worksheet(self, worksheet: MockWorksheet) -> None:
    """Deletes the given worksheet from the spreadsheet."""
    self._worksheets.pop(worksheet.title)


class MockGspreadClient:
  """A mock gspread client for testing.

  This mock is not comprehensive, it just covers the functionality that is used
  by the Copycat library.
  """

  def __init__(self):
    self._spreadsheets = {}

  def create(self, title: str) -> MockSpreadsheet:
    """Creates a mock spreadsheet."""
    new_sheet = MockSpreadsheet(title)
    self._spreadsheets[new_sheet.url] = new_sheet
    return new_sheet

  def open_by_url(self, url: str) -> MockSpreadsheet:
    """Opens a mock spreadsheet by URL."""
    if url not in self._spreadsheets:
      raise gspread.SpreadsheetNotFound("Invalid URL")

    return self._spreadsheets[url]


class PatchGspread:
  """This objects handles the patching of gspread.

  This allows us to run tests without connecting to google sheets. It will
  return a mock gspread client which can handle reading and writing data
  locally.

  Context manager:
  ```
  with testing_utils.PatchGspread() as gspread_patcher:
    creds, _ = google.auth.default()
    client = gspread.authorize(creds)
  ```

  Manually calling start and stop:
  ```
  patcher = PatchGspread()
  patcher.start()
  creds, _ = google.auth.default()
  client = gspread.authorize(creds)
  patcher.stop()
  ```
  """

  def __init__(self):
    self.mock_client = MockGspreadClient()
    self._gspread_authorize_patcher = mock.patch(
        "gspread.authorize",
        return_value=self.mock_client,
    )

  def start(self):
    self.mock_gspread_authorize = self._gspread_authorize_patcher.start()

  def stop(self):
    self._gspread_authorize_patcher.stop()

  def __enter__(self) -> "PatchGspread":
    self.start()
    return self

  def __exit__(self, *args, **kwargs):
    self.stop()
