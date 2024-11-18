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

from absl.testing import absltest
from absl.testing import parameterized

from copycat import google_ads


class GoogleAdTest(parameterized.TestCase):

  def test_google_ad_can_be_converted_to_string_representation(self):
    google_ad = google_ads.GoogleAd(
        headlines=["Headline 1", "Headline 2"],
        descriptions=["Description 1.", "Description 2."],
    )
    self.assertEqual(
        str(google_ad),
        "**Headline 1 | Headline 2**\nDescription 1. Description 2.",
    )

  def test_google_ad_accepts_unicode_characters(self):
    google_ad = google_ads.GoogleAd(
        headlines=["Headline 1", "Headline 2"],
        descriptions=["Description 1.", "Description with unicode weiß."],
    )
    self.assertEqual(
        str(google_ad),
        "**Headline 1 | Headline 2**\nDescription 1. Description with unicode"
        " weiß.",
    )

  def test_google_ad_can_be_hashed_deterministically(self):
    # Must be hashable so it can be efficiently deduplicated.
    google_ad_1 = google_ads.GoogleAd(
        headlines=["Headline 1", "Headline 2"],
        descriptions=["Description 1.", "Description 2."],
    )
    google_ad_2 = google_ads.GoogleAd(
        headlines=["Headline 1", "Headline 2"],
        descriptions=["Description 1.", "Description 2."],
    )
    google_ad_3 = google_ads.GoogleAd(
        headlines=["Headline 2", "Headline 3"],
        descriptions=["Description 2.", "Description 3."],
    )

    self.assertEqual(hash(google_ad_1), hash(google_ad_2))
    self.assertNotEqual(hash(google_ad_1), hash(google_ad_3))

  @parameterized.parameters(
      ("responsive_search_ad", google_ads.RESPONSIVE_SEARCH_AD_FORMAT),
      ("text_ad", google_ads.TEXT_AD_FORMAT),
  )
  def test_get_google_ad_format_retuens_expected_format(
      self, name, expected_format
  ):
    self.assertEqual(google_ads.get_google_ad_format(name), expected_format)

  def test_get_google_ad_format_raises_error_for_invalid_format(self):
    with self.assertRaises(ValueError):
      google_ads.get_google_ad_format("invalid_format")

  @parameterized.parameters([
      ("No DKI is unchanged", "No DKI is unchanged"),
      (
          (
              "A few different DKIs: {KeyWord:all first letters capital}"
              " {Keyword:first letter first word capital} {keyword:all"
              " lowercase} {KEYWord:first word all caps} {KeyWORD:last word all"
              " caps} {CUSTOMIZER.something:my customizer}"
          ),
          (
              "A few different DKIs: All First Letters Capital First letter"
              " first word capital all lowercase FIRST Word All Caps Last Word"
              " All CAPS my customizer"
          ),
      ),
      (
          "Non DKI brackets are unchanged {not a keyword}",
          "Non DKI brackets are unchanged {not a keyword}",
      ),
  ])
  def test_parse_google_ads_special_variables(self, text, expected):
    got = google_ads.parse_google_ads_special_variables(text=text)
    self.assertEqual(expected, got)


if __name__ == "__main__":
  absltest.main()
