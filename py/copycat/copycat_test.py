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

import json

from absl.testing import absltest
from absl.testing import parameterized
from vertexai import generative_models
import pandas as pd

from copycat import copycat
from copycat import google_ads
from copycat import testing_utils


class CopycatResponseTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()

    self.training_headlines = ["train headline 1", "train headline 2"]
    self.training_descriptions = ["train description 1", "train description 2"]
    self.keywords = "keyword 1, keyword 2"

    self.default_kwargs = dict(
        training_headlines=self.training_headlines,
        training_descriptions=self.training_descriptions,
        keywords=self.keywords,
    )

  @parameterized.parameters([([], True), (["Non empty error message"], False)])
  def test_success_is_false_if_there_is_an_error_message(
      self, errors, expected_success
  ):
    generated_google_ad = google_ads.GoogleAd(
        headlines=["New headline 1", "New headline 2"],
        descriptions=["New description"],
    )

    response = copycat.CopycatResponse(
        google_ad=generated_google_ad,
        keywords=self.keywords,
        evaluation_results=copycat.EvaluationResults(
            headlines_are_memorised=False,
            descriptions_are_memorised=False,
            style_similarity=None,
            keyword_similarity=None,
            errors=errors,
            warnings=[],
        ),
    )
    self.assertEqual(response.success, expected_success)

  @parameterized.parameters([
      ([], ""),
      (["One error message"], "- One error message"),
      (
          ["Two error message", "Two error message (b)"],
          "- Two error message\n- Two error message (b)",
      ),
  ])
  def test_error_message_is_created_by_joining_errors(
      self, errors, expected_error_message
  ):
    generated_google_ad = google_ads.GoogleAd(
        headlines=["New headline 1", "New headline 2"],
        descriptions=["New description"],
    )

    response = copycat.CopycatResponse(
        google_ad=generated_google_ad,
        keywords=self.keywords,
        evaluation_results=copycat.EvaluationResults(
            headlines_are_memorised=False,
            descriptions_are_memorised=False,
            style_similarity=None,
            keyword_similarity=None,
            errors=errors,
            warnings=[],
        ),
    )
    self.assertEqual(response.error_message, expected_error_message)

  def test_raise_if_not_success_raises_exception_if_not_success(self):
    response = copycat.CopycatResponse(
        google_ad=google_ads.GoogleAd(
            headlines=["New headline 1", "New headline 2"],
            descriptions=["New description"],
        ),
        keywords=self.keywords,
        evaluation_results=copycat.EvaluationResults(
            headlines_are_memorised=False,
            descriptions_are_memorised=False,
            style_similarity=None,
            keyword_similarity=None,
            errors=["One error message"],
            warnings=[],
        ),
    )
    with self.assertRaisesWithLiteralMatch(
        copycat.CopycatResponseError, "- One error message"
    ):
      response.raise_if_not_success()

  def test_raise_if_not_success_does_not_raise_if_success(self):
    response = copycat.CopycatResponse(
        google_ad=google_ads.GoogleAd(
            headlines=["New headline 1", "New headline 2"],
            descriptions=["New description"],
        ),
        keywords=self.keywords,
        evaluation_results=copycat.EvaluationResults(
            headlines_are_memorised=False,
            descriptions_are_memorised=False,
            style_similarity=None,
            keyword_similarity=None,
            errors=[],
            warnings=[],
        ),
    )
    response.raise_if_not_success()


class CopycatTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()

    self.training_data = lambda n_rows: pd.DataFrame({
        "headlines": [
            [f"train headline {i}", f"train headline {i} (2)"]
            for i in range(1, n_rows + 1)
        ],
        "descriptions": [
            [f"train description {i}"] for i in range(1, n_rows + 1)
        ],
        "keywords": [
            f"keyword {i}a, keyword {i}b" for i in range(1, n_rows + 1)
        ],
        "redundant_column": [
            f"redundant col {i}" for i in range(1, n_rows + 1)
        ],
    })
    self.tmp_dir = self.create_tempdir()

    self.model_name = "gemini-1.5-flash-preview-0514"

    self.embedding_model_patcher = testing_utils.PatchEmbeddingsModel()
    self.embedding_model_patcher.start()

  def tearDown(self):
    super().tearDown()
    self.embedding_model_patcher.stop()

  def test_create_from_pandas_creates_copycat_instance(
      self,
  ):
    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(n_rows=3),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )

    self.assertIsInstance(copycat_instance, copycat.Copycat)

  def test_create_from_pandas_uses_training_data_to_construct_vectorstore(
      self,
  ):
    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(n_rows=3),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )

    # Will return all the entries because we only had 3 rows in the training
    # data.
    vectorstore_results = copycat_instance.ad_copy_vectorstore.get_relevant_ads(
        ["query"], k=3
    )[0]

    expected_vectorstore_results = [
        copycat.ad_copy_generator.ExampleAd(
            keywords="keyword 1a, keyword 1b",
            google_ad=google_ads.GoogleAd(
                headlines=["train headline 1", "train headline 1 (2)"],
                descriptions=["train description 1"],
            ),
        ),
        copycat.ad_copy_generator.ExampleAd(
            keywords="keyword 2a, keyword 2b",
            google_ad=google_ads.GoogleAd(
                headlines=["train headline 2", "train headline 2 (2)"],
                descriptions=["train description 2"],
            ),
        ),
        copycat.ad_copy_generator.ExampleAd(
            keywords="keyword 3a, keyword 3b",
            google_ad=google_ads.GoogleAd(
                headlines=["train headline 3", "train headline 3 (2)"],
                descriptions=["train description 3"],
            ),
        ),
    ]
    self.assertCountEqual(vectorstore_results, expected_vectorstore_results)

  def test_create_from_pandas_on_invalid_ad_is_skip_ignores_invalid_ads(self):
    training_data = pd.DataFrame.from_records([
        {
            "headlines": ["a" * 31, "invalid headline"],
            "descriptions": ["invalid description 1"],
            "keywords": "keyword 1, keyword 2",
        },
        {
            "headlines": ["headline 3"],
            "descriptions": ["description 3"],
            "keywords": "keyword 3, keyword 4",
        },
    ])

    with self.assertWarnsRegex(
        Warning,
        "^1 \(50\.00%\) invalid ads found in the training data\. Keeping them"
        " in the training data\.$",
    ):
      copycat_instance = copycat.Copycat.create_from_pandas(
          training_data=training_data,
          embedding_model_name="text-embedding-004",
          ad_format="text_ad",
          on_invalid_ad="skip",
          vectorstore_exemplar_selection_method="random",
      )

    pd.testing.assert_frame_equal(
        copycat_instance.ad_copy_vectorstore.ad_exemplars[
            ["headlines", "descriptions", "keywords"]
        ],
        training_data,
        check_like=True,
    )

  def test_create_from_pandas_on_invalid_ad_is_raise_raises_exception(self):
    training_data = pd.DataFrame.from_records([
        {
            "headlines": ["a" * 31, "invalid headline"],
            "descriptions": ["invalid description 1"],
            "keywords": "keyword 1, keyword 2",
        },
        {
            "headlines": ["headline 3"],
            "descriptions": ["description 3"],
            "keywords": "keyword 3, keyword 4",
        },
    ])

    with self.assertRaisesRegex(
        ValueError,
        "^1 \(50\.00%\) invalid ads found in the training data\.",
    ):
      copycat.Copycat.create_from_pandas(
          training_data=training_data,
          embedding_model_name="text-embedding-004",
          ad_format="text_ad",
          on_invalid_ad="raise",
          vectorstore_exemplar_selection_method="random",
      )

  def test_create_from_pandas_on_invalid_ad_is_drop_drops_invalid_ads(self):
    training_data = pd.DataFrame.from_records([
        {
            "headlines": ["a" * 31, "invalid headline"],
            "descriptions": ["invalid description 1"],
            "keywords": "keyword 1, keyword 2",
        },
        {
            "headlines": ["headline 3"],
            "descriptions": ["description 3"],
            "keywords": "keyword 3, keyword 4",
        },
    ])

    with self.assertWarnsRegex(
        Warning,
        "^1 \(50\.00%\) invalid ads found in the training data\. Dropping them"
        " from the training data\.$",
    ):
      copycat_instance = copycat.Copycat.create_from_pandas(
          training_data=training_data,
          embedding_model_name="text-embedding-004",
          ad_format="text_ad",
          on_invalid_ad="drop",
          vectorstore_exemplar_selection_method="random",
      )

    pd.testing.assert_frame_equal(
        copycat_instance.ad_copy_vectorstore.ad_exemplars[
            ["headlines", "descriptions", "keywords"]
        ],
        pd.DataFrame.from_records([
            {
                "headlines": ["headline 3"],
                "descriptions": ["description 3"],
                "keywords": "keyword 3, keyword 4",
            },
        ]),
        check_like=True,
    )

  @parameterized.parameters("headlines", "descriptions", "keywords")
  def test_create_from_pandas_raises_exception_when_required_column_is_missing(
      self, missing_column
  ):
    expected_error_message = (
        "Training data must contain the columns ['descriptions',"
        f" 'headlines', 'keywords']. Missing columns: ['{missing_column}']."
    )
    with self.assertRaisesWithLiteralMatch(ValueError, expected_error_message):
      copycat.Copycat.create_from_pandas(
          training_data=self.training_data(3).drop(columns=[missing_column]),
          embedding_model_name="text-embedding-004",
          ad_format="text_ad",
          vectorstore_exemplar_selection_method="random",
      )

  @parameterized.named_parameters(
      dict(
          testcase_name="without keyword specific instructions",
          keywords="my keyword 1, my keyword 2",
          keywords_specific_instructions="",
          expected_prompt=[
              generative_models.Content(
                  role="user",
                  parts=[
                      generative_models.Part.from_text(
                          "Keywords: keyword 11a, keyword 11b"
                      )
                  ],
              ),
              generative_models.Content(
                  role="model",
                  parts=[
                      generative_models.Part.from_text(
                          '{"headlines":["train headline 11","train headline 11'
                          ' (2)"],"descriptions":["train description 11"]}'
                      )
                  ],
              ),
              generative_models.Content(
                  role="user",
                  parts=[
                      generative_models.Part.from_text(
                          "Keywords: keyword 20a, keyword 20b"
                      )
                  ],
              ),
              generative_models.Content(
                  role="model",
                  parts=[
                      generative_models.Part.from_text(
                          '{"headlines":["train headline 20","train headline 20'
                          ' (2)"],"descriptions":["train description 20"]}'
                      )
                  ],
              ),
              generative_models.Content(
                  role="user",
                  parts=[
                      generative_models.Part.from_text(
                          "Keywords: my keyword 1, my keyword 2"
                      )
                  ],
              ),
          ],
      ),
      dict(
          testcase_name="with keyword specific instructions",
          keywords="my keyword 1, my keyword 2",
          keywords_specific_instructions="Some keyword specific instructions.",
          expected_prompt=[
              generative_models.Content(
                  role="user",
                  parts=[
                      generative_models.Part.from_text(
                          "Keywords: keyword 11a, keyword 11b"
                      )
                  ],
              ),
              generative_models.Content(
                  role="model",
                  parts=[
                      generative_models.Part.from_text(
                          '{"headlines":["train headline 11","train headline 11'
                          ' (2)"],"descriptions":["train description 11"]}'
                      )
                  ],
              ),
              generative_models.Content(
                  role="user",
                  parts=[
                      generative_models.Part.from_text(
                          "Keywords: keyword 20a, keyword 20b"
                      )
                  ],
              ),
              generative_models.Content(
                  role="model",
                  parts=[
                      generative_models.Part.from_text(
                          '{"headlines":["train headline 20","train headline 20'
                          ' (2)"],"descriptions":["train description 20"]}'
                      )
                  ],
              ),
              generative_models.Content(
                  role="user",
                  parts=[
                      generative_models.Part.from_text(
                          f"For the next set of keywords, please consider the"
                          f" following additional instructions:\n\nSome keyword"
                          f" specific instructions.\n\nKeywords: my keyword 1,"
                          f" my keyword 2"
                      )
                  ],
              ),
          ],
      ),
  )
  def test_construct_text_generation_requests_for_new_ad_copy_returns_expected_request(
      self,
      keywords,
      keywords_specific_instructions,
      expected_prompt,
  ):
    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(n_rows=20),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )
    request = (
        copycat_instance.construct_text_generation_requests_for_new_ad_copy(
            keywords=[keywords],
            keywords_specific_instructions=[keywords_specific_instructions],
            num_in_context_examples=2,
            system_instruction="Example system instruction",
        )[0]
    )

    expected_request = copycat.TextGenerationRequest(
        keywords=keywords,
        prompt=expected_prompt,
        system_instruction="Example system instruction",
        chat_model_name=copycat.ModelName.GEMINI_1_5_FLASH,
        temperature=0.95,
        top_k=20,
        top_p=0.95,
        safety_settings=None,
    )
    self.assertEqual(expected_request.to_markdown(), request.to_markdown())

  @testing_utils.PatchGenerativeModel(
      response=(
          '{"headlines": ["generated headline 1", "generated headline 2"],'
          ' "descriptions": ["generated description"]}'
      )
  )
  def test_generate_new_ad_copy_returns_expected_response(
      self, generative_model_patcher
  ):

    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(20),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )
    response = copycat_instance.generate_new_ad_copy(
        keywords=["my keyword 1, my keyword 2"],
        style_guide="This is my style guide.",
        num_in_context_examples=2,
        system_instruction_kwargs=dict(
            company_name="My company",
            language="english",
        ),
    )[0]
    self.assertEqual(
        response,
        copycat.CopycatResponse(
            google_ad=google_ads.GoogleAd(
                headlines=["generated headline 1", "generated headline 2"],
                descriptions=["generated description"],
            ),
            keywords="my keyword 1, my keyword 2",
            evaluation_results=copycat.EvaluationResults(
                errors=[],
                warnings=[],
                headlines_are_memorised=False,
                descriptions_are_memorised=False,
                style_similarity=0.5338446522650305,
                keyword_similarity=0.47668610866645195,
            ),
        ),
    )

  @testing_utils.PatchGenerativeModel(
      response=(
          '{"headlines": ["generated headline 1", "generated headline 2"],'
          ' "descriptions": ["generated description"]}'
      )
  )
  def test_generate_new_ad_copy_returns_expected_responses_for_list_of_keywords(
      self, generative_model_patcher
  ):

    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(20),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )
    responses = copycat_instance.generate_new_ad_copy(
        keywords=["my keyword 1, my keyword 2", "another keyword"],
        style_guide="This is my style guide.",
        num_in_context_examples=2,
        system_instruction_kwargs=dict(
            company_name="My company",
            language="english",
        ),
    )
    self.assertLen(responses, 2)

  @testing_utils.PatchGenerativeModel(response="not a json")
  def test_generate_new_ad_copy_returns_expected_response_for_non_json_chat_model_output(
      self, generative_model_patcher
  ):

    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(20),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )

    response = copycat_instance.generate_new_ad_copy(
        keywords=["my keyword 1, my keyword 2"],
        style_guide="This is my style guide.",
        num_in_context_examples=2,
        system_instruction_kwargs=dict(
            company_name="My company",
            language="english",
        ),
    )[0]

    self.assertEqual(
        response,
        copycat.CopycatResponse(
            keywords="my keyword 1, my keyword 2",
            google_ad=google_ads.GoogleAd(headlines=[], descriptions=[]),
            evaluation_results=copycat.EvaluationResults(
                errors=[
                    "1 validation error for GoogleAd\n  Invalid JSON: expected"
                    " ident at line 1 column 2 [type=json_invalid,"
                    " input_value='not a json', input_type=str]\n    For"
                    " further information visit"
                    " https://errors.pydantic.dev/2.6/v/json_invalid"
                ],
                warnings=[],
                headlines_are_memorised=None,
                descriptions_are_memorised=None,
                style_similarity=None,
                keyword_similarity=None,
            ),
        ),
    )

  @parameterized.named_parameters(
      dict(
          testcase_name="all descriptions too long",
          headlines=["generated headline"],
          descriptions=["a" * 91],
          expected_error_message=(
              "Invalid number of descriptions for the ad format."
          ),
          expected_headlines_are_memorised=False,
          expected_descriptions_are_memorised=False,
          expected_headlines=["generated headline"],
          expected_descriptions=[],
      ),
      dict(
          testcase_name="all headlines too long",
          headlines=["a" * 31],
          descriptions=["generated description"],
          expected_error_message=(
              "Invalid number of headlines for the ad format."
          ),
          expected_headlines_are_memorised=False,
          expected_descriptions_are_memorised=False,
          expected_headlines=[],
          expected_descriptions=["generated description"],
      ),
      dict(
          testcase_name="headline is memorised",
          headlines=["train headline 1"],
          descriptions=["generated description"],
          expected_error_message=(
              "All headlines are memorised from the training data."
          ),
          expected_headlines_are_memorised=True,
          expected_descriptions_are_memorised=False,
          expected_headlines=["train headline 1"],
          expected_descriptions=["generated description"],
      ),
      dict(
          testcase_name="description is memorised",
          headlines=["generated headline"],
          descriptions=["train description 1"],
          expected_error_message=(
              "All descriptions are memorised from the training data."
          ),
          expected_headlines_are_memorised=False,
          expected_descriptions_are_memorised=True,
          expected_headlines=["generated headline"],
          expected_descriptions=["train description 1"],
      ),
  )
  def test_generate_new_ad_copy_returns_expected_response_if_chat_model_generates_bad_headlines_or_descriptions(
      self,
      headlines,
      descriptions,
      expected_error_message,
      expected_headlines_are_memorised,
      expected_descriptions_are_memorised,
      expected_headlines,
      expected_descriptions,
  ):

    with testing_utils.PatchGenerativeModel(
        response=json.dumps({
            "headlines": headlines,
            "descriptions": descriptions,
        })
    ):
      copycat_instance = copycat.Copycat.create_from_pandas(
          training_data=self.training_data(20),
          embedding_model_name="text-embedding-004",
          ad_format="text_ad",
          vectorstore_exemplar_selection_method="random",
      )

      response = copycat_instance.generate_new_ad_copy(
          keywords=["my keyword 1, my keyword 2"],
          style_guide="This is my style guide.",
          num_in_context_examples=2,
          system_instruction_kwargs=dict(
              company_name="My company",
              language="english",
          ),
          allow_memorised_headlines=False,
          allow_memorised_descriptions=False,
      )[0]

      # I don't want to test the similarity metrics here, so I'm just setting
      # them to None.
      response.evaluation_results.style_similarity = None
      response.evaluation_results.keyword_similarity = None

      expected_google_ad = google_ads.GoogleAd(
          headlines=expected_headlines,
          descriptions=expected_descriptions,
      )
      expected_response = copycat.CopycatResponse(
          google_ad=expected_google_ad,
          keywords="my keyword 1, my keyword 2",
          evaluation_results=copycat.EvaluationResults(
              errors=[expected_error_message],
              warnings=[],
              headlines_are_memorised=expected_headlines_are_memorised,
              descriptions_are_memorised=expected_descriptions_are_memorised,
              style_similarity=None,
              keyword_similarity=None,
          ),
      )

      self.assertEqual(response, expected_response)

  def test_generate_new_ad_copy_returns_expected_response_if_chat_model_fails_to_generate(
      self,
  ):
    failed_response = generative_models.GenerationResponse.from_dict({
        "candidates": [{
            "finish_reason": generative_models.FinishReason.SAFETY,
        }]
    })

    with testing_utils.PatchGenerativeModel(response=failed_response):
      copycat_instance = copycat.Copycat.create_from_pandas(
          training_data=self.training_data(20),
          embedding_model_name="text-embedding-004",
          ad_format="text_ad",
          vectorstore_exemplar_selection_method="random",
      )

      response = copycat_instance.generate_new_ad_copy(
          keywords=["my keyword 1, my keyword 2"],
          style_guide="This is my style guide.",
          num_in_context_examples=2,
          system_instruction_kwargs=dict(
              company_name="My company",
              language="english",
          ),
          allow_memorised_headlines=False,
          allow_memorised_descriptions=False,
      )[0]

      expected_google_ad = google_ads.GoogleAd(
          headlines=[],
          descriptions=[],
      )

      expected_response = copycat.CopycatResponse(
          google_ad=expected_google_ad,
          keywords="my keyword 1, my keyword 2",
          evaluation_results=copycat.EvaluationResults(
              errors=[str(failed_response.candidates[0])],
              warnings=[],
              headlines_are_memorised=None,
              descriptions_are_memorised=None,
              style_similarity=None,
              keyword_similarity=None,
          ),
      )
      self.assertEqual(response, expected_response)

  def test_write_and_load_loads_the_same_copycat_instance(self):

    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(3),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )
    copycat_instance.write(self.tmp_dir.full_path)

    loaded_copycat_instance = copycat.Copycat.load(self.tmp_dir.full_path)

    self.assertTrue(
        testing_utils.copycat_instances_are_equal(
            copycat_instance, loaded_copycat_instance
        )
    )

  @testing_utils.PatchGenerativeModel(
      response=(
          '{"headlines": ["generated headline 1", "generated headline 2"],'
          ' "descriptions": ["generated description"]}'
      )
  )
  def test_generate_new_ad_copy_raises_exception_if_different_number_of_keywords_and_instructions(
      self, generative_model_patcher
  ):
    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(20),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )
    with self.assertRaisesWithLiteralMatch(
        ValueError,
        "keywords and keywords_specific_instructions must have the same"
        " length.",
    ):
      copycat_instance.generate_new_ad_copy(
          keywords=["my keyword 1, my keyword 2"],
          keywords_specific_instructions=[
              "Some keyword specific instructions.",
              "another set",
          ],
          style_guide="This is my style guide.",
          num_in_context_examples=2,
          system_instruction_kwargs=dict(
              company_name="My company",
              language="english",
          ),
      )

  @testing_utils.PatchGenerativeModel(
      response=(
          '{"headlines": ["generated headline 1", "generated headline 2"],'
          ' "descriptions": ["generated description"]}'
      )
  )
  def test_generate_new_ad_copy_uses_keyword_specific_instructions_if_provided(
      self, generative_model_patcher
  ):
    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(20),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )

    _ = copycat_instance.generate_new_ad_copy(
        keywords=["my keyword 1, my keyword 2"],
        keywords_specific_instructions=[
            "Some keyword specific instructions.",
        ],
        style_guide="This is my style guide.",
        num_in_context_examples=2,
        system_instruction_kwargs=dict(
            company_name="My company",
            language="english",
        ),
    )[0]

    mock_generate_content_async = (
        generative_model_patcher.mock_generative_model.generate_content_async
    )

    self.assertEqual(
        mock_generate_content_async.call_args[0][0][-1].parts[0].text,
        "For the next set of keywords, please consider the following additional"
        " instructions:\n\nSome keyword specific instructions.\n\nKeywords: my"
        " keyword 1, my keyword 2",
    )

  @testing_utils.PatchGenerativeModel(
      response=(
          '{"headlines": ["generated headline 1", "generated headline 2"],'
          ' "descriptions": ["generated description"]}'
      )
  )
  def test_generate_new_ad_copy_uses_no_keyword_specific_instructions_if_not_provided(
      self, generative_model_patcher
  ):
    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(20),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )

    _ = copycat_instance.generate_new_ad_copy(
        keywords=["my keyword 1, my keyword 2"],
        style_guide="This is my style guide.",
        num_in_context_examples=2,
        system_instruction_kwargs=dict(
            company_name="My company",
            language="english",
        ),
    )[0]

    mock_generate_content_async = (
        generative_model_patcher.mock_generative_model.generate_content_async
    )

    self.assertEqual(
        mock_generate_content_async.call_args[0][0][-1].parts[0].text,
        "Keywords: my keyword 1, my keyword 2",
    )


if __name__ == "__main__":
  absltest.main()
