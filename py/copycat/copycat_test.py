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
import keyword

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

  @parameterized.parameters([
      ([], ""),
      (["One warning message"], "- One warning message"),
      (
          ["Two warning message", "Two warning message (b)"],
          "- Two warning message\n- Two warning message (b)",
      ),
  ])
  def test_warning_message_is_created_by_joining_warnings(
      self, warnings, expected_warning_message
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
            warnings=warnings,
            errors=[],
        ),
    )
    self.assertEqual(response.warning_message, expected_warning_message)

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

    self.model_name = "gemini-1.5-flash-002"

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

  def test_create_from_pandas_replaces_special_variables_in_training_data_if_set(
      self,
  ):
    training_data = pd.DataFrame({
        "headlines": [
            ["headline 1", "headline {CUSTOMIZER.product:my product}"]
        ],
        "descriptions": [
            ["description 1", "description {CUSTOMIZER.product:my product}"]
        ],
        "keywords": ["keyword 1, keyword 2"],
    })
    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=training_data,
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
        replace_special_variables_with_default=True,
    )

    # Will return all the entries because we only had 3 rows in the training
    # data.
    vectorstore_results = copycat_instance.ad_copy_vectorstore.get_relevant_ads(
        ["query"], k=3
    )[0]

    expected_vectorstore_results = [
        copycat.ad_copy_generator.ExampleAd(
            keywords="keyword 1, keyword 2",
            google_ad=google_ads.GoogleAd(
                headlines=["headline 1", "headline my product"],
                descriptions=["description 1", "description my product"],
            ),
        ),
    ]
    self.assertCountEqual(vectorstore_results, expected_vectorstore_results)

  def test_create_from_pandas_considers_unfillable_special_variables_as_invalid_ads_if_replacing_them(
      self,
  ):
    training_data = pd.DataFrame({
        "headlines": [["headline 1", "headline {CUSTOMIZER.product}"]],
        "descriptions": [["description 1", "description {CUSTOMIZER.product}"]],
        "keywords": ["keyword 1, keyword 2"],
    })
    with self.assertRaisesWithLiteralMatch(
        ValueError, "1 (100.00%) invalid ads found in the training data."
    ):
      copycat.Copycat.create_from_pandas(
          training_data=training_data,
          embedding_model_name="text-embedding-004",
          ad_format="text_ad",
          vectorstore_exemplar_selection_method="random",
          replace_special_variables_with_default=True,
          on_invalid_ad="raise",
      )

  def test_create_from_pandas_ignores_special_variables_in_training_data_if_not_replacing_them(
      self,
  ):
    training_data = pd.DataFrame({
        "headlines": [
            ["headline 1", "headline {CUSTOMIZER.product:my product}"]
        ],
        "descriptions": [["description 1", "description {CUSTOMIZER.product}"]],
        "keywords": ["keyword 1, keyword 2"],
    })
    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=training_data,
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
        replace_special_variables_with_default=False,
    )

    # Will return all the entries because we only had 3 rows in the training
    # data.
    vectorstore_results = copycat_instance.ad_copy_vectorstore.get_relevant_ads(
        ["query"], k=3
    )[0]

    expected_vectorstore_results = [
        copycat.ad_copy_generator.ExampleAd(
            keywords="keyword 1, keyword 2",
            google_ad=google_ads.GoogleAd(
                headlines=[
                    "headline 1",
                    "headline {CUSTOMIZER.product:my product}",
                ],
                descriptions=[
                    "description 1",
                    "description {CUSTOMIZER.product}",
                ],
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
          existing_headlines=None,
          existing_descriptions=None,
          keywords_specific_instructions="",
          expected_prompt=[
              generative_models.Content(
                  role="user",
                  parts=[
                      generative_models.Part.from_text(
                          "Please write 2 headlines and 1 descriptions for this"
                          " ad.\n\nKeywords: keyword 11a, keyword 11b"
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
                          "Please write 2 headlines and 1 descriptions for this"
                          " ad.\n\nKeywords: keyword 20a, keyword 20b"
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
                          "Please write 3 headlines and 2 descriptions for this"
                          " ad.\n\nKeywords: my keyword 1, my keyword 2"
                      )
                  ],
              ),
          ],
      ),
      dict(
          testcase_name="with keyword specific instructions",
          keywords="my keyword 1, my keyword 2",
          existing_headlines=None,
          existing_descriptions=None,
          keywords_specific_instructions="Some keyword specific instructions.",
          expected_prompt=[
              generative_models.Content(
                  role="user",
                  parts=[
                      generative_models.Part.from_text(
                          "Please write 2 headlines and 1 descriptions for this"
                          " ad.\n\nKeywords: keyword 11a, keyword 11b"
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
                          "Please write 2 headlines and 1 descriptions for this"
                          " ad.\n\nKeywords: keyword 20a, keyword 20b"
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
                          f" specific instructions.\n\nPlease write 3 headlines"
                          f" and 2 descriptions for this ad.\n\nKeywords: my"
                          f" keyword 1, my keyword 2"
                      )
                  ],
              ),
          ],
      ),
      dict(
          testcase_name="with existing ad copy",
          keywords="my keyword 1, my keyword 2",
          existing_headlines=["existing headline"],
          existing_descriptions=["existing description"],
          keywords_specific_instructions="",
          expected_prompt=[
              generative_models.Content(
                  role="user",
                  parts=[
                      generative_models.Part.from_text(
                          "Please write 2 headlines and 1 descriptions for this"
                          " ad.\n\nKeywords: keyword 11a, keyword 11b"
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
                          "Please write 2 headlines and 1 descriptions for this"
                          " ad.\n\nKeywords: keyword 20a, keyword 20b"
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
                          "This ad already has 1 headlines and 1"
                          " descriptions:\n\n- headlines: ['existing"
                          " headline']\n- descriptions: ['existing"
                          " description']\n\nPlease write 2 more headlines and"
                          " 1 more descriptions to complete this"
                          " ad.\n\nKeywords: my keyword 1, my keyword 2"
                      )
                  ],
              ),
          ],
      ),
  )
  def test_construct_text_generation_requests_for_new_ad_copy_returns_expected_request(
      self,
      keywords,
      existing_headlines,
      existing_descriptions,
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
            existing_headlines=[existing_headlines],
            existing_descriptions=[existing_descriptions],
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
        existing_ad_copy=google_ads.GoogleAd(
            headlines=existing_headlines or [],
            descriptions=existing_descriptions or [],
        ),
    )
    self.assertEqual(expected_request.to_markdown(), request.to_markdown())

  @parameterized.named_parameters(
      dict(
          testcase_name="with existing ad copy",
          existing_headlines=["existing headline"],
          existing_descriptions=["existing description"],
          expected_style_similarity=0.5590658228752543,
          expected_keyword_similarity=0.5056089825975687,
      ),
      dict(
          testcase_name="without existing ad copy",
          existing_headlines=None,
          existing_descriptions=None,
          expected_style_similarity=0.5338446522650305,
          expected_keyword_similarity=0.4766861086664519,
      ),
  )
  @testing_utils.PatchGenerativeModel(
      response=(
          '{"headlines": ["generated headline 1", "generated headline 2"],'
          ' "descriptions": ["generated description"]}'
      )
  )
  def test_generate_new_ad_copy_returns_expected_response(
      self,
      generative_model_patcher,
      existing_headlines,
      existing_descriptions,
      expected_style_similarity,
      expected_keyword_similarity,
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
        existing_headlines=[existing_headlines],
        existing_descriptions=[existing_descriptions],
    )[0]

    existing_headlines = existing_headlines or []
    existing_descriptions = existing_descriptions or []
    generated_headlines = ["generated headline 1", "generated headline 2"]
    generated_descriptions = ["generated description"]

    self.assertEqual(
        response,
        copycat.CopycatResponse(
            google_ad=google_ads.GoogleAd(
                headlines=existing_headlines + generated_headlines,
                descriptions=existing_descriptions + generated_descriptions,
            ),
            keywords="my keyword 1, my keyword 2",
            evaluation_results=copycat.EvaluationResults(
                errors=[],
                warnings=[],
                headlines_are_memorised=False,
                descriptions_are_memorised=False,
                style_similarity=expected_style_similarity,
                keyword_similarity=expected_keyword_similarity,
            ),
        ),
    )

  @testing_utils.PatchGenerativeModel(response="Generated style guide.")
  def test_generate_style_guide_returns_style_guide_and_updates_attribute(
      self, generative_model_patcher
  ):

    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(20),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )
    style_guide = copycat_instance.generate_style_guide(
        company_name="My company"
    )
    self.assertEqual(style_guide, "Generated style guide.")
    self.assertEqual(copycat_instance.style_guide, "Generated style guide.")

  def test_generate_style_guide_raises_exception_if_model_fails_to_generate(
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

      with self.assertRaises(RuntimeError):
        copycat_instance.generate_style_guide(
            company_name="My company",
            additional_style_instructions="Some additional style instructions.",
            model_name="gemini-1.5-flash-001",
            temperature=0.95,
            top_k=20,
            top_p=0.95,
        )

  @parameterized.named_parameters(
      dict(testcase_name="empty company name", args=dict(company_name="")),
      dict(
          testcase_name="no exemplars or files uri provided",
          args=dict(
              company_name="My company", use_exemplar_ads=False, files_uri=""
          ),
      ),
  )
  @testing_utils.PatchGenerativeModel(response="Generated style guide.")
  def test_generate_style_guide_raises_exception_for_bad_args(
      self, generative_model_patcher, args
  ):

    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(20),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )

    with self.assertRaises(ValueError):
      copycat_instance.generate_style_guide(**args)

  @parameterized.named_parameters(
      dict(
          testcase_name="no style guide",
          generate_style_guide=False,
          style_guide_arg=None,
          expected_system_instruction="Example system instruction",
      ),
      dict(
          testcase_name="pass style guide",
          generate_style_guide=False,
          style_guide_arg="This is my style guide.",
          expected_system_instruction=(
              "Example system instruction\n\nThis is my style guide."
          ),
      ),
      dict(
          testcase_name="generated style guide",
          generate_style_guide=True,
          style_guide_arg=None,
          expected_system_instruction=(
              "Example system instruction\n\nGenerated style guide."
          ),
      ),
      dict(
          testcase_name="generated style guide overridden",
          generate_style_guide=True,
          style_guide_arg="This is my style guide.",
          expected_system_instruction=(
              "Example system instruction\n\nThis is my style guide."
          ),
      ),
      dict(
          testcase_name="generated style guide overridden with nothing",
          generate_style_guide=True,
          style_guide_arg="",
          expected_system_instruction="Example system instruction",
      ),
  )
  @testing_utils.PatchGenerativeModel(response="Generated style guide.")
  def test_construct_text_generation_requests_uses_generated_style_guide(
      self,
      generative_model_patcher,
      generate_style_guide,
      style_guide_arg,
      expected_system_instruction,
  ):
    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(n_rows=20),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )
    if generate_style_guide:
      copycat_instance.generate_style_guide(
          company_name="My company",
          additional_style_instructions="Some additional style instructions.",
          model_name="gemini-1.5-flash-001",
          temperature=0.95,
          top_k=20,
          top_p=0.95,
      )

    request = (
        copycat_instance.construct_text_generation_requests_for_new_ad_copy(
            keywords=["my keyword 1, my keyword 2"],
            existing_headlines=[["Headline 1"]],
            existing_descriptions=[["Description 1"]],
            keywords_specific_instructions=[""],
            num_in_context_examples=1,
            system_instruction="Example system instruction",
            style_guide=style_guide_arg,
        )[0]
    )
    self.assertEqual(expected_system_instruction, request.system_instruction)

  @testing_utils.PatchGenerativeModel(
      response='{"descriptions": ["generated description"]}'
  )
  def test_generate_new_ad_copy_returns_expected_response_if_headlines_is_missing(
      self,
      generative_model_patcher,
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

    # I don't want to test the similarity metrics here, so I'm just setting
    # them to None.
    response.evaluation_results.style_similarity = None
    response.evaluation_results.keyword_similarity = None

    self.assertEqual(
        response,
        copycat.CopycatResponse(
            google_ad=google_ads.GoogleAd(
                headlines=[],
                descriptions=["generated description"],
            ),
            keywords="my keyword 1, my keyword 2",
            evaluation_results=copycat.EvaluationResults(
                errors=["Invalid number of headlines for the ad format."],
                warnings=[],
                headlines_are_memorised=False,
                descriptions_are_memorised=False,
                style_similarity=None,
                keyword_similarity=None,
            ),
        ),
    )

  @testing_utils.PatchGenerativeModel(
      response='{"headlines": ["generated headline"]}'
  )
  def test_generate_new_ad_copy_returns_expected_response_if_descriptions_is_missing(
      self,
      generative_model_patcher,
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

    # I don't want to test the similarity metrics here, so I'm just setting
    # them to None.
    response.evaluation_results.style_similarity = None
    response.evaluation_results.keyword_similarity = None

    self.assertEqual(
        response,
        copycat.CopycatResponse(
            google_ad=google_ads.GoogleAd(
                headlines=["generated headline"],
                descriptions=[],
            ),
            keywords="my keyword 1, my keyword 2",
            evaluation_results=copycat.EvaluationResults(
                errors=["Invalid number of descriptions for the ad format."],
                warnings=[],
                headlines_are_memorised=False,
                descriptions_are_memorised=False,
                style_similarity=None,
                keyword_similarity=None,
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

  @parameterized.named_parameters(
      dict(
          testcase_name="with existing ad copy",
          existing_headlines=["existing headline"],
          existing_descriptions=["existing description"],
      ),
      dict(
          testcase_name="without existing ad copy",
          existing_headlines=None,
          existing_descriptions=None,
      ),
  )
  @testing_utils.PatchGenerativeModel(response="not a json")
  def test_generate_new_ad_copy_returns_expected_response_for_non_json_chat_model_output(
      self, generative_model_patcher, existing_headlines, existing_descriptions
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
        existing_headlines=[existing_headlines],
        existing_descriptions=[existing_descriptions],
    )[0]

    # I don't want to test the similarity metrics here, so I'm just setting
    # them to None.
    response.evaluation_results.style_similarity = None
    response.evaluation_results.keyword_similarity = None

    self.assertEqual(
        response,
        copycat.CopycatResponse(
            keywords="my keyword 1, my keyword 2",
            google_ad=google_ads.GoogleAd(
                headlines=existing_headlines or [],
                descriptions=existing_descriptions or [],
            ),
            evaluation_results=copycat.EvaluationResults(
                errors=[
                    "1 validation error for GoogleAd\n  Invalid JSON: expected"
                    " ident at line 1 column 2 [type=json_invalid,"
                    " input_value='not a json', input_type=str]\n    For"
                    " further information visit"
                    " https://errors.pydantic.dev/2.6/v/json_invalid"
                ],
                warnings=[],
                headlines_are_memorised=False if existing_headlines else None,
                descriptions_are_memorised=False
                if existing_descriptions
                else None,
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

  @parameterized.named_parameters(
      dict(
          testcase_name="with existing ad copy",
          existing_headlines=["existing headline"],
          existing_descriptions=["existing description"],
          expected_style_similarity=0.569982855557986,
          expected_keyword_similarity=0.49631553094971914,
      ),
      dict(
          testcase_name="without existing ad copy",
          existing_headlines=None,
          existing_descriptions=None,
          expected_style_similarity=None,
          expected_keyword_similarity=None,
      ),
  )
  def test_generate_new_ad_copy_returns_expected_response_if_chat_model_fails_to_generate(
      self,
      existing_headlines,
      existing_descriptions,
      expected_style_similarity,
      expected_keyword_similarity,
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
          existing_headlines=[existing_headlines],
          existing_descriptions=[existing_descriptions],
      )[0]

      expected_google_ad = google_ads.GoogleAd(
          headlines=existing_headlines or [],
          descriptions=existing_descriptions or [],
      )

      expected_response = copycat.CopycatResponse(
          google_ad=expected_google_ad,
          keywords="my keyword 1, my keyword 2",
          evaluation_results=copycat.EvaluationResults(
              errors=[str(failed_response.candidates[0])],
              warnings=[],
              headlines_are_memorised=False if existing_headlines else None,
              descriptions_are_memorised=False
              if existing_descriptions
              else None,
              style_similarity=expected_style_similarity,
              keyword_similarity=expected_keyword_similarity,
          ),
      )
      self.assertEqual(response, expected_response)

  def test_to_dict_and_from_dict_returns_same_copycat_instance(self):

    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(3),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )
    copycat_instance.style_guide = "This is my style guide."

    reloaded_copycat_instance = copycat.Copycat.from_dict(
        copycat_instance.to_dict()
    )

    self.assertTrue(
        testing_utils.copycat_instances_are_equal(
            copycat_instance, reloaded_copycat_instance
        )
    )

  @parameterized.parameters([
      "ad_copy_vectorstore",
      "ad_format",
  ])
  def test_from_dict_raises_key_error_if_required_key_is_missing(
      self, required_key
  ):
    with self.assertRaises(KeyError):
      copycat_instance = copycat.Copycat.create_from_pandas(
          training_data=self.training_data(3),
          embedding_model_name="text-embedding-004",
          ad_format="text_ad",
          vectorstore_exemplar_selection_method="random",
      )
      copycat_instance_dict = copycat_instance.to_dict()
      del copycat_instance_dict[required_key]
      copycat.Copycat.from_dict(copycat_instance_dict)

  def test_to_json_and_from_json_returns_same_copycat_instance(self):

    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(3),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )
    copycat_instance.style_guide = "This is my style guide."

    reloaded_copycat_instance = copycat.Copycat.from_json(
        copycat_instance.to_json()
    )

    self.assertTrue(
        testing_utils.copycat_instances_are_equal(
            copycat_instance, reloaded_copycat_instance
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
  def test_generate_new_ad_copy_raises_exception_if_different_number_of_keywords_and_existing_headlines(
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
        "keywords and existing_headlines must have the same length.",
    ):
      copycat_instance.generate_new_ad_copy(
          keywords=["my keyword 1, my keyword 2"],
          existing_headlines=[
              ["headline 1"],
              ["headline 2"],
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
  def test_generate_new_ad_copy_raises_exception_if_different_number_of_keywords_and_existing_descriptions(
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
        "keywords and existing_descriptions must have the same length.",
    ):
      copycat_instance.generate_new_ad_copy(
          keywords=["my keyword 1, my keyword 2"],
          existing_descriptions=[
              ["description 1"],
              ["description 2"],
          ],
          style_guide="This is my style guide.",
          num_in_context_examples=2,
          system_instruction_kwargs=dict(
              company_name="My company",
              language="english",
          ),
      )

  @parameterized.named_parameters([
      dict(
          testcase_name="with_keyword_specific_instructions",
          keywords_specific_instructions=[
              "Some keyword specific instructions."
          ],
          existing_headlines=None,
          existing_descriptions=None,
          expected_final_message=(
              "For the next set of keywords, please consider the following"
              " additional instructions:\n\nSome keyword specific"
              " instructions.\n\nPlease write 3 headlines and 2 descriptions"
              " for this ad.\n\nKeywords: my keyword 1, my keyword 2"
          ),
      ),
      dict(
          testcase_name="without_keyword_specific_instructions",
          keywords_specific_instructions=None,
          existing_headlines=None,
          existing_descriptions=None,
          expected_final_message=(
              "Please write 3 headlines and 2 descriptions"
              " for this ad.\n\nKeywords: my keyword 1, my keyword 2"
          ),
      ),
      dict(
          testcase_name="with_existing_headlines_and_descriptions",
          keywords_specific_instructions=None,
          existing_headlines=[["existing headline 1"]],
          existing_descriptions=[
              ["existing description 1"],
          ],
          expected_final_message=(
              "This ad already has 1 headlines and 1 descriptions:\n\n-"
              " headlines: ['existing headline 1']\n- descriptions: ['existing"
              " description 1']\n\nPlease write 2 more headlines and 1 more"
              " descriptions to complete this ad.\n\nKeywords: my keyword 1, my"
              " keyword 2"
          ),
      ),
  ])
  @testing_utils.PatchGenerativeModel(
      response=(
          '{"headlines": ["generated headline 1", "generated headline 2"],'
          ' "descriptions": ["generated description"]}'
      )
  )
  def test_generate_new_ad_copy_uses_expected_prompt_final_message(
      self,
      generative_model_patcher,
      keywords_specific_instructions,
      existing_headlines,
      existing_descriptions,
      expected_final_message,
  ):
    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(20),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )

    _ = copycat_instance.generate_new_ad_copy(
        keywords=["my keyword 1, my keyword 2"],
        keywords_specific_instructions=keywords_specific_instructions,
        style_guide="This is my style guide.",
        num_in_context_examples=2,
        system_instruction_kwargs=dict(
            company_name="My company",
            language="english",
        ),
        existing_headlines=existing_headlines,
        existing_descriptions=existing_descriptions,
    )[0]

    mock_generate_content_async = (
        generative_model_patcher.mock_generative_model.generate_content_async
    )

    self.assertEqual(
        mock_generate_content_async.call_args[0][0][-1].parts[0].text,
        expected_final_message,
    )

  @testing_utils.PatchGenerativeModel(
      response=(
          '{"headlines": ["generated headline 1", "generated headline 2"],'
          ' "descriptions": ["generated description"]}'
      )
  )
  def test_generate_new_ad_copy_for_dataframe_returns_expected_response(
      self,
      generative_model_patcher,
  ):
    data = pd.DataFrame({
        "keywords": ["my keyword 1, my keyword 2", "my keyword 3"],
        "keywords_specific_instructions": [
            "Some keyword specific instructions.",
            "",
        ],
        "existing_headlines": [["existing headline 1"], []],
        "existing_descriptions": [["existing description 1"], []],
    })

    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(20),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )
    response_series = copycat_instance.generate_new_ad_copy_for_dataframe(
        data,
        style_guide="This is my style guide.",
        num_in_context_examples=2,
        system_instruction_kwargs=dict(
            company_name="My company",
            language="english",
        ),
    )

    for response in response_series:
      # I don't want to test the similarity metrics here, so I'm just setting
      # them to None.
      response.evaluation_results.style_similarity = None
      response.evaluation_results.keyword_similarity = None

    expected_response_series = pd.Series([
        copycat.CopycatResponse(
            google_ad=google_ads.GoogleAd(
                headlines=[
                    "existing headline 1",
                    "generated headline 1",
                    "generated headline 2",
                ],
                descriptions=[
                    "existing description 1",
                    "generated description",
                ],
            ),
            keywords="my keyword 1, my keyword 2",
            evaluation_results=copycat.EvaluationResults(
                errors=[],
                warnings=[],
                headlines_are_memorised=False,
                descriptions_are_memorised=False,
                style_similarity=None,
                keyword_similarity=None,
            ),
        ),
        copycat.CopycatResponse(
            google_ad=google_ads.GoogleAd(
                headlines=["generated headline 1", "generated headline 2"],
                descriptions=["generated description"],
            ),
            keywords="my keyword 3",
            evaluation_results=copycat.EvaluationResults(
                errors=[],
                warnings=[],
                headlines_are_memorised=False,
                descriptions_are_memorised=False,
                style_similarity=None,
                keyword_similarity=None,
            ),
        ),
    ])

    pd.testing.assert_series_equal(response_series, expected_response_series)

  @testing_utils.PatchGenerativeModel(
      response=(
          '{"headlines": ["generated headline 1", "generated headline 2"],'
          ' "descriptions": ["generated description"]}'
      )
  )
  def test_generate_new_ad_copy_for_dataframe_returns_expected_response_if_only_keywords_column_is_provided(
      self,
      generative_model_patcher,
  ):
    data = pd.DataFrame({
        "keywords": ["my keyword 1, my keyword 2", "my keyword 3"],
    })

    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(20),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )
    response_series = copycat_instance.generate_new_ad_copy_for_dataframe(
        data,
        style_guide="This is my style guide.",
        num_in_context_examples=2,
        system_instruction_kwargs=dict(
            company_name="My company",
            language="english",
        ),
    )

    for response in response_series:
      # I don't want to test the similarity metrics here, so I'm just setting
      # them to None.
      response.evaluation_results.style_similarity = None
      response.evaluation_results.keyword_similarity = None

    expected_response_series = pd.Series([
        copycat.CopycatResponse(
            google_ad=google_ads.GoogleAd(
                headlines=[
                    "generated headline 1",
                    "generated headline 2",
                ],
                descriptions=[
                    "generated description",
                ],
            ),
            keywords="my keyword 1, my keyword 2",
            evaluation_results=copycat.EvaluationResults(
                errors=[],
                warnings=[],
                headlines_are_memorised=False,
                descriptions_are_memorised=False,
                style_similarity=None,
                keyword_similarity=None,
            ),
        ),
        copycat.CopycatResponse(
            google_ad=google_ads.GoogleAd(
                headlines=["generated headline 1", "generated headline 2"],
                descriptions=["generated description"],
            ),
            keywords="my keyword 3",
            evaluation_results=copycat.EvaluationResults(
                errors=[],
                warnings=[],
                headlines_are_memorised=False,
                descriptions_are_memorised=False,
                style_similarity=None,
                keyword_similarity=None,
            ),
        ),
    ])

    pd.testing.assert_series_equal(response_series, expected_response_series)

  @testing_utils.PatchGenerativeModel(
      response=(
          '{"headlines": ["generated headline 1", "generated headline 2"],'
          ' "descriptions": ["generated description"]}'
      )
  )
  def test_generate_new_ad_copy_for_dataframe_raises_exception_if_keywords_column_is_missing(
      self,
      generative_model_patcher,
  ):
    data = pd.DataFrame({
        "keywords_specific_instructions": [
            "Some keyword specific instructions.",
            "",
        ],
        "existing_headlines": [["existing headline 1"], []],
        "existing_descriptions": [["existing description 1"], []],
    })

    copycat_instance = copycat.Copycat.create_from_pandas(
        training_data=self.training_data(20),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        vectorstore_exemplar_selection_method="random",
    )
    with self.assertRaisesWithLiteralMatch(
        ValueError,
        "The dataframe does not contain the required column: keywords",
    ):
      copycat_instance.generate_new_ad_copy_for_dataframe(
          data,
          style_guide="This is my style guide.",
          num_in_context_examples=2,
          system_instruction_kwargs=dict(
              company_name="My company",
              language="english",
          ),
      )


if __name__ == "__main__":
  absltest.main()
