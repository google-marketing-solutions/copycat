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
import mock
import pandas as pd

from copycat import ad_copy_evaluator
from copycat import ad_copy_generator
from copycat import google_ads
from copycat import testing_utils


class AdCopyEvaluatorTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()
    self.embedding_model_patcher = testing_utils.PatchEmbeddingsModel()
    self.embedding_model_patcher.start()

    training_data = pd.DataFrame({
        "headlines": [[f"train headline {i}"] for i in range(20)],
        "descriptions": [[f"train description {i}"] for i in range(20)],
        "keywords": [f"keyword {i}a, keyword {i}b" for i in range(20)],
    })

    self.ad_copy_vectorstore = (
        ad_copy_generator.AdCopyVectorstore.create_from_pandas(
            training_data=training_data,
            embedding_model_name="text-embedding-004",
            dimensionality=256,
            max_initial_ads=100,
            max_exemplar_ads=20,
            affinity_preference=None,
            embeddings_batch_size=10,
            exemplar_selection_method="random",
        )
    )

    self.ad_format = google_ads.GoogleAdFormat(
        name="test_format",
        max_headlines=15,
        min_headlines=3,
        max_descriptions=4,
        min_descriptions=2,
        max_headline_length=30,
        max_description_length=90,
    )

  def tearDown(self):
    super().tearDown()
    self.embedding_model_patcher.stop()

  def test_similarity_metrics_are_calculated_correctly(self):
    evaluator = ad_copy_evaluator.AdCopyEvaluator(
        self.ad_format,
        ad_copy_vectorstore=self.ad_copy_vectorstore,
    )

    generated_ad = google_ads.GoogleAd(
        headlines=["generated headline"], descriptions=["generated description"]
    )

    actual_metrics = evaluator.calculate_similarity_metrics_batch(
        ad_copies=[generated_ad],
        keywords=["keyword 1, keyword 2"],
    )[0]

    expected_metrics = dict(
        style_similarity=0.5366996856066526,
        keyword_similarity=0.48784862680427793,
    )
    self.assertDictEqual(actual_metrics, expected_metrics)

  @parameterized.named_parameters([
      {
          "testcase_name": "valid",
          "n_headlines": 15,
          "expected_response": True,
      },
      {
          "testcase_name": "too many",
          "n_headlines": 16,
          "expected_response": False,
      },
      {
          "testcase_name": "too few",
          "n_headlines": 2,
          "expected_response": False,
      },
  ])
  def test_has_valid_number_of_headlines(self, n_headlines, expected_response):
    evaluator = ad_copy_evaluator.AdCopyEvaluator(self.ad_format)

    google_ad = google_ads.GoogleAd(
        headlines=["Headline 1"] * n_headlines,
        descriptions=["Description 1.", "Description 2."],
    )

    self.assertEqual(
        evaluator.has_valid_number_of_headlines(google_ad), expected_response
    )

  @parameterized.named_parameters([
      {
          "testcase_name": "valid",
          "n_descriptions": 4,
          "expected_response": True,
      },
      {
          "testcase_name": "too many",
          "n_descriptions": 5,
          "expected_response": False,
      },
      {
          "testcase_name": "too few",
          "n_descriptions": 1,
          "expected_response": False,
      },
  ])
  def test_has_valid_number_of_descriptions(
      self, n_descriptions, expected_response
  ):
    evaluator = ad_copy_evaluator.AdCopyEvaluator(self.ad_format)

    google_ad = google_ads.GoogleAd(
        headlines=["Headline 1"],
        descriptions=["Description 1."] * n_descriptions,
    )

    self.assertEqual(
        evaluator.has_valid_number_of_descriptions(google_ad), expected_response
    )

  @parameterized.named_parameters([
      {
          "testcase_name": "valid",
          "headline": "a" * 30,
          "expected_response": True,
      },
      {
          "testcase_name": "too long",
          "headline": "a" * 31,
          "expected_response": False,
      },
      {
          "testcase_name": "valid dki",
          "headline": "Valid DKI {KeyWord:my keyword} 123",
          "expected_response": True,
      },
      {
          "testcase_name": "invalid dki",
          "headline": "Invalid DKI {KeyWord:my keyword} too long!",
          "expected_response": False,
      },
  ])
  def test_has_valid_headline_lengths(self, headline, expected_response):
    evaluator = ad_copy_evaluator.AdCopyEvaluator(self.ad_format)

    google_ad = google_ads.GoogleAd(
        headlines=[headline, "headline 2"],
        descriptions=["Description 1."],
    )

    self.assertEqual(
        evaluator.has_valid_headline_lengths(google_ad), expected_response
    )

  @parameterized.named_parameters([
      {
          "testcase_name": "valid",
          "description": "a" * 90,
          "expected_response": True,
      },
      {
          "testcase_name": "too long",
          "description": "a" * 91,
          "expected_response": False,
      },
      {
          "testcase_name": "valid dki",
          "description": "Valid DKI {KeyWord:my keyword} " + "a" * 63,
          "expected_response": True,
      },
      {
          "testcase_name": "invalid dki",
          "description": "Invalid DKI {KeyWord:my keyword}" + "a" * 70,
          "expected_response": False,
      },
  ])
  def test_has_valid_description_lengths(self, description, expected_response):
    evaluator = ad_copy_evaluator.AdCopyEvaluator(self.ad_format)

    google_ad = google_ads.GoogleAd(
        headlines=["Headline 1", "headline 2"],
        descriptions=[description, "description 2"],
    )

    self.assertEqual(
        evaluator.has_valid_description_lengths(google_ad), expected_response
    )

  @parameterized.parameters(
      "has_valid_number_of_headlines",
      "has_valid_number_of_descriptions",
      "has_valid_headline_lengths",
      "has_valid_description_lengths",
  )
  def test_is_valid_fails_if_any_check_fails(self, failing_check):
    with mock.patch.object(
        ad_copy_evaluator.AdCopyEvaluator,
        failing_check,
        return_value=False,
    ):
      evaluator = ad_copy_evaluator.AdCopyEvaluator(self.ad_format)
      google_ad = google_ads.GoogleAd(
          headlines=["Headline 1", "Headline 2"],
          descriptions=["Description 1.", "Description 2."],
      )
      self.assertFalse(evaluator.is_valid(google_ad))

  @parameterized.named_parameters([
      {
          "testcase_name": "complete",
          "n_headlines": 15,
          "n_descriptions": 4,
          "expected_response": True,
      },
      {
          "testcase_name": "too few headlines",
          "n_headlines": 14,
          "n_descriptions": 4,
          "expected_response": False,
      },
      {
          "testcase_name": "too few descriptions",
          "n_headlines": 15,
          "n_descriptions": 3,
          "expected_response": False,
      },
      {
          "testcase_name": "too many headlines",
          "n_headlines": 16,
          "n_descriptions": 4,
          "expected_response": False,
      },
      {
          "testcase_name": "too many descriptions",
          "n_headlines": 15,
          "n_descriptions": 5,
          "expected_response": False,
      },
  ])
  def test_is_complete_checks_if_headlines_and_descriptions_are_full(
      self, n_headlines, n_descriptions, expected_response
  ):
    evaluator = ad_copy_evaluator.AdCopyEvaluator(self.ad_format)
    google_ad = google_ads.GoogleAd(
        headlines=list(map(str, range(n_headlines))),
        descriptions=list(map(str, range(n_descriptions))),
    )

    self.assertEqual(evaluator.is_complete(google_ad), expected_response)

  @parameterized.named_parameters([
      {
          "testcase_name": "enough headlines and descriptions",
          "n_headlines": 3,
          "n_descriptions": 2,
          "expected_response": False,
      },
      {
          "testcase_name": "too few headlines",
          "n_headlines": 2,
          "n_descriptions": 2,
          "expected_response": True,
      },
      {
          "testcase_name": "too few descriptions",
          "n_headlines": 3,
          "n_descriptions": 1,
          "expected_response": True,
      },
      {
          "testcase_name": "too few both",
          "n_headlines": 2,
          "n_descriptions": 1,
          "expected_response": True,
      },
  ])
  def test_is_underpopulated_checks_if_too_few_headlines_or_descriptions(
      self, n_headlines, n_descriptions, expected_response
  ):
    evaluator = ad_copy_evaluator.AdCopyEvaluator(self.ad_format)

    google_ad = google_ads.GoogleAd(
        headlines=list(map(str, range(n_headlines))),
        descriptions=list(map(str, range(n_descriptions))),
    )

    self.assertEqual(evaluator.is_underpopulated(google_ad), expected_response)

  @parameterized.named_parameters([
      {
          "testcase_name": "has headlines and descriptions",
          "n_headlines": 1,
          "n_descriptions": 1,
          "expected_response": False,
      },
      {
          "testcase_name": "no headlines",
          "n_headlines": 0,
          "n_descriptions": 1,
          "expected_response": False,
      },
      {
          "testcase_name": "no descriptions",
          "n_headlines": 1,
          "n_descriptions": 0,
          "expected_response": False,
      },
      {
          "testcase_name": "is empty",
          "n_headlines": 0,
          "n_descriptions": 0,
          "expected_response": True,
      },
  ])
  def test_is_empty_checks_if_zero_headlines_and_descriptions(
      self, n_headlines, n_descriptions, expected_response
  ):
    evaluator = ad_copy_evaluator.AdCopyEvaluator(self.ad_format)

    google_ad = google_ads.GoogleAd(
        headlines=list(map(str, range(n_headlines))),
        descriptions=list(map(str, range(n_descriptions))),
    )

    self.assertEqual(evaluator.is_empty(google_ad), expected_response)

  @parameterized.named_parameters(
      dict(
          testcase_name="not memorised",
          generated_headlines=["new headline", "train headline 1"],
          generated_descriptions=["new description", "train description 1"],
          allow_memorised_headlines=False,
          allow_memorised_descriptions=False,
          expected_headlines_are_memorised=False,
          expected_descriptions_are_memorised=False,
          expected_errors=[],
      ),
      dict(
          testcase_name="headline memorised but allowed",
          generated_headlines=["train headline 1"],
          generated_descriptions=["new description", "train description 1"],
          allow_memorised_headlines=True,
          allow_memorised_descriptions=False,
          expected_headlines_are_memorised=True,
          expected_descriptions_are_memorised=False,
          expected_errors=[],
      ),
      dict(
          testcase_name="headline memorised but not allowed",
          generated_headlines=["train headline 1"],
          generated_descriptions=["new description", "train description 1"],
          allow_memorised_headlines=False,
          allow_memorised_descriptions=False,
          expected_headlines_are_memorised=True,
          expected_descriptions_are_memorised=False,
          expected_errors=[
              "All headlines are memorised from the training data."
          ],
      ),
      dict(
          testcase_name="description memorised but allowed",
          generated_headlines=["new headline", "train headline 1"],
          generated_descriptions=["train description 1"],
          allow_memorised_headlines=False,
          allow_memorised_descriptions=True,
          expected_headlines_are_memorised=False,
          expected_descriptions_are_memorised=True,
          expected_errors=[],
      ),
      dict(
          testcase_name="description memorised but not allowed",
          generated_headlines=["new headline", "train headline 1"],
          generated_descriptions=["train description 1"],
          allow_memorised_headlines=False,
          allow_memorised_descriptions=False,
          expected_headlines_are_memorised=False,
          expected_descriptions_are_memorised=True,
          expected_errors=[
              "All descriptions are memorised from the training data."
          ],
      ),
      dict(
          testcase_name="both memorised but allowed",
          generated_headlines=["train headline 1"],
          generated_descriptions=["train description 1"],
          allow_memorised_headlines=True,
          allow_memorised_descriptions=True,
          expected_headlines_are_memorised=True,
          expected_descriptions_are_memorised=True,
          expected_errors=[],
      ),
      dict(
          testcase_name="both memorised but not allowed",
          generated_headlines=["train headline 1"],
          generated_descriptions=["train description 1"],
          allow_memorised_headlines=False,
          allow_memorised_descriptions=False,
          expected_headlines_are_memorised=True,
          expected_descriptions_are_memorised=True,
          expected_errors=[
              "All headlines are memorised from the training data.",
              "All descriptions are memorised from the training data.",
          ],
      ),
  )
  def test_check_ad_copy_memorisation(
      self,
      generated_headlines,
      generated_descriptions,
      allow_memorised_headlines,
      allow_memorised_descriptions,
      expected_headlines_are_memorised,
      expected_descriptions_are_memorised,
      expected_errors,
  ):
    test_ad_foramt = google_ads.GoogleAdFormat(
        name="test_format",
        max_headlines=15,
        min_headlines=1,
        max_descriptions=4,
        min_descriptions=1,
        max_headline_length=30,
        max_description_length=90,
    )
    evaluator = ad_copy_evaluator.AdCopyEvaluator(
        test_ad_foramt, self.ad_copy_vectorstore
    )
    ad_copy = google_ads.GoogleAd(
        headlines=generated_headlines, descriptions=generated_descriptions
    )

    results = evaluator.evaluate_batch(
        [ad_copy],
        allow_memorised_headlines=allow_memorised_headlines,
        allow_memorised_descriptions=allow_memorised_descriptions,
    )[0]

    self.assertEqual(
        expected_headlines_are_memorised, results.headlines_are_memorised
    )
    self.assertEqual(
        expected_descriptions_are_memorised, results.descriptions_are_memorised
    )
    self.assertCountEqual(expected_errors, results.errors)

  def test_evaluate_returns_expected_results_with_vectorstore(self):
    evaluator = ad_copy_evaluator.AdCopyEvaluator(
        self.ad_format,
        ad_copy_vectorstore=self.ad_copy_vectorstore,
    )

    ad_copy = google_ads.GoogleAd(
        headlines=["headline 1", "headline 2", "headline 3"],
        descriptions=["description 1", "description 2"],
    )

    results = evaluator.evaluate_batch(
        [ad_copy],
        allow_memorised_headlines=False,
        allow_memorised_descriptions=False,
        keywords=["keyword 1, keyword 2"],
    )[0]

    expected_results = ad_copy_evaluator.EvaluationResults(
        errors=[],
        warnings=[],
        headlines_are_memorised=False,
        descriptions_are_memorised=False,
        keyword_similarity=0.5023139051908866,
        style_similarity=0.5617324461155475,
    )
    self.assertEqual(results, expected_results)

  def test_evaluate_returns_expected_results_without_vectorstore(self):
    evaluator = ad_copy_evaluator.AdCopyEvaluator(
        self.ad_format,
    )

    ad_copy = google_ads.GoogleAd(
        headlines=["headline 1", "headline 2", "headline 3"],
        descriptions=["description 1", "description 2"],
    )

    results = evaluator.evaluate_batch(
        [ad_copy],
        allow_memorised_headlines=False,
        allow_memorised_descriptions=False,
        keywords=["keyword 1, keyword 2"],
    )[0]

    expected_results = ad_copy_evaluator.EvaluationResults(
        errors=[],
        warnings=[],
        headlines_are_memorised=False,
        descriptions_are_memorised=False,
        keyword_similarity=None,
        style_similarity=None,
    )
    self.assertEqual(results, expected_results)

  def test_evaluate_returns_expected_results_with_vectorstore_no_keywords(self):
    evaluator = ad_copy_evaluator.AdCopyEvaluator(
        self.ad_format,
        ad_copy_vectorstore=self.ad_copy_vectorstore,
    )

    ad_copy = google_ads.GoogleAd(
        headlines=["headline 1", "headline 2", "headline 3"],
        descriptions=["description 1", "description 2"],
    )

    results = evaluator.evaluate_batch(
        [ad_copy],
        allow_memorised_headlines=False,
        allow_memorised_descriptions=False,
    )[0]

    expected_results = ad_copy_evaluator.EvaluationResults(
        errors=[],
        warnings=[],
        headlines_are_memorised=False,
        descriptions_are_memorised=False,
        keyword_similarity=None,
        style_similarity=None,
    )
    self.assertEqual(results, expected_results)

  def test_evaluate_returns_expected_results_with_vectorstore_empty_ad(self):
    evaluator = ad_copy_evaluator.AdCopyEvaluator(
        self.ad_format,
        ad_copy_vectorstore=self.ad_copy_vectorstore,
    )

    ad_copy = google_ads.GoogleAd(headlines=[], descriptions=[])

    results = evaluator.evaluate_batch(
        [ad_copy],
        allow_memorised_headlines=False,
        allow_memorised_descriptions=False,
        keywords=["keyword 1, keyword 2"],
    )[0]

    expected_results = ad_copy_evaluator.EvaluationResults(
        errors=[
            "Invalid number of headlines for the ad format.",
            "Invalid number of descriptions for the ad format.",
        ],
        warnings=[],
        headlines_are_memorised=False,
        descriptions_are_memorised=False,
        keyword_similarity=None,
        style_similarity=None,
    )
    self.assertEqual(results, expected_results)

  @parameterized.named_parameters([
      {
          "testcase_name": "no special variables",
          "headlines": ["headline 1", "headline 2"],
          "descriptions": ["description 1", "description 2"],
          "expected_response": False,
      },
      {
          "testcase_name": "headline dki",
          "headlines": ["headline {KeyWord:my keyword}", "headline 2"],
          "descriptions": ["description 1", "description 2"],
          "expected_response": False,
      },
      {
          "testcase_name": "description dki",
          "headlines": ["headline 1", "headline 2"],
          "descriptions": ["description {KeyWord:my keyword}", "description 2"],
          "expected_response": False,
      },
      {
          "testcase_name": "headline customizer",
          "headlines": [
              "headline {CUSTOMIZER.product:my product}",
              "headline 2",
          ],
          "descriptions": ["description 1", "description 2"],
          "expected_response": False,
      },
      {
          "testcase_name": "description customizer",
          "headlines": ["headline 1", "headline 2"],
          "descriptions": [
              "description {CUSTOMIZER.product:my product}",
              "description 2",
          ],
          "expected_response": False,
      },
      {
          "testcase_name": "headline customizer no default",
          "headlines": ["headline {CUSTOMIZER.product}", "headline 2"],
          "descriptions": ["description 1", "description 2"],
          "expected_response": True,
      },
      {
          "testcase_name": "description customizer no default",
          "headlines": ["headline 1", "headline 2"],
          "descriptions": ["description {CUSTOMIZER.product}", "description 2"],
          "expected_response": True,
      },
  ])
  def test_has_unfillable_google_ads_special_variables(
      self, headlines, descriptions, expected_response
  ):
    google_ad = google_ads.GoogleAd(
        headlines=headlines,
        descriptions=descriptions,
    )
    evaluator = ad_copy_evaluator.AdCopyEvaluator(self.ad_format)
    self.assertEqual(
        evaluator.has_unfillable_google_ads_special_variables(google_ad),
        expected_response,
    )


if __name__ == "__main__":
  absltest.main()
