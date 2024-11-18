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

"""The main entrypoint for the Copycat UI."""

import logging

import mesop as me

from copycat.ui import components
from copycat.ui import event_handlers
from copycat.ui import generate_ads_page
from copycat.ui import new_instance_page
from copycat.ui import prepare_data_page
from copycat.ui import setup_page
from copycat.ui import states
from copycat.ui import style_guide_page
from copycat.ui import styles
from copycat.ui import sub_pages


all_sub_pages = sub_pages.SubPages()
all_sub_pages.add_page(
    setup_page.setup,
    nav_text="Setup",
    nav_icon="settings",
)
all_sub_pages.add_page(
    prepare_data_page.prepare_data,
    nav_text="Prepare Data",
    nav_icon="download",
)
all_sub_pages.add_page(
    new_instance_page.new_instance,
    nav_text="New Copycat Instance",
    nav_icon="smart_toy",
)
all_sub_pages.add_page(
    style_guide_page.style_guide, nav_text="Style Guide", nav_icon="edit_note"
)
all_sub_pages.add_page(
    generate_ads_page.generate_new_ads,
    nav_text="Generate New Ads",
    nav_icon="bolt",
)


def starting_dialog(state: states.AppState):
  """The dialog that is shown when the user first opens the UI.

  This is also shown when they want to load a new Google Sheet.

  Args:
    state: The AppState.
  """
  with components.dialog(is_open=state.show_starting_dialog):
    if state.google_sheet_url:
      # Can close if there is already a google sheet URL.
      with me.content_button(
          type="icon",
          on_click=event_handlers.close_starting_dialog,
      ):
        me.icon("close", style=me.Style(color=me.theme_var("outline-variant")))

    with components.column(align_items="center", width="100%", gap=0):
      me.text("Welcome to Copycat", type="headline-5")
      me.text(
          "Please select a Google Sheet to load, or create a new one. Note:"
          " after entering the name or URL, you may first need to click outside"
          " the input box for the buttons to activate.",
          style=me.Style(width=500),
      )
      me.text(
          "WARNING: The data in the Google Sheet you use can be edited by"
          " Copycat, so if you have your data in another google sheet, it's"
          " best to select 'Create New Sheet' here and then copy the data to"
          " the new sheet. Only load an existing sheet if it was a previous"
          " Copycat sheet that you want to continue working on.",
          style=me.Style(
              margin=me.Margin.all(15),
              color=me.theme_var("error"),
              width=400,
              border=me.Border.all(
                  me.BorderSide(
                      width=1, color=me.theme_var("error"), style="solid"
                  )
              ),
              text_align="center",
          ),
          type="body-2",
      )
      with components.row(width="100%", margin=me.Margin(top=15), gap=0):
        with components.column(
            align_items="center",
            width="50%",
            gap=0,
            border=me.Border(right=styles.DEFAULT_BORDER_STYLE),
        ):
          me.text("Create New Sheet", type="headline-6")
          me.input(
              label="Google Sheet Name",
              key="new_google_sheet_name",
              on_blur=event_handlers.update_app_state_parameter,
              value=state.new_google_sheet_name,
              appearance="outline",
              style=me.Style(
                  width="100%",
                  padding=me.Padding.all(0),
              ),
          )
          with components.row(align_items="center"):
            me.button(
                "New",
                type="flat",
                disabled=not state.new_google_sheet_name,
                on_click=event_handlers.create_new_google_sheet,
            )
            me.checkbox(
                label="Include Demo Data",
                key="new_google_sheet_include_demo_data",
                on_change=event_handlers.update_app_state_parameter_checkbox,
                checked=state.new_google_sheet_include_demo_data,
                disabled=not state.new_google_sheet_name,
            )
        with components.column(align_items="center", width="50%", gap=0):
          me.text("Load Existing Sheet", type="headline-6")
          me.input(
              label="Google Sheet URL",
              key="new_google_sheet_url",
              on_blur=event_handlers.update_app_state_parameter,
              value=state.new_google_sheet_url,
              type="url",
              appearance="outline",
              style=me.Style(
                  width="100%",
                  padding=me.Padding.all(0),
              ),
          )
          me.button(
              "Load",
              type="flat",
              disabled=not state.new_google_sheet_url,
              on_click=event_handlers.load_existing_google_sheet,
          )


def main_copycat_header(state: states.AppState):
  """The header bar that is shown at the top of the UI.

  It contains the Copycat name, the Google Sheet URL, buttons to save and
  load the parameters from the Google Sheet, and a drop down to select the
  logging level.

  Args:
    state: The AppState.
  """

  with components.header_bar(
      border=me.Border.symmetric(vertical=styles.DEFAULT_BORDER_STYLE)
  ):
    with components.header_section():
      me.text(
          "Copycat",
          type="headline-3",
          style=me.Style(margin=me.Margin(bottom=0)),
      )

    with components.header_section():
      me.text(
          "Google Sheet URL",
          type="headline-6",
          style=me.Style(margin=me.Margin(bottom=0)),
      )
      me.input(
          label="URL",
          value=state.google_sheet_url,
          type="url",
          appearance="outline",
          style=me.Style(
              width=500,
              padding=me.Padding.all(0),
              margin=me.Margin(top=20),
          ),
          readonly=True,
      )
      with me.content_button(
          style=me.Style(
              padding=me.Padding.symmetric(vertical=30, horizontal=25)
          ),
          on_click=event_handlers.save_params_to_google_sheet,
      ):
        me.icon("save")
        me.text("Save")

      with me.content_button(
          style=me.Style(
              padding=me.Padding.symmetric(vertical=30, horizontal=25)
          ),
          on_click=event_handlers.open_starting_dialog,
      ):
        me.icon("add_circle")
        me.text("New / Load")

      with me.content_button(
          style=me.Style(
              padding=me.Padding.symmetric(vertical=30, horizontal=25)
          ),
          on_click=event_handlers.show_hide_google_sheet,
      ):
        if state.display_google_sheet:
          me.icon("visibility_off")
          me.text("Hide Preview")
        else:
          me.icon("visibility")
          me.text("Show Preview")

    with components.header_section():
      me.select(
          label="Log Level",
          options=[
              me.SelectOption(label="DEBUG", value=str(logging.DEBUG)),
              me.SelectOption(label="INFO", value=str(logging.INFO)),
              me.SelectOption(label="ERROR", value=str(logging.ERROR)),
              me.SelectOption(label="CRITICAL", value=str(logging.CRITICAL)),
          ],
          on_selection_change=event_handlers.update_log_level,
          multiple=False,
          value=str(state.log_level),
          style=me.Style(
              padding=me.Padding.all(0),
              margin=me.Margin(top=20),
          ),
      )


def body_and_google_sheet_preview(state: states.AppState):
  """The main body of the UI.

  It contains the sub pages (left), and the Google Sheet preview if it is
  enabled (right).

  Args:
    state: The AppState.
  """

  with components.row(
      gap=0,
      height="100%",
      width="100%",
  ):
    all_sub_pages.render(
        height="100%",
        width="50%" if state.display_google_sheet else "100%",
        gap=0,
        border=me.Border(right=styles.DEFAULT_BORDER_STYLE),
    )

    # Google Sheet
    if state.display_google_sheet:
      with me.box(
          style=me.Style(
              height="100%",
              width="50%",
          )
      ):
        me.embed(
            src=state.google_sheet_url,
            style=me.Style(width="100%", height="100%"),
        )


@me.page(path="/")
def home():
  """The home page of the Copycat UI.

  This contains all the scaffolding for the UI, but the actual content is
  rendered by the sub-pages.
  """
  state = me.state(states.AppState)

  starting_dialog(state)
  components.snackbar(
      snackbar_is_visible_name="show_copycat_instance_created_snackbar",
      label=(
          "Copycat instance successfully created. You can now generate a style"
          " guide and new ads."
      ),
      action_label="Okay",
  )
  components.snackbar(
      snackbar_is_visible_name="show_ad_copy_generated_snackbar",
      label=(
          "Ad copy generation complete. You can view the generated ads in the"
          " Google Sheet in the 'Generated Ads' tab."
      ),
      action_label="Okay",
  )

  with components.column(height="100%", width="100%", gap=0):
    main_copycat_header(state)
    body_and_google_sheet_preview(state)
