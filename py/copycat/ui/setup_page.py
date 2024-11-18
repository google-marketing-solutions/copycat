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

from copycat.ui import components
from copycat.ui import event_handlers
from copycat.ui import states


def setup():
  """Renders the setup page.

  The setup page is used to configure some global Copycat parameters, such as
  the Google Cloud Project and Google Ads Account.
  """
  params = me.state(states.CopycatParamsState)
  with components.column(width="100%"):
    with components.rounded_box_section("Google Cloud Project"):
      with components.row():
        me.text(
            "Copycat uses Vertex AI on Google Cloud to call Gemini. You must "
            + "provide a valid Google Cloud Project for this, with "
            + "the Vertex AI API enabled.",
            style=me.Style(margin=me.Margin(bottom=15)),
        )

      with components.row():
        me.input(
            label="Google Cloud Project ID",
            key="vertex_ai_project_id",
            on_blur=event_handlers.update_copycat_parameter,
            value=params.vertex_ai_project_id,
            appearance="outline",
            style=me.Style(
                margin=me.Margin.symmetric(horizontal=5),
            ),
        )
        me.input(
            label="Google Cloud Project Location",
            key="vertex_ai_location",
            on_blur=event_handlers.update_copycat_parameter,
            value=params.vertex_ai_location,
            appearance="outline",
            style=me.Style(margin=me.Margin.symmetric(horizontal=5)),
        )
