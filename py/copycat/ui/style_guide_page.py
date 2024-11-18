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


_STYLE_GUIDE_EDITOR_STYLE = me.Style(
    overflow_y="scroll",
    padding=me.Padding(left=20, right=15, top=20, bottom=0),
    border=me.Border(
        right=styles.DEFAULT_BORDER_STYLE,
    ),
    width="50%",
)

_STYLE_GUIDE_PREVIEW_STYLE = me.Style(
    overflow_y="scroll",
    padding=me.Padding.symmetric(vertical=0, horizontal=20),
    width="50%",
)

_STYLE_GUIDE_TEXTAREA_STYLE = me.Style(
    outline="none",  # Hides focus border
    border=me.Border.all(me.BorderSide(style="none")),
    width="100%",
    height="100%",
    background=me.theme_var("background"),
)


def style_guide():
  """Renders the style guide page."""
  params = me.state(states.CopycatParamsState)

  with components.column(width="100%"):
    with components.row(width="100%"):
      with components.rounded_box_section("Generate Style Guide", width="100%"):
        me.text("Chat Model:")
        me.radio(
            on_change=event_handlers.update_copycat_parameter,
            key="style_guide_chat_model_name",
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
            value=params.style_guide_chat_model_name,
            style=me.Style(margin=me.Margin(bottom=15)),
        )
        with components.row():
          me.input(
              label="Temperature",
              on_blur=event_handlers.update_copycat_parameter,
              key="style_guide_temperature",
              value=str(params.style_guide_temperature),
              appearance="outline",
              type="number",
              style=me.Style(margin=me.Margin.symmetric(horizontal=5)),
          )
          me.input(
              label="Top-K",
              on_blur=event_handlers.update_copycat_parameter,
              key="style_guide_top_k",
              value=str(params.style_guide_top_k),
              appearance="outline",
              type="number",
              style=me.Style(margin=me.Margin.symmetric(horizontal=5)),
          )
          me.input(
              label="Top-P",
              on_blur=event_handlers.update_copycat_parameter,
              key="style_guide_top_p",
              value=str(params.style_guide_top_p),
              appearance="outline",
              type="number",
              style=me.Style(margin=me.Margin.symmetric(horizontal=5)),
          )
        me.slide_toggle(
            label="Use exemplar ads to generate Style Guide",
            on_change=event_handlers.update_copycat_parameter_from_slide_toggle,
            key="style_guide_use_exemplar_ads",
            checked=params.style_guide_use_exemplar_ads,
        )
        me.text(
            "Additional instructions for generating the style guide"
            " (optional):",
            style=me.Style(margin=me.Margin.symmetric(vertical=15)),
        )
        with me.box(style=me.Style(width="40%")):
          me.input(
              label="Additional Instructions",
              on_blur=event_handlers.update_copycat_parameter,
              key="style_guide_additional_instructions",
              value=str(params.style_guide_additional_instructions),
              appearance="outline",
              style=me.Style(
                  margin=me.Margin.symmetric(horizontal=5), width="100%"
              ),
          )
        me.text(
            "Google Cloud Bucket URI containing supplementary materials"
            " (optional):",
            style=me.Style(margin=me.Margin(bottom=15)),
        )

        with components.row(
            align_items="center",
            gap=5,
            justify_content="space-between",
        ):
          with me.box(style=me.Style(width="40%")):
            me.input(
                label="GCP Bucket URI",
                on_blur=event_handlers.update_copycat_parameter,
                key="style_guide_files_uri",
                value=str(params.style_guide_files_uri),
                appearance="outline",
                style=me.Style(
                    margin=me.Margin.symmetric(horizontal=5), width="100%"
                ),
            )
          me.button(
              label="Generate",
              type="flat",
              on_click=event_handlers.generate_style_guide,
              style=me.Style(margin=me.Margin(top=20)),
          )

    with components.rounded_box_section(width="100%", height="80%"):
      with components.row(width="100%", height="100%", gap=0):
        # Markdown Editor Column
        with me.box(style=_STYLE_GUIDE_EDITOR_STYLE):
          me.native_textarea(
              value=params.style_guide,
              style=_STYLE_GUIDE_TEXTAREA_STYLE,
              on_blur=event_handlers.update_copycat_parameter,
              key="style_guide"
          )

        # Markdown Preview Column
        with me.box(style=_STYLE_GUIDE_PREVIEW_STYLE):
          me.markdown(params.style_guide)
