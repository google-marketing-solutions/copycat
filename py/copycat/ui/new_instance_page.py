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


def advertiser_info_section(params: states.CopycatParamsState) -> None:
  """Renders the advertiser info section of the new instance page."""
  me.text(
      "Advertising Info:", style=me.Style(margin=me.Margin(bottom=15))
  )
  with components.row():
    me.input(
        label="Company Name",
        key="company_name",
        on_blur=event_handlers.update_copycat_parameter,
        value=params.company_name,
        appearance="outline",
        style=me.Style(margin=me.Margin.symmetric(horizontal=5)),
    )

    me.input(
        label="Ad Copy Language",
        on_blur=event_handlers.language_on_blur,
        value=params.language,
        appearance="outline",
        style=me.Style(margin=me.Margin.symmetric(horizontal=5)),
    )

  me.text("Ad Format:")
  me.radio(
      on_change=event_handlers.ad_format_on_change,
      options=[
          me.RadioOption(
              label="Responsive Search Ads", value="responsive_search_ad"
          ),
          me.RadioOption(label="Text Ads", value="text_ad"),
          me.RadioOption(label="Custom", value="custom"),
      ],
      value=params.ad_format,
      style=me.Style(margin=me.Margin(bottom=15)),
  )

  ad_format_is_not_custom = params.ad_format != "custom"
  with components.row():
    me.input(
        label="Max Headlines",
        key="max_headlines",
        on_blur=event_handlers.update_copycat_parameter,
        value=str(params.max_headlines),
        type="number",
        appearance="outline",
        disabled=ad_format_is_not_custom,
        style=me.Style(margin=me.Margin.symmetric(horizontal=5)),
    )

    me.input(
        label="Max Descriptions",
        key="max_descriptions",
        on_blur=event_handlers.update_copycat_parameter,
        value=str(params.max_descriptions),
        type="number",
        appearance="outline",
        disabled=ad_format_is_not_custom,
        style=me.Style(margin=me.Margin.symmetric(horizontal=5)),
    )

  with me.tooltip(
      message=(
          "Special variables are things like Dynamic Keyword Insertion"
          " (DKI) or Customizers. If you don't want Copycat to use these"
          " features in your generated ads, then you should replace them"
          " with their default values. If you do want Copycat to use them"
          " then keep them in but make sure the Style Guide clearly"
          " explains how they should be used."
      )
  ):
    me.text("How to handle special variables:")
    me.radio(
        on_change=event_handlers.update_copycat_parameter,
        key="how_to_handle_special_variables",
        options=[
            me.RadioOption(
                label="Replace with default value", value="replace"
            ),
            me.RadioOption(label="Keep", value="keep"),
        ],
        value=params.how_to_handle_special_variables,
        style=me.Style(margin=me.Margin(bottom=15)),
    )

  me.text("How to handle invalid training ads:")
  me.radio(
      on_change=event_handlers.update_copycat_parameter,
      key="on_invalid_ad",
      options=[
          me.RadioOption(label="Drop", value="drop"),
          me.RadioOption(label="Skip", value="skip"),
          me.RadioOption(label="Raise", value="raise"),
      ],
      value=params.on_invalid_ad,
      style=me.Style(margin=me.Margin(bottom=15)),
  )


def copycat_creation_settings_section(params: states.CopycatParamsState) -> None:
  """Renders the Copycat creation settings section of the new instance page."""
  me.text("Embedding model:", style=me.Style(margin=me.Margin(bottom=15)))
  with components.row():
    with me.tooltip(
        message="Dimensionality of embeddings must be between 10 and 768."
    ):
      me.input(
          label="Dimensionality",
          on_blur=event_handlers.embedding_model_dimensionality_on_blur,
          value=str(params.embedding_model_dimensionality),
          type="number",
          appearance="outline",
          style=me.Style(margin=me.Margin.symmetric(horizontal=5)),
      )
    with me.tooltip(message="Batch size must be between 1 and 250."):
      me.input(
          label="Batch Size",
          key="embedding_model_batch_size",
          on_blur=event_handlers.update_copycat_parameter,
          value=str(params.embedding_model_batch_size),
          type="number",
          appearance="outline",
          style=me.Style(margin=me.Margin.symmetric(horizontal=5)),
      )

  me.text("Exemplar selection method:")
  with me.tooltip(
      message=(
          "Exemplars are selected either randomly, or using Affinity"
          " Propogation to find clusters of ads and select the ads that"
          " are the most representative of each cluster. We recommend"
          " Affinity Propagation."
      )
  ):
    me.radio(
        on_change=event_handlers.update_copycat_parameter,
        key="exemplar_selection_method",
        options=[
            me.RadioOption(
                label=v.value.replace("_", " ").title(), value=v.value
            )
            for v in copycat.ExemplarSelectionMethod
        ],
        value=params.exemplar_selection_method,
        style=me.Style(margin=me.Margin(bottom=15)),
    )

  with components.row():
    me.input(
        label="Max Exemplar Ads",
        key="max_exemplar_ads",
        on_blur=event_handlers.update_copycat_parameter,
        value=str(params.max_exemplar_ads),
        type="number",
        appearance="outline",
        style=me.Style(margin=me.Margin.symmetric(horizontal=5)),
    )
    if (
        params.exemplar_selection_method
        == copycat.ExemplarSelectionMethod.AFFINITY_PROPAGATION.value
    ):
      me.input(
          label="Max Initial Ads",
          key="max_initial_ads",
          on_blur=event_handlers.update_copycat_parameter,
          value=str(params.max_initial_ads),
          type="number",
          appearance="outline",
          style=me.Style(margin=me.Margin.symmetric(horizontal=5)),
      )
  if (
      params.exemplar_selection_method
      == copycat.ExemplarSelectionMethod.AFFINITY_PROPAGATION.value
  ):
    me.text(
        "Use Custom Affinity Preference:",
        style=me.Style(margin=me.Margin(bottom=15)),
    )
    with components.row():
      with me.box(
          style=me.Style(
              margin=me.Margin.symmetric(vertical=10),
              align_items="center",
          )
      ):
        me.slide_toggle(
            key="use_custom_affinity_preference",
            on_change=event_handlers.update_copycat_parameter_from_slide_toggle,
            checked=params.use_custom_affinity_preference,
        )
      if params.use_custom_affinity_preference:
        me.input(
            label="Affinity Preference",
            key="custom_affinity_preference",
            on_blur=event_handlers.update_copycat_parameter,
            value=str(params.custom_affinity_preference),
            type="number",
            appearance="outline",
            style=me.Style(
                margin=me.Margin.symmetric(horizontal=5), width=100
            ),
        )


def new_instance() -> None:
  """Renders the new instance page."""
  params = me.state(states.CopycatParamsState)
  state = me.state(states.AppState)

  with components.rounded_box_section("Create Copycat Instance"):
    with components.row(width="100%"):
      with components.column(width="50%", gap=0):
        advertiser_info_section(params)

      with components.column(width="50%", gap=0):
        copycat_creation_settings_section(params)

    with components.conditional_tooltip(
        disabled=not state.google_sheet_is_valid,
        disabled_tooltip="Must first validate the google sheet.",
    ):
      with components.row(align_items="center"):
        me.button(
            label="Re-build Copycat Instance"
            if state.has_copycat_instance
            else "Build Copycat Instance",
            type="flat",
            on_click=event_handlers.build_new_copycat_instance,
            style=me.Style(margin=me.Margin.symmetric(vertical=10)),
        )
        if state.has_copycat_instance:
          me.icon("check_circle")
          me.text("Copycat Instance Exists")
