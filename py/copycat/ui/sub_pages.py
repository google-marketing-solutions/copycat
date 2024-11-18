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

"""An object for handling the sub pages of the Copycat UI."""

from typing import Callable

import mesop as me

from copycat.ui import components
from copycat.ui import states
from copycat.ui import styles


def navigate_to_subpage(event: me.ClickEvent):
  state = me.state(states.AppState)
  state.highlighted_url = event.key


class SubPages(dict):
  """An object for handling the sub pages of the Copycat UI.

  Stores functions for rendering the pages, and the navigation button text and
  icon, in a dictionary. The keys of the dictionary are the urls of the pages.
  """

  def add_page(
      self, page_func: Callable[[], None], *, nav_text: str, nav_icon: str
  ) -> None:
    """Adds a page to the sub pages.

    Args:
      page_func: The function to call to render the page.
      nav_text: The text to display in the navigation button.
      nav_icon: The icon to display in the navigation button.
    """
    url = "/" + getattr(page_func, "__name__", repr(page_func))
    self[url] = dict(
        page_func=page_func,
        nav_text=nav_text,
        nav_icon=nav_icon,
    )

  @me.content_component
  def navigation_button(self, url: str):
    """Renders the navigation button for a sub page.

    Args:
      url: The url of the sub page.
    """
    state = me.state(states.AppState)

    style_params = dict(
        padding=me.Padding.symmetric(vertical=30, horizontal=25),
    )
    if state.highlighted_url == url:
      style_params["background"] = me.theme_var("primary")
      style_params["color"] = me.theme_var("surface-container")

    with me.content_button(
        key=url, on_click=navigate_to_subpage, style=me.Style(**style_params)
    ):
      me.icon(self[url]["nav_icon"])
      me.text(self[url]["nav_text"])

  def render(self, **kwargs):
    """Renders the nav bar and the body of the active sub page.

    Args:
      **kwargs: Any additional keyword arguments to pass to the outer box
        containing the nav bar and the body.
    """
    state = me.state(states.AppState)

    with components.column(**kwargs):
      # Nav Bar
      with components.header_bar(
          border=me.Border(bottom=styles.DEFAULT_BORDER_STYLE)
      ):
        with components.header_section():
          for i, url in enumerate(self.keys()):
            with self.navigation_button(url):
              pass
            if i < (len(self.keys()) - 1):
              me.icon(
                  "arrow_forward_ios",
                  style=me.Style(color=me.theme_var("primary")),
              )

      # Body
      with me.box(
          style=me.Style(
              padding=me.Padding.all(24),
              overflow_y="auto",
              display="flex",
              height="100%",
              width="100%",
              gap=5,
          )
      ):
        if state.highlighted_url:
          self[state.highlighted_url]["page_func"]()
