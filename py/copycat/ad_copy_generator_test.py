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

from absl.testing import absltest
from absl.testing import parameterized
from vertexai import generative_models
import mock
import pandas as pd
import requests

from copycat import ad_copy_generator
from copycat import google_ads
from copycat import testing_utils


def mock_training_data(
    n_headlines_per_row: list[int], n_descriptions_per_row: list[int]
) -> pd.DataFrame:
  return pd.DataFrame({
      "headlines": [
          [f"train headline {i}_{j}" for i in range(n_headlines)]
          for j, n_headlines in enumerate(n_headlines_per_row)
      ],
      "descriptions": [
          [f"train description {i}_{j}" for i in range(n_descriptions)]
          for j, n_descriptions in enumerate(n_descriptions_per_row)
      ],
      "keywords": [
          f"keyword {i}a, keyword {i}b" for i in range(len(n_headlines_per_row))
      ],
  })


class TextGenerationRequestTest(parameterized.TestCase):

  def test_to_markdown_returns_expected_markdown(self):
    request = ad_copy_generator.TextGenerationRequest(
        keywords="keyword 1, keyword 2",
        prompt=[
            generative_models.Content(
                role="user",
                parts=[
                    generative_models.Part.from_text(
                        '{"Keywords": "keyword 1, keyword 2",'
                        ' "additional_instructions": ""}'
                    )
                ],
            ),
            generative_models.Content(
                role="model",
                parts=[
                    generative_models.Part.from_text(
                        '{"headlines":["headline 1","headline 2"],'
                        '"descriptions":["description 1","description 2"]}'
                    )
                ],
            ),
            generative_models.Content(
                role="user",
                parts=[
                    generative_models.Part.from_text(
                        '{"Keywords": "keyword 3, keyword 4",'
                        ' "additional_instructions": "something"}'
                    )
                ],
            ),
        ],
        system_instruction="My system instruction",
        chat_model_name=ad_copy_generator.ModelName.GEMINI_1_5_FLASH,
        temperature=0.95,
        top_k=20,
        top_p=0.95,
        safety_settings=None,
    )

    expected_markdown = textwrap.dedent(
        """\
      **Keywords:**
      
      keyword 1, keyword 2
      
      **Model Parameters:**

      Model name: gemini-1.5-flash-preview-0514

      Temperature: 0.95

      Top K: 20

      Top P: 0.95
      
      Safety settings: None

      **System instruction:**

      My system instruction

      **User:**

      {"Keywords": "keyword 1, keyword 2", "additional_instructions": ""}

      **Model:**

      {"headlines":["headline 1","headline 2"],"descriptions":["description 1","description 2"]}

      **User:**

      {"Keywords": "keyword 3, keyword 4", "additional_instructions": "something"}"""
    )
    self.assertEqual(request.to_markdown(), expected_markdown)


class AdCopyVectorstoreTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()
    self.tmp_dir = self.create_tempdir()
    self.embedding_model_patcher = testing_utils.PatchEmbeddingsModel()
    self.embedding_model_patcher.start()

  def tearDown(self):
    super().tearDown()
    self.embedding_model_patcher.stop()

  def test_create_from_pandas_deduplicates_ads(self):
    # Training data has same ad for two different sets of keywords.
    # It should keep only one of them.
    training_data = pd.DataFrame.from_records([
        {
            "headlines": ["headline 1", "headline 2"],
            "descriptions": ["description 1", "description 2"],
            "keywords": "keyword 1, keyword 2",
        },
        {
            "headlines": ["headline 1", "headline 2"],
            "descriptions": ["description 1", "description 2"],
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
    self.assertLen(
        ad_copy_vectorstore.ad_exemplars,
        1,
    )

  def test_get_relevant_ads_retrieves_keywords_and_ads(self):

    training_data = pd.DataFrame.from_records([
        {
            "headlines": ["headline 1", "headline 2"],
            "descriptions": ["description 1", "description 2"],
            "keywords": "keyword 1, keyword 2",
        },
        {
            "headlines": ["headline 3"],
            "descriptions": ["description 3"],
            "keywords": "keyword 3, keyword 4",
        },
        {
            "headlines": ["headline 4", "headline 5"],
            "descriptions": ["description 2"],
            "keywords": "keyword 5, keyword 6",
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

    results = ad_copy_vectorstore.get_relevant_ads(["test query"], k=2)
    expected_results = [[
        ad_copy_generator.ExampleAd(
            keywords="keyword 1, keyword 2",
            google_ad=google_ads.GoogleAd(
                headlines=["headline 1", "headline 2"],
                descriptions=["description 1", "description 2"],
            ),
        ),
        ad_copy_generator.ExampleAd(
            keywords="keyword 3, keyword 4",
            google_ad=google_ads.GoogleAd(
                headlines=["headline 3"],
                descriptions=["description 3"],
            ),
        ),
    ]]

    self.assertListEqual(results, expected_results)

  def test_get_relevant_ads_and_embeddings_from_embeddings(self):
    ad_exemplars = pd.DataFrame.from_records([
        {
            "headlines": ["headline 1", "headline 2"],
            "descriptions": ["description 1", "description 2"],
            "keywords": "keyword 1, keyword 2",
            "embeddings": [1.0, 2.0, 3.0],
        },
        {
            "headlines": ["headline 3"],
            "descriptions": ["description 3"],
            "keywords": "keyword 3, keyword 4",
            "embeddings": [4.0, 5.0, 6.0],
        },
        {
            "headlines": ["headline 4", "headline 5"],
            "descriptions": ["description 2"],
            "keywords": "keyword 5, keyword 6",
            "embeddings": [7.0, 8.0, 9.0],
        },
    ])

    ad_copy_vectorstore = ad_copy_generator.AdCopyVectorstore(
        ad_exemplars=ad_exemplars,
        embedding_model_name="text-embedding-004",
        dimensionality=3,
        embeddings_batch_size=10,
    )

    results = (
        ad_copy_vectorstore.get_relevant_ads_and_embeddings_from_embeddings(
            [[2.0, 3.0, 4.0]], k=2
        )
    )
    expected_ads = [[
        ad_copy_generator.ExampleAd(
            keywords="keyword 1, keyword 2",
            google_ad=google_ads.GoogleAd(
                headlines=["headline 1", "headline 2"],
                descriptions=["description 1", "description 2"],
            ),
        ),
        ad_copy_generator.ExampleAd(
            keywords="keyword 3, keyword 4",
            google_ad=google_ads.GoogleAd(
                headlines=["headline 3"],
                descriptions=["description 3"],
            ),
        ),
    ]]
    expected_embeddings = [[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]]
    expected_results = (expected_ads, expected_embeddings)

    self.assertEqual(results, expected_results)

  def test_affinity_propagation_is_used_to_select_ads_if_provided(self):
    training_data = pd.DataFrame.from_records([
        {
            "headlines": ["headline 1", "headline 2"],
            "descriptions": ["description 1", "description 2"],
            "keywords": "keyword 1, keyword 2",
        },
        {
            "headlines": ["headline 3"],
            "descriptions": ["description 3"],
            "keywords": "keyword 3, keyword 4",
        },
    ])

    with mock.patch(
        "google3.third_party.professional_services.solutions.copycat.ad_copy_generator.cluster.AffinityPropagation"
    ) as mock_affinity_propagation:
      (
          ad_copy_generator.AdCopyVectorstore.create_from_pandas(
              training_data=training_data,
              embedding_model_name="text-embedding-004",
              dimensionality=256,
              max_initial_ads=100,
              max_exemplar_ads=10,
              affinity_preference=None,
              embeddings_batch_size=10,
              exemplar_selection_method="affinity_propagation",
          )
      )

      mock_affinity_propagation.assert_called_once()

  def test_write_and_load_loads_the_same_instance(self):
    training_data = pd.DataFrame.from_records([
        {
            "headlines": ["headline 1", "headline 2"],
            "descriptions": ["description 1", "description 2"],
            "keywords": "keyword 1, keyword 2",
        },
        {
            "headlines": ["headline 3"],
            "descriptions": ["description 3"],
            "keywords": "keyword 3, keyword 4",
        },
        {
            "headlines": ["headline 4", "headline 5"],
            "descriptions": ["description 2"],
            "keywords": "keyword 5, keyword 6",
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
    ad_copy_vectorstore.write(self.tmp_dir.full_path)

    loaded_ad_copy_vectorstore = ad_copy_generator.AdCopyVectorstore.load(
        self.tmp_dir.full_path
    )

    self.assertTrue(
        testing_utils.vectorstore_instances_are_equal(
            ad_copy_vectorstore, loaded_ad_copy_vectorstore
        )
    )

  def test_unique_headlines_and_descriptions_are_set_correctly(self):
    training_data = pd.DataFrame.from_records([
        {
            "headlines": ["headline 1", "headline 2"],
            "descriptions": ["description 1", "description 2"],
            "keywords": "keyword 1, keyword 2",
        },
        {
            "headlines": ["headline 3", "headline 2"],
            "descriptions": ["description 3", "description 1"],
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

    self.assertSetEqual(
        ad_copy_vectorstore.unique_headlines,
        {"headline 1", "headline 2", "headline 3"},
    )
    self.assertSetEqual(
        ad_copy_vectorstore.unique_descriptions,
        {"description 1", "description 2", "description 3"},
    )

  def test_embed_documents_returns_expected_embeddings(self):
    training_data = pd.DataFrame.from_records([
        {
            "headlines": ["headline 1", "headline 2"],
            "descriptions": ["description 1", "description 2"],
            "keywords": "keyword 1, keyword 2",
        },
        {
            "headlines": ["headline 3"],
            "descriptions": ["description 3"],
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

    embeddings = ad_copy_vectorstore.embed_documents(
        ["headline 1", "headline 2", "headline 3"]
    )
    self.assertLen(embeddings, 3)
    self.assertLen(embeddings[0], 256)
    self.assertLen(embeddings[1], 256)
    self.assertLen(embeddings[2], 256)

  def test_embed_queries_embeds_queries_correctly(self):
    training_data = pd.DataFrame.from_records([
        {
            "headlines": ["headline 1", "headline 2"],
            "descriptions": ["description 1", "description 2"],
            "keywords": "keyword 1, keyword 2",
        },
        {
            "headlines": ["headline 3"],
            "descriptions": ["description 3"],
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

    embeddings = ad_copy_vectorstore.embed_queries(
        ["headline 1", "headline 2", "headline 3"]
    )
    self.assertLen(embeddings, 3)
    self.assertLen(embeddings[0], 256)
    self.assertLen(embeddings[1], 256)
    self.assertLen(embeddings[2], 256)


class AdCopyGeneratorTest(parameterized.TestCase):

  def test_construct_system_instruction_constructs_expected_instruction_with_style_guide(
      self,
  ):

    instruction = ad_copy_generator.construct_system_instruction(
        system_instruction="My system instruction",
        style_guide="My style guide",
        system_instruction_kwargs={},
    )

    expected_instruction = "My system instruction\n\nMy style guide"
    self.assertEqual(instruction, expected_instruction)

  def test_construct_system_instruction_replaces_system_instruction_placeholders(
      self,
  ):
    instruction = ad_copy_generator.construct_system_instruction(
        system_instruction="My system instruction for {company_name}",
        style_guide="",
        system_instruction_kwargs=dict(
            company_name="my company",
        ),
    )

    expected_instruction = "My system instruction for my company"
    self.assertEqual(instruction, expected_instruction)

  def test_construct_system_instruction_constructs_expected_instruction_without_style_guide(
      self,
  ):

    instruction = ad_copy_generator.construct_system_instruction(
        system_instruction="My system instruction",
        style_guide="",
        system_instruction_kwargs={},
    )
    expected_instruction = "My system instruction"
    self.assertEqual(instruction, expected_instruction)

  def test_construct_new_ad_copy_prompt_constructs_expected_prompt_with_keywords_specific_instructions(
      self,
  ):
    prompt = ad_copy_generator.construct_new_ad_copy_prompt(
        example_ads=[
            ad_copy_generator.ExampleAd(
                keywords="keyword 5, keyword 6",
                google_ad=google_ads.GoogleAd(
                    headlines=["headline 4", "headline 5"],
                    descriptions=["description 2"],
                ),
            ),
            ad_copy_generator.ExampleAd(
                keywords="keyword 3, keyword 4",
                google_ad=google_ads.GoogleAd(
                    headlines=["headline 3"],
                    descriptions=[
                        "description 3",
                        "description with unicode weiß",
                    ],
                ),
            ),
        ],
        keywords_specific_instructions=(
            "My keywords specific instructions with unicode ß"
        ),
        keywords="Keyword 1, Keyword 2, keyword λ",
    )

    expected_prompt = [
        generative_models.Content(
            role="user",
            parts=[
                generative_models.Part.from_text(
                    "Keywords: keyword 3, keyword 4"
                )
            ],
        ),
        generative_models.Content(
            role="model",
            parts=[
                generative_models.Part.from_text(
                    '{"headlines":["headline 3"],"descriptions":'
                    '["description 3","description with unicode weiß"]}'
                )
            ],
        ),
        generative_models.Content(
            role="user",
            parts=[
                generative_models.Part.from_text(
                    "Keywords: keyword 5, keyword 6"
                )
            ],
        ),
        generative_models.Content(
            role="model",
            parts=[
                generative_models.Part.from_text(
                    '{"headlines":["headline 4","headline 5"],'
                    '"descriptions":["description 2"]}'
                )
            ],
        ),
        generative_models.Content(
            role="user",
            parts=[
                generative_models.Part.from_text(
                    "For the next set of keywords, please consider the"
                    " following additional instructions:\n\nMy keywords"
                    " specific instructions with unicode ß\n\nKeywords: Keyword"
                    " 1, Keyword 2, keyword λ"
                )
            ],
        ),
    ]

    for single_prompt, single_expected_prompt in zip(prompt, expected_prompt):
      self.assertEqual(
          single_prompt.to_dict(), single_expected_prompt.to_dict()
      )

  def test_construct_new_ad_copy_prompt_without_keywords_specific_instructions(
      self,
  ):
    prompt = ad_copy_generator.construct_new_ad_copy_prompt(
        example_ads=[
            ad_copy_generator.ExampleAd(
                keywords="keyword 5, keyword 6",
                google_ad=google_ads.GoogleAd(
                    headlines=["headline 4", "headline 5"],
                    descriptions=["description 2"],
                ),
            ),
            ad_copy_generator.ExampleAd(
                keywords="keyword 3, keyword 4",
                google_ad=google_ads.GoogleAd(
                    headlines=["headline 3"],
                    descriptions=[
                        "description 3",
                        "description with unicode weiß",
                    ],
                ),
            ),
        ],
        keywords_specific_instructions="",
        keywords="Keyword 1, Keyword 2",
    )

    expected_prompt = [
        generative_models.Content(
            role="user",
            parts=[
                generative_models.Part.from_text(
                    "Keywords: keyword 3, keyword 4"
                )
            ],
        ),
        generative_models.Content(
            role="model",
            parts=[
                generative_models.Part.from_text(
                    '{"headlines":["headline 3"],"descriptions":'
                    '["description 3","description with unicode weiß"]}'
                )
            ],
        ),
        generative_models.Content(
            role="user",
            parts=[
                generative_models.Part.from_text(
                    "Keywords: keyword 5, keyword 6"
                )
            ],
        ),
        generative_models.Content(
            role="model",
            parts=[
                generative_models.Part.from_text(
                    '{"headlines":["headline 4","headline 5"],'
                    '"descriptions":["description 2"]}'
                )
            ],
        ),
        generative_models.Content(
            role="user",
            parts=[
                generative_models.Part.from_text(
                    "Keywords: Keyword 1, Keyword 2"
                )
            ],
        ),
    ]

    for single_prompt, single_expected_prompt in zip(prompt, expected_prompt):
      self.assertEqual(
          single_prompt.to_dict(), single_expected_prompt.to_dict()
      )

  @parameterized.named_parameters([
      {
          "testcase_name": "too many headlines",
          "headlines": [f"headline {i}" for i in range(16)],
          "descriptions": ["description 1"],
          "fixed_headlines": [f"headline {i}" for i in range(15)],
          "fixed_descriptions": ["description 1"],
      },
      {
          "testcase_name": "too many descriptions",
          "headlines": ["headline 1"],
          "descriptions": [f"description {i}" for i in range(6)],
          "fixed_headlines": ["headline 1"],
          "fixed_descriptions": [f"description {i}" for i in range(4)],
      },
      {
          "testcase_name": "too long headline",
          "headlines": ["headline 1", "a" * 31, "headline 2"],
          "descriptions": ["description 1"],
          "fixed_headlines": ["headline 1", "headline 2"],
          "fixed_descriptions": ["description 1"],
      },
      {
          "testcase_name": "too long description",
          "headlines": ["headline 1", "headline 2"],
          "descriptions": ["description 1", "a" * 91, "description 2"],
          "fixed_headlines": ["headline 1", "headline 2"],
          "fixed_descriptions": ["description 1", "description 2"],
      },
      {
          "testcase_name": "dynamic keyword insertion",
          "headlines": [
              "Valid DKI {KeyWord:my keyword} 123",
              "Invalid DKI {KeyWord:my keyword} too long!",
          ],
          "descriptions": [
              "Valid DKI {KeyWord:my keyword} " + "a" * 63,
              "Invalid DKI {KeyWord:my keyword} too long!" + "a" * 63,
          ],
          "fixed_headlines": ["Valid DKI {KeyWord:my keyword} 123"],
          "fixed_descriptions": ["Valid DKI {KeyWord:my keyword} " + "a" * 63],
      },
  ])
  def test_remove_invalid_headlines_and_descriptions_returns_fixed_ad_copy(
      self, headlines, descriptions, fixed_headlines, fixed_descriptions
  ):
    google_ad = google_ads.GoogleAd(
        headlines=headlines,
        descriptions=descriptions,
    )
    ad_copy_generator.remove_invalid_headlines_and_descriptions(
        google_ad, google_ads.RESPONSIVE_SEARCH_AD_FORMAT
    )

    expected_fixed_ad = google_ads.GoogleAd(
        headlines=fixed_headlines,
        descriptions=fixed_descriptions,
    )
    self.assertEqual(expected_fixed_ad, google_ad)

  @parameterized.parameters(
      (
          ad_copy_generator.ModelName.GEMINI_1_5_FLASH,
          "gemini-1.5-flash-preview-0514",
      ),
      (
          ad_copy_generator.ModelName.GEMINI_1_5_PRO,
          "gemini-1.5-pro-preview-0514",
      ),
  )
  @testing_utils.PatchGenerativeModel(response="Response text")
  def test_generate_google_ad_parses_model_name_correctly(
      self, input_model_name, parsed_model_name, generative_model_patcher
  ):
    request = ad_copy_generator.TextGenerationRequest(
        keywords="keyword 1, keyword 2",
        prompt=[
            generative_models.Content(
                role="user",
                parts=[generative_models.Part.from_text("Example prompt")],
            )
        ],
        system_instruction="Example system instruction",
        chat_model_name=input_model_name,
        temperature=0.9,
        top_k=40,
        top_p=0.95,
        safety_settings=None,
    )
    ad_copy_generator.generate_google_ad_json_batch([request])

    self.assertEqual(
        generative_model_patcher.mock_init.call_args[1]["model_name"],
        parsed_model_name,
    )

  @testing_utils.PatchGenerativeModel(response="Response text")
  def test_generate_google_ad_parses_safety_settings_correctly(
      self, generative_model_patcher
  ):
    custom_safety_settings = {
        ad_copy_generator.generative_models.HarmCategory.HARM_CATEGORY_HATE_SPEECH: (
            ad_copy_generator.generative_models.HarmBlockThreshold.BLOCK_NONE
        )
    }
    request = ad_copy_generator.TextGenerationRequest(
        keywords="keyword 1, keyword 2",
        prompt=[
            generative_models.Content(
                role="user",
                parts=[generative_models.Part.from_text("Example prompt")],
            )
        ],
        system_instruction="Example system instruction",
        chat_model_name=ad_copy_generator.ModelName.GEMINI_1_5_FLASH,
        temperature=0.9,
        top_k=40,
        top_p=0.95,
        safety_settings=custom_safety_settings,
    )
    ad_copy_generator.generate_google_ad_json_batch([request])

    self.assertEqual(
        generative_model_patcher.mock_init.call_args[1]["safety_settings"],
        custom_safety_settings,
    )

  @parameterized.parameters(
      ad_copy_generator.ModelName.GEMINI_1_5_FLASH,
      ad_copy_generator.ModelName.GEMINI_1_5_PRO,
  )
  @testing_utils.PatchGenerativeModel(response="Response text")
  def test_generate_google_ad_adds_format_instructions_to_system_instruction(
      self, input_model_name, generative_model_patcher
  ):
    request = ad_copy_generator.TextGenerationRequest(
        keywords="keyword 1, keyword 2",
        prompt=[
            generative_models.Content(
                role="user",
                parts=[generative_models.Part.from_text("Example prompt")],
            )
        ],
        system_instruction="Example system instruction",
        chat_model_name=input_model_name,
        temperature=0.9,
        top_k=40,
        top_p=0.95,
        safety_settings=None,
    )
    ad_copy_generator.generate_google_ad_json_batch([request])
    expected_system_instruction = (
        "Example system instruction\n\nReturn:"
        " GoogleAd\nGoogleAd = {\n  'headlines': list[str],\n "
        " 'descriptions': list[str]\n}"
    )
    self.assertEqual(
        generative_model_patcher.mock_init.call_args[1]["system_instruction"],
        expected_system_instruction,
    )

  @parameterized.parameters(
      ad_copy_generator.ModelName.GEMINI_1_5_FLASH,
      ad_copy_generator.ModelName.GEMINI_1_5_PRO,
  )
  @testing_utils.PatchGenerativeModel(response="Response text")
  def test_generate_google_ad_uses_expected_generation_config(
      self, input_model_name, generative_model_patcher
  ):

    request = ad_copy_generator.TextGenerationRequest(
        keywords="keyword 1, keyword 2",
        prompt=[
            generative_models.Content(
                role="user",
                parts=[generative_models.Part.from_text("Example prompt")],
            )
        ],
        system_instruction="Example system instruction",
        chat_model_name=input_model_name,
        temperature=0.9,
        top_k=40,
        top_p=0.95,
        safety_settings=None,
    )
    ad_copy_generator.generate_google_ad_json_batch([request])

    expected_generation_config = dict(
        temperature=0.9,
        top_k=40,
        top_p=0.95,
        response_mime_type="application/json",
    )
    if input_model_name is ad_copy_generator.ModelName.GEMINI_1_5_PRO:
      expected_generation_config["response_schema"] = {
          "type_": "OBJECT",
          "properties": {
              "headlines": {
                  "type_": "ARRAY",
                  "items": {"type_": "STRING"},
                  "title": "Headlines",
              },
              "descriptions": {
                  "type_": "ARRAY",
                  "items": {"type_": "STRING"},
                  "title": "Descriptions",
              },
          },
          "required": ["headlines", "descriptions"],
          "description": (
              "Google ad copy. The google ad is defined by a list of headlines"
              " and descriptions. The headlines and descriptions are each"
              " limited to 30 and 90 characters respectively. Google Ads"
              " combines the headlines and descriptions to create the final ad"
              " copy."
          ),
          "title": "GoogleAd",
      }

    self.assertDictEqual(
        generative_model_patcher.mock_init.call_args[1][
            "generation_config"
        ].to_dict(),
        expected_generation_config,
    )

  @parameterized.parameters(
      ad_copy_generator.ModelName.GEMINI_1_5_FLASH,
      ad_copy_generator.ModelName.GEMINI_1_5_PRO,
  )
  @testing_utils.PatchGenerativeModel(response="Response text")
  def test_generate_google_ad_uses_prompt(
      self, input_model_name, generative_model_patcher
  ):
    prompt = [
        generative_models.Content(
            role="user",
            parts=[generative_models.Part.from_text("Example prompt")],
        )
    ]
    request = ad_copy_generator.TextGenerationRequest(
        keywords="keyword 1, keyword 2",
        prompt=prompt,
        system_instruction="Example system instruction",
        chat_model_name=input_model_name,
        temperature=0.9,
        top_k=40,
        top_p=0.95,
        safety_settings=None,
    )
    ad_copy_generator.generate_google_ad_json_batch([request])

    generative_model_patcher.mock_generative_model.generate_content_async.assert_called_with(
        prompt
    )

  @parameterized.parameters(
      ad_copy_generator.ModelName.GEMINI_1_5_FLASH,
      ad_copy_generator.ModelName.GEMINI_1_5_PRO,
  )
  @testing_utils.PatchGenerativeModel(response="Response text")
  def test_generate_google_ad_returns_response_from_gemini(
      self, input_model_name, generative_model_patcher
  ):

    request = ad_copy_generator.TextGenerationRequest(
        keywords="keyword 1, keyword 2",
        prompt=[
            generative_models.Content(
                role="user",
                parts=[generative_models.Part.from_text("Example prompt")],
            )
        ],
        system_instruction="Example system instruction",
        chat_model_name=input_model_name,
        temperature=0.9,
        top_k=40,
        top_p=0.95,
        safety_settings=None,
    )
    response = ad_copy_generator.generate_google_ad_json_batch([request])
    self.assertEqual(
        response[0].candidates[0].content.parts[0].text, "Response text"
    )

  @parameterized.parameters(
      ad_copy_generator.ModelName.GEMINI_1_5_FLASH,
      ad_copy_generator.ModelName.GEMINI_1_5_PRO,
  )
  @testing_utils.PatchGenerativeModel(response="Response text")
  def test_generate_google_ad_returns_multiple_responses_from_gemini_in_batch(
      self, input_model_name, generative_model_patcher
  ):

    prompt_1 = [
        generative_models.Content(
            role="user",
            parts=[generative_models.Part.from_text("Example prompt")],
        )
    ]
    prompt_2 = [
        generative_models.Content(
            role="user",
            parts=[generative_models.Part.from_text("Another example prompt")],
        )
    ]

    request_1 = ad_copy_generator.TextGenerationRequest(
        keywords="keyword 1, keyword 2",
        prompt=prompt_1,
        system_instruction="Example system instruction",
        chat_model_name=input_model_name,
        temperature=0.9,
        top_k=40,
        top_p=0.95,
        safety_settings=None,
    )

    request_2 = ad_copy_generator.TextGenerationRequest(
        keywords="keyword 1, keyword 2",
        prompt=prompt_2,
        system_instruction="Example system instruction",
        chat_model_name=input_model_name,
        temperature=0.9,
        top_k=40,
        top_p=0.95,
        safety_settings=None,
    )

    response = ad_copy_generator.generate_google_ad_json_batch(
        [request_1, request_2]
    )

    self.assertLen(response, 2)

  def test_extract_url_with_http(self):
    text = "Check out this website: http://www.example.com for more info."
    expected_url = "http://www.example.com"
    self.assertEqual(
        ad_copy_generator.extract_url_from_string(text), expected_url
    )

  def test_extract_url_with_https(self):
    text = "Secure site: https://www.google.com"
    expected_url = "https://www.google.com"
    self.assertEqual(
        ad_copy_generator.extract_url_from_string(text), expected_url
    )

  def test_extract_url_with_complex_path(self):
    text = "API endpoint: https://api.example.com/v1/users/1234?key=abc"
    expected_url = "https://api.example.com/v1/users/1234?key=abc"
    self.assertEqual(
        ad_copy_generator.extract_url_from_string(text), expected_url
    )

  def test_no_url_present(self):
    text = "No URL in this text."
    self.assertFalse(
        ad_copy_generator.extract_url_from_string(text)
    )  # Check for False

  def test_multiple_urls(self):
    # This function is designed to extract the first URL it finds
    text = "Visit http://www.example.com or https://www.google.com"
    expected_url = "http://www.example.com"
    self.assertEqual(
        ad_copy_generator.extract_url_from_string(text), expected_url
    )

  def test_valid_urls(self):
    valid_urls = [
        "http://www.example.com",
        "https://www.google.com",
        "https://subdomain.example.co.uk/some/path",
        "https://google.com/path/with-hyphens",
    ]
    for url in valid_urls:
      self.assertTrue(ad_copy_generator.is_valid_url(url))

  def test_invalid_urls(self):
    invalid_urls = [
        "www.example.com",  # Missing protocol
        "htt://www.example.com",  # Invalid protocol
        "https://.com",  # Missing domain name
        "https://example",  # Missing TLD
        "ftp://example.com",  # Unsupported protocol
        "https://example.com/ path/with/spaces",  # Spaces in the path
    ]
    for url in invalid_urls:
      self.assertFalse(ad_copy_generator.is_valid_url(url))

  @mock.patch("bs4.BeautifulSoup")
  @mock.patch("requests.get")
  def test_extract_urls_for_keyword_instructions(
      self,
      mock_requests_get,
      mock_beautiful_soup,
  ):

    mock_requests_get.return_value.raise_for_status.return_value = None
    mock_requests_get.return_value.content = (
        "<html><body><h1>Test Page</h1></body></html>"
    )
    mock_beautiful_soup.return_value.get_text.return_value = "Test Page"

    mock_requests_get.side_effect = [
        mock.DEFAULT,
        mock.DEFAULT,
        requests.exceptions.RequestException(
            "Simulated Error"
        ),
    ]

    keyword_instructions = [
        "This is some text without a URL.",
        "Visit https://www.example.com for more details.",
        "https://www.google.com",
        "invalid_url",
        "https://www.error.com",
    ]
    expected_output = [
        "This is some text without a URL.",
        (
            "Visit https://www.example.com for more details. ## Content of"
            " https://www.example.com: Test Page"
        ),
        "Web page content of https://www.google.com: Test Page",
        "invalid_url",
        "https://www.error.com",
    ]

    result = ad_copy_generator.extract_urls_for_keyword_instructions(
        keyword_instructions
    )
    self.assertEqual(len(result), len(expected_output))
    self.assertEqual(result, expected_output)


if __name__ == "__main__":
  absltest.main()
