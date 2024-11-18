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

"""Contains the sub-page for loading data into Copycat and validating it."""

import mesop as me

from copycat.ui import components
from copycat.ui import event_handlers
from copycat.ui import states


def prepare_data() -> None:
  """Creates the sub-page for loading data into Copycat and validating it."""
  state = me.state(states.AppState)
  with components.column(width="100%"):
    with components.rounded_box_section(
        title="Validate Google Sheet", width="100%"
    ):
      me.text(
          "The data in the Google Sheet must contain three worksheets,"
          " 'Training Ads', 'New Keywords' and 'Extra Instructions for New"
          " Ads', and they must follow the expected format exactly. This is"
          " especially important to check if you have created the Google Sheet"
          " manually. Make sure all the column names are correct and in the"
          " correct order, and that the correct number of columns and rows are"
          " frozen in the google sheet. To see what is expected, select New /"
          " Load and then create a new Google Sheet and check the columns it"
          " contains."
      )
      me.text(
          "If the validation fails, you should check the Logs tab of your"
          " Google Sheet to see which rows are invalid and why.",
          style=me.Style(margin=me.Margin(top=15)),
      )

      with components.row(align_items="center"):
        me.button(
            label="Validate Sheet",
            type="flat",
            on_click=event_handlers.validate_sheet,
            style=me.Style(margin=me.Margin.symmetric(vertical=20)),
        )
        if state.google_sheet_is_valid:
          me.icon("check_circle")
          me.text("Validated")
        else:
          me.icon("warning", style=me.Style(color=me.theme_var("error")))
          me.text("Not Validated", style=me.Style(color=me.theme_var("error")))
