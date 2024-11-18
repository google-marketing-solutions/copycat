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

import mesop as me

from copycat import copycat
from copycat.ui import components
from copycat.ui import event_handlers
from copycat.ui import states
from copycat.ui import styles


_NEW_ADS_PREVIEW_STYLE = me.Style(
    overflow_y="scroll",
    padding=me.Padding.all(20),
    width="100%",
    height=300,
    border=me.Border.all(
        styles.DEFAULT_BORDER_STYLE,
    ),
    border_radius=6,
)


def generation_settings_section(params: states.CopycatParamsState) -> None:
  """Renders the chat model parameters section of the generate new ads page."""
  with components.rounded_box_section(
      title="Generation Settings", width="100%"
  ):
    me.text("Chat Model:")
    me.radio(
        on_change=event_handlers.update_copycat_parameter,
        key="new_ads_chat_model_name",
        options=[
            me.RadioOption(
                label="Gemini 1.5 Flash",
                value=copycat.ModelName.GEMINI_1_5_FLASH.value,
            ),
            me.RadioOption(
                label="Gemini 1.5 Pro",
                value=copycat.ModelName.GEMINI_1_5_PRO.value,
            ),
        ],
        value=params.new_ads_chat_model_name,
        style=me.Style(margin=me.Margin(bottom=10)),
    )
    with me.box(style=me.Style(margin=me.Margin(bottom=20))):
      me.slide_toggle(
          label="Use Style Guide",
          on_change=event_handlers.update_copycat_parameter_from_slide_toggle,
          key="new_ads_use_style_guide",
          checked=params.new_ads_use_style_guide,
      )

    with components.row(width="100%"):
      with me.box(
          style=me.Style(width="45%", margin=me.Margin.symmetric(horizontal=5))
      ):
        me.input(
            label="N In-context Examples",
            on_blur=event_handlers.update_copycat_parameter,
            key="new_ads_num_in_context_examples",
            value=str(params.new_ads_num_in_context_examples),
            appearance="outline",
            type="number",
            style=me.Style(width="100%"),
        )
      with me.box(
          style=me.Style(width="45%", margin=me.Margin.symmetric(horizontal=5))
      ):
        me.input(
            label="Temperature",
            on_blur=event_handlers.update_copycat_parameter,
            key="new_ads_temperature",
            value=str(params.new_ads_temperature),
            appearance="outline",
            type="number",
            style=me.Style(width="100%"),
        )

    with components.row(width="100%"):
      with me.box(
          style=me.Style(width="45%", margin=me.Margin.symmetric(horizontal=5))
      ):
        me.input(
            label="Top-K",
            on_blur=event_handlers.update_copycat_parameter,
            key="new_ads_top_k",
            value=str(params.new_ads_top_k),
            appearance="outline",
            type="number",
            style=me.Style(width="100%"),
        )
      with me.box(
          style=me.Style(width="45%", margin=me.Margin.symmetric(horizontal=5))
      ):
        me.input(
            label="Top-P",
            on_blur=event_handlers.update_copycat_parameter,
            key="new_ads_top_p",
            value=str(params.new_ads_top_p),
            appearance="outline",
            type="number",
            style=me.Style(width="100%"),
        )

    with components.row(gap=10, margin=me.Margin(bottom=20)):
      me.slide_toggle(
          label="Allow memorised headlines",
          on_change=event_handlers.update_copycat_parameter_from_slide_toggle,
          key="new_ads_allow_memorised_headlines",
          checked=params.new_ads_allow_memorised_headlines,
      )
      me.slide_toggle(
          label="Allow memorised descriptions",
          on_change=event_handlers.update_copycat_parameter_from_slide_toggle,
          key="new_ads_allow_memorised_descriptions",
          checked=params.new_ads_allow_memorised_descriptions,
      )

    with components.row():
      with me.box(
          style=me.Style(width="45%", margin=me.Margin.symmetric(horizontal=5))
      ):
        me.input(
            label="Number of Versions per Ad Group",
            on_blur=event_handlers.update_copycat_parameter,
            key="new_ads_number_of_versions",
            value=str(params.new_ads_number_of_versions),
            appearance="outline",
            type="number",
            style=me.Style(width="100%"),
        )


def preview_prompt_section(state: states.AppState) -> None:
  """Renders the preview prompt section of the generate new ads page."""
  with components.rounded_box_section(title="Preview Prompt", width="100%"):
    me.text(
        "Preview the prompt and settings that will be used to generate the"
        " first ad."
    )
    with components.row(
        gap=15,
        align_items="center",
        margin=me.Margin.symmetric(vertical=15),
    ):
      me.button(
          label="Preview",
          type="flat",
          disabled=not state.has_copycat_instance,
          on_click=event_handlers.generate_new_ad_preview,
      )
    if state.new_ad_preview_request:
      with me.box(style=_NEW_ADS_PREVIEW_STYLE):
        me.markdown(state.new_ad_preview_request, style=me.Style(height="40%"))


def generate_new_ads_section(
    params: states.CopycatParamsState, state: states.AppState
) -> None:
  """Renders the generate new ads section of the generate new ads page."""
  with components.rounded_box_section(title="Generate Ads", width="100%"):
    me.text(
        "Copycat will generate ads in batches. The batch size is the number of"
        " ads to generate at a time, and the limit is the total number of ads"
        " to generate. For example, a batch size of 15 and a limit of 25 would"
        " mean two batches are generated, the first 15 ads and then the next 10"
        " ads. The ads will be written to the Google Sheet in a tab named"
        " 'Generated Ads'"
    )
    with components.row(gap=15, align_items="center", margin=me.Margin(top=15)):
      with me.tooltip(
          message=(
              "The batch size for generating ads. A larger batch size will"
              " finish faster but you may hit your quota limit."
          )
      ):
        me.input(
            label="Batch Size",
            value=str(params.new_ads_batch_size),
            type="number",
            appearance="outline",
            style=me.Style(width=100),
            on_blur=event_handlers.update_copycat_parameter,
            key="new_ads_batch_size",
        )
      with me.tooltip(
          message=(
              "The maximum number of ads to generate. If 0 then there is no"
              " limit."
          )
      ):
        me.input(
            label="Limit",
            value=str(params.new_ads_generation_limit),
            type="number",
            appearance="outline",
            style=me.Style(width=100),
            on_blur=event_handlers.update_copycat_parameter,
            key="new_ads_generation_limit",
        )
    with components.row(gap=15, align_items="center", margin=me.Margin(top=15)):
      me.button(
          label="Generate",
          type="flat",
          disabled=not state.has_copycat_instance,
          on_click=event_handlers.generate_ads,
      )
      me.slide_toggle(
          label="Fill Gaps",
          on_change=event_handlers.update_copycat_parameter_from_slide_toggle,
          key="new_ads_fill_gaps",
          checked=params.new_ads_fill_gaps,
      )


def generate_new_ads() -> None:
  """Renders the generate new ads page."""
  state = me.state(states.AppState)
  params = me.state(states.CopycatParamsState)

  with components.column(gap=15, width="50%"):
    with components.row(width="100%"):
      generation_settings_section(params)

  with components.column(gap=15, width="50%"):
    with components.row(width="100%"):
      preview_prompt_section(state)

    with components.row(width="100%"):
      generate_new_ads_section(params, state)
