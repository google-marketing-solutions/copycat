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

"""Contains the objects that contain google ad copy."""

import re
import pydantic


# See https://support.google.com/google-ads/answer/6371157
def parse_google_ads_special_variables(text: str) -> str:
  """Replaces any special variables used by Google Ads with the default string.

  First replaces dynamic keyword insertion with the default keyword. How the
  text is inserted depends on the capitalization:
    "Buy {KeyWord:my keyword} now" -> "Buy My Keyword now"
    "Buy {Keyword:my keyword} now" -> "Buy My keyword now"
    "Buy {keyword:my keyword} now" -> "Buy my keyword now"
    "Buy {KEYWord:my keyword} now" -> "Buy MY Keyword now"
    "Buy {KeyWORD:my keyword} now" -> "Buy My KEYWORD now"

  Then replaces any other customizers with the default value:
    "Buy {CUSTOMIZER.product:my product} now" -> "Buy my product now"

  Args:
    text: The text to parse.

  Returns:
    The text with the default keyword inserted.
  """
  # Title Case
  pattern = r"\{KeyWord:([^}]+)\}"  # The regex pattern
  text = re.sub(pattern, lambda m: m.group(1).title(), text)

  # First Word Capitalized
  pattern = r"\{Keyword:([^}]+)\}"  # The regex pattern
  text = re.sub(pattern, lambda m: m.group(1).capitalize(), text)

  # Lower Case
  pattern = r"\{keyword:([^}]+)\}"  # The regex pattern
  text = re.sub(pattern, lambda m: m.group(1).lower(), text)

  # Caps First Word
  pattern = r"\{KEYWord:([^}]+)\}"  # The regex pattern
  text = re.sub(
      pattern,
      lambda m: m.group(1).split()[0].upper()
      + " "
      + " ".join(m.group(1).split()[1:]).title(),
      text,
  )

  # Caps Last Word
  pattern = r"\{KeyWORD:([^}]+)\}"  # The regex pattern
  text = re.sub(
      pattern,
      lambda m: " ".join(m.group(1).split()[:-1]).title()
      + " "
      + m.group(1).split()[-1].upper(),
      text,
  )

  # Customizers
  pattern = r"\{CUSTOMIZER\.([a-zA-Z0-9_]+):([^}]+)\}"
  text = re.sub(pattern, lambda m: m.group(2), text)

  return text


class GoogleAd(pydantic.BaseModel):
  """Google ad copy.

  The google ad is defined by a list of headlines and descriptions. The
  headlines and descriptions are each limited to 30 and 90 characters
  respectively. Google Ads combines the headlines and descriptions to create the
  final ad copy.
  """

  headlines: list[str] = []  # The list of headlines for the ad.
  descriptions: list[str] = []  # The list of descriptions for the ad.

  def __str__(self) -> str:
    """Returns the headlines and descriptions as a string.

    The string is constructed by combining all of the headlines and descriptions
    into a single string. The headlines are separated by a pipe character. The
    descriptions are separated by a space character.
    """
    headline = " | ".join(self.headlines)
    description = " ".join(self.descriptions)
    return f"**{headline}**\n{description}"

  def __hash__(self) -> int:
    return hash(str(self))

  @property
  def headline_count(self) -> int:
    """The number of headlines in the ad copy."""
    return len(self.headlines)

  @property
  def description_count(self) -> int:
    """The number of descriptions in the ad copy."""
    return len(self.descriptions)

  def __add__(self, other: "GoogleAd") -> "GoogleAd":
    """Adds two GoogleAds together."""
    return self.__class__(
        headlines=self.headlines + other.headlines,
        descriptions=self.descriptions + other.descriptions,
    )


class GoogleAdFormat(pydantic.BaseModel):
  """The Google Ads format."""

  name: str
  max_headlines: int
  max_descriptions: int
  min_headlines: int
  min_descriptions: int
  max_headline_length: int
  max_description_length: int


# More info: https://support.google.com/google-ads/answer/7684791
RESPONSIVE_SEARCH_AD_FORMAT = GoogleAdFormat(
    name="responsive_search_ad",
    max_headlines=15,
    max_descriptions=4,
    min_headlines=3,
    min_descriptions=2,
    max_headline_length=30,
    max_description_length=90,
)


# More info: https://support.google.com/google-ads/answer/12437745
TEXT_AD_FORMAT = GoogleAdFormat(
    name="text_ad",
    max_headlines=3,
    max_descriptions=2,
    min_headlines=1,
    min_descriptions=1,
    max_headline_length=30,
    max_description_length=90,
)


def get_google_ad_format(ad_format: str) -> GoogleAdFormat:
  """Returns the requested Google Ad format.

  Args:
    ad_format: The ad format to get the Google Ad format for. Must be one of
      "responsive_search_ad" or "text_ad".
  """
  ad_formats = [RESPONSIVE_SEARCH_AD_FORMAT, TEXT_AD_FORMAT]
  ad_format_lookup = {ad_format.name: ad_format for ad_format in ad_formats}

  if ad_format not in ad_format_lookup.keys():
    raise ValueError(
        f"Invalid ad format: {ad_format}. Must be one of"
        f" {ad_format_lookup.keys()}"
    )

  return ad_format_lookup[ad_format]
