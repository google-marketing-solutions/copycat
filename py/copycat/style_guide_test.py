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

import textwrap
from unittest.mock import MagicMock, patch

from absl.testing import absltest
from absl.testing import parameterized
from google.cloud import storage
from vertexai import generative_models
import pandas as pd

from copycat import ad_copy_generator
from copycat import style_guide
from copycat import testing_utils


class TestStyleGuideGenerator(parameterized.TestCase):

  def setUp(self):
    super().setUp()

    self.test_response = generative_models.GenerationResponse.from_dict({
        "candidates": [
            {"content": {"parts": [{"text": "This is a test style guide"}]}}
        ]
    })
    self.embedding_model_patcher = testing_utils.PatchEmbeddingsModel()
    self.embedding_model_patcher.start()

  def tearDown(self):
    super().tearDown()
    self.embedding_model_patcher.stop()

  def test_get_all_files(self):
    mock_storage_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_blob.name = "test_file.pdf"
    mock_blob.content_type = "application/pdf"

    mock_storage_client.bucket.return_value = mock_bucket
    mock_bucket.list_blobs.return_value = [mock_blob]

    with patch("google.cloud.storage.Client", return_value=mock_storage_client):
      generator = style_guide.StyleGuideGenerator()
      result = generator.get_all_files(bucket_name="test_bucket")

    expected_result = [{
        "uri": "gs://test_bucket/test_file.pdf",
        "mime_type": "application/pdf",
    }]
    self.assertEqual(result, expected_result)

    mock_storage_client.bucket.assert_called_once_with("test_bucket")
    mock_bucket.list_blobs.assert_called_once()

  def test_generate_style_guide(self):
    """Tests the style guide generation process with a mock model."""

    with testing_utils.PatchGenerativeModel(
        response=self.test_response
    ) as model_patcher:

      generator = style_guide.StyleGuideGenerator()
      generator.file_info = [
          {"uri": "gs://test_bucket/file1.pdf", "mime_type": "application/pdf"}
      ]

      response = generator.generate_style_guide(
          brand_name="Test Brand",
          additional_style_instructions="Write in a fun and friendly tone.",
          model_name="gemini-1.5-pro-002",
          temperature=0.8,
      )

      # Assertions
      self.assertLen(response.candidates, 1)  # Check for one candidate
      self.assertEqual(
          response.candidates[0].content.text,
          self.test_response.candidates[0].content.text,
      )  # Compare with the test response

      model_patcher.mock_generative_model.generate_content.assert_called_once()

  @parameterized.named_parameters([
      dict(
          testcase_name="No vectorstore, with additional instructions",
          with_ad_copy_vectorstore=False,
          additional_style_instructions="Write in a fun and friendly tone.",
          expected_text_prompt=textwrap.dedent("""\
            In these files is an ad report for Test Brand, containing their ads (headlines and descriptions) that they use on Google Search Ads for the corresponding keywords. Headlines and descriptions are lists, and Google constructs ads by combining those headlines and descriptions together into ads. Therefore the headlines and descriptions should be sufficiently varied that Google is able to try lots of different combinations in order to find what works best.

            Use the ad report to write a comprehensive style guide for this brand's ad copies that can serve as instruction for a copywriter to write new ad copies for Test Brand for new lists of keywords. Ensure that you capure strong phrases, slogans and brand names of Test Brand in the guide.

            Additionally, there could be other files included regarding the brand's style that you should consider in the style guide.

            Also incorporate the following style instructions into the style guide:

            Write in a fun and friendly tone."""),
      ),
      dict(
          testcase_name="With vectorstore, with additional instructions",
          with_ad_copy_vectorstore=True,
          additional_style_instructions="Write in a fun and friendly tone.",
          expected_text_prompt=textwrap.dedent("""\
            Below is an ad report for Test Brand, containing their ads (headlines and descriptions) that they use on Google Search Ads for the corresponding keywords. Headlines and descriptions are lists, and Google constructs ads by combining those headlines and descriptions together into ads. Therefore the headlines and descriptions should be sufficiently varied that Google is able to try lots of different combinations in order to find what works best.

            Use the ad report to write a comprehensive style guide for this brand's ad copies that can serve as instruction for a copywriter to write new ad copies for Test Brand for new lists of keywords. Ensure that you capure strong phrases, slogans and brand names of Test Brand in the guide.

            Additionally, there could be other files included regarding the brand's style that you should consider in the style guide.

            Also incorporate the following style instructions into the style guide:

            Write in a fun and friendly tone.

            Ad Report:

             {  "keywords":"keyword 1, keyword 2",  "headlines":[  "headline 1",  "headline 2"  ],  "descriptions":[  "description 1",  "description 2"  ] }

             {  "keywords":"keyword 3, keyword 4",  "headlines":[  "headline 3",  "headline 4"  ],  "descriptions":[  "description 3",  "description 4"  ] }
            
            """),
      ),
      dict(
          testcase_name="No vectorstore, no additional instructions",
          with_ad_copy_vectorstore=False,
          additional_style_instructions="",
          expected_text_prompt=textwrap.dedent(
              """\
              In these files is an ad report for Test Brand, containing their ads (headlines and descriptions) that they use on Google Search Ads for the corresponding keywords. Headlines and descriptions are lists, and Google constructs ads by combining those headlines and descriptions together into ads. Therefore the headlines and descriptions should be sufficiently varied that Google is able to try lots of different combinations in order to find what works best.

              Use the ad report to write a comprehensive style guide for this brand's ad copies that can serve as instruction for a copywriter to write new ad copies for Test Brand for new lists of keywords. Ensure that you capure strong phrases, slogans and brand names of Test Brand in the guide.

              Additionally, there could be other files included regarding the brand's style that you should consider in the style guide."""
          ),
      ),
      dict(
          testcase_name="With vectorstore, no additional instructions",
          with_ad_copy_vectorstore=True,
          additional_style_instructions="",
          expected_text_prompt=textwrap.dedent("""\
            Below is an ad report for Test Brand, containing their ads (headlines and descriptions) that they use on Google Search Ads for the corresponding keywords. Headlines and descriptions are lists, and Google constructs ads by combining those headlines and descriptions together into ads. Therefore the headlines and descriptions should be sufficiently varied that Google is able to try lots of different combinations in order to find what works best.

            Use the ad report to write a comprehensive style guide for this brand's ad copies that can serve as instruction for a copywriter to write new ad copies for Test Brand for new lists of keywords. Ensure that you capure strong phrases, slogans and brand names of Test Brand in the guide.

            Additionally, there could be other files included regarding the brand's style that you should consider in the style guide.

            Ad Report:

             {  "keywords":"keyword 1, keyword 2",  "headlines":[  "headline 1",  "headline 2"  ],  "descriptions":[  "description 1",  "description 2"  ] }

             {  "keywords":"keyword 3, keyword 4",  "headlines":[  "headline 3",  "headline 4"  ],  "descriptions":[  "description 3",  "description 4"  ] }
            
            """),
      ),
  ])
  def test_generate_style_guide_uses_expected_text_prompt(
      self,
      with_ad_copy_vectorstore,
      additional_style_instructions,
      expected_text_prompt,
  ):
    if with_ad_copy_vectorstore:
      training_data = pd.DataFrame.from_records([
          {
              "headlines": ["headline 1", "headline 2"],
              "descriptions": ["description 1", "description 2"],
              "keywords": "keyword 1, keyword 2",
          },
          {
              "headlines": ["headline 3", "headline 4"],
              "descriptions": ["description 3", "description 4"],
              "keywords": "keyword 3, keyword 4",
          },
      ])

      ad_copy_vectorstore = (
          ad_copy_generator.AdCopyVectorstore.create_from_pandas(
              training_data=training_data,
              embedding_model_name="text-embedding-004",
              dimensionality=256,
              max_initial_ads=100,
              max_exemplar_ads=10,
              affinity_preference=None,
              embeddings_batch_size=10,
              exemplar_selection_method="random",
          )
      )
    else:
      ad_copy_vectorstore = None

    with testing_utils.PatchGenerativeModel(
        response=self.test_response
    ) as model_patcher:
      generator = style_guide.StyleGuideGenerator()

      generator.generate_style_guide(
          brand_name="Test Brand",
          additional_style_instructions=additional_style_instructions,
          model_name="gemini-1.5-pro-002",
          temperature=0.8,
          ad_copy_vectorstore=ad_copy_vectorstore,
      )

      text_prompt = (
          model_patcher.mock_generative_model.generate_content.call_args.kwargs[
              "contents"
          ][0]
          .parts[-1]
          .text
      )
      self.assertEqual(text_prompt, expected_text_prompt)


if __name__ == "__main__":
  absltest.main()
