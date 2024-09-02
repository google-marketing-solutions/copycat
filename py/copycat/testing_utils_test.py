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
from vertexai import generative_models
from vertexai import language_models
import pandas as pd

from copycat import testing_utils


ad_copy_generator = testing_utils.ad_copy_generator
copycat = testing_utils.copycat


class PatchEmbeddingsModelTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()
    self.input_texts = [
        language_models.TextEmbeddingInput(
            text="Test 1", task_type="RETRIEVAL_DOCUMENT"
        ),
        language_models.TextEmbeddingInput(
            text="Test 2", task_type="RETRIEVAL_DOCUMENT"
        ),
    ]

  def test_random_embeddings_returns_expected_embeddings(self):
    # If this test fails then something has changed with the random number
    # generation used by the mock embedding model. This shouldn't happen,
    # but if it does just fix all tests, because it's nothing to do with
    # copycat.
    embeddings = testing_utils.random_embeddings(
        [
            language_models.TextEmbeddingInput(
                text="Test 1", task_type="RETRIEVAL_DOCUMENT"
            )
        ],
        output_dimensionality=5,
    )[0].values
    self.assertListEqual(
        embeddings,
        [
            0.2501313331234188,
            -0.4632126439646736,
            1.0048817101237066,
            0.53742307130886,
            -0.23405590135295984,
        ],
    )

  @testing_utils.PatchEmbeddingsModel()
  def test_get_embeddings_returns_list_of_embeddings(
      self, embeddings_model_patcher
  ):
    model = language_models.TextEmbeddingModel.from_pretrained("test_model")
    doc_embeddings = model.get_embeddings(
        self.input_texts, output_dimensionality=768
    )
    doc_embeddings = [emb.values for emb in doc_embeddings]

    self.assertLen(doc_embeddings, 2)
    self.assertLen(doc_embeddings[0], 768)
    self.assertLen(doc_embeddings[1], 768)

  @testing_utils.PatchEmbeddingsModel()
  def test_embeddings_are_deterministic(self, embeddings_model_patcher):
    model = language_models.TextEmbeddingModel.from_pretrained("test_model")
    doc_embeddings = model.get_embeddings(
        self.input_texts, output_dimensionality=768
    )
    doc_embeddings_2 = model.get_embeddings(
        self.input_texts, output_dimensionality=768
    )
    doc_embeddings = [emb.values for emb in doc_embeddings]
    doc_embeddings_2 = [emb.values for emb in doc_embeddings_2]
    self.assertSequenceEqual(doc_embeddings, doc_embeddings_2)

  @testing_utils.PatchEmbeddingsModel()
  def test_embeddings_depend_on_text_input(self, embeddings_model_patcher):
    model = language_models.TextEmbeddingModel.from_pretrained("test_model")
    doc_embeddings = model.get_embeddings(
        self.input_texts, output_dimensionality=768
    )
    doc_embeddings = [emb.values for emb in doc_embeddings]
    self.assertNotEqual(doc_embeddings[0], doc_embeddings[1])

  def test_patch_works_as_a_context_manager(self):
    with testing_utils.PatchEmbeddingsModel() as embeddings_model_patcher:
      model = language_models.TextEmbeddingModel.from_pretrained("test_model")
      doc_embeddings = model.get_embeddings(
          self.input_texts, output_dimensionality=768
      )
      doc_embeddings = [emb.values for emb in doc_embeddings]
      self.assertLen(doc_embeddings, 2)
      self.assertLen(doc_embeddings[0], 768)
      self.assertLen(doc_embeddings[1], 768)


class PatchGenerativeModelTest(parameterized.TestCase):

  def test_patch_works_as_a_context_manager(self):
    with testing_utils.PatchGenerativeModel(
        response="Response text"
    ) as generative_model_patcher:
      model = generative_models.GenerativeModel(model_name="test-model")
      response = model.generate_content("Example prompt")
      expected_response = generative_models.GenerationResponse.from_dict({
          "candidates": [{
              "finish_reason": generative_models.FinishReason.STOP,
              "content": {
                  "role": "model",
                  "parts": [{"text": "Response text"}],
              },
          }]
      })

      self.assertDictEqual(response.to_dict(), expected_response.to_dict())

      generative_model_patcher.mock_init.assert_called_once_with(
          model_name="test-model"
      )
      generative_model_patcher.mock_generative_model.generate_content.assert_called_once_with(
          "Example prompt"
      )

  @testing_utils.PatchGenerativeModel(response="Response text")
  def test_patch_works_as_a_decorator(self, generative_model_patcher):
    model = generative_models.GenerativeModel(model_name="test-model")
    response = model.generate_content("Example prompt")
    expected_response = generative_models.GenerationResponse.from_dict({
        "candidates": [{
            "finish_reason": generative_models.FinishReason.STOP,
            "content": {
                "role": "model",
                "parts": [{"text": "Response text"}],
            },
        }]
    })

    self.assertDictEqual(response.to_dict(), expected_response.to_dict())

    generative_model_patcher.mock_init.assert_called_once_with(
        model_name="test-model"
    )
    generative_model_patcher.mock_generative_model.generate_content.assert_called_once_with(
        "Example prompt"
    )

  def test_patch_can_produce_failed_response(self):
    with testing_utils.PatchGenerativeModel(
        response=generative_models.GenerationResponse.from_dict({
            "candidates": [{
                "finish_reason": generative_models.FinishReason.SAFETY,
            }]
        })
    ):
      expected_response = generative_models.GenerationResponse.from_dict({
          "candidates": [{
              "finish_reason": generative_models.FinishReason.SAFETY,
          }]
      })
      model = generative_models.GenerativeModel(model_name="test-model")
      self.assertDictEqual(
          model.generate_content("example prompt").to_dict(),
          expected_response.to_dict(),
      )


class ValuesAreEqualTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()
    self.embedding_model_patcher = testing_utils.PatchEmbeddingsModel()
    self.embedding_model_patcher.start()

  def tearDown(self):
    super().tearDown()
    self.embedding_model_patcher.stop()

  @parameterized.parameters(
      (1, 1, True),
      (1, 2, False),
      ([1], [1], True),
      ([1], [2], False),
      ([1], 1, False),
      ([1], (1,), True),
      ([[1, 2], 3], [[1, 2], 3], True),
      ([[1, 2], 3], [[3], 3], False),
      ({"a": 1}, {"a": 1}, True),
      ({"a": 1}, {"a": 2}, False),
      ({"a": 1}, {"b": 1}, False),
  )
  def test_values_are_equal(self, a, b, expected):
    self.assertEqual(testing_utils.values_are_equal(a, b), expected)

  @parameterized.parameters(
      (None, True),
      ("training_data", False),
      ("embedding_model_name", False),
      ("dimensionality", False),
      ("embeddings_batch_size", False),
  )
  def test_vectorstore_instances_are_equal(self, different_param, expected):
    params_1 = dict(
        training_data=pd.DataFrame({
            "headlines": [["headline 1"], ["headline 2"]],
            "descriptions": [["description 1"], ["description 2"]],
            "keywords": ["keyword 1", "keyword 2"],
        }),
        embedding_model_name="text-embedding-004",
        dimensionality=256,
        max_initial_ads=10,
        max_exemplar_ads=10,
        affinity_preference=-1,
        embeddings_batch_size=50,
    )

    params_2 = params_1.copy()
    if different_param:
      params_2[different_param] = dict(
          training_data=pd.DataFrame({
              "headlines": [["headline 3"], ["headline 2"]],
              "descriptions": [["description 1"], ["description 2"]],
              "keywords": ["keyword 1", "keyword 5"],
          }),
          embedding_model_name="text-multilingual-embedding-002",
          dimensionality=500,
          max_initial_ads=20,
          max_exemplar_ads=30,
          affinity_preference=-2,
          embeddings_batch_size=100,
      )[different_param]

    vectorstore_1 = ad_copy_generator.AdCopyVectorstore.create_from_pandas(
        **params_1
    )

    vectorstore_2 = ad_copy_generator.AdCopyVectorstore.create_from_pandas(
        **params_2
    )

    self.assertEqual(
        testing_utils.vectorstore_instances_are_equal(
            vectorstore_1, vectorstore_2
        ),
        expected,
    )

  def test_vectorstore_instances_are_equal_returns_false_for_different_types(
      self,
  ):
    vectorstore_1 = ad_copy_generator.AdCopyVectorstore.create_from_pandas(
        training_data=pd.DataFrame({
            "headlines": [["headline 1"], ["headline 2"]],
            "descriptions": [["description 1"], ["description 2"]],
            "keywords": ["keyword 1", "keyword 2"],
        }),
        embedding_model_name="text-embedding-004",
        dimensionality=256,
        max_initial_ads=10,
        max_exemplar_ads=10,
        affinity_preference=-1,
        embeddings_batch_size=50,
    )
    not_a_vectorstore = "not a vectorstore"
    self.assertFalse(
        testing_utils.vectorstore_instances_are_equal(
            vectorstore_1, not_a_vectorstore
        )
    )
    self.assertFalse(
        testing_utils.vectorstore_instances_are_equal(
            not_a_vectorstore, vectorstore_1
        )
    )

  @parameterized.parameters(
      (None, True),
      ("training_data", False),
      ("embedding_model_name", False),
      ("ad_format", False),
      ("embedding_model_dimensionality", False),
      ("embedding_model_batch_size", False),
  )
  def test_copycat_instances_are_equal(self, different_param, expected):
    params_1 = dict(
        training_data=pd.DataFrame({
            "headlines": [
                ["headline 1", "headline 2", "headline 3"],
                ["headline 2", "headline 3", "headline 4"],
            ],
            "descriptions": [
                ["description 1", "description 2"],
                ["description 2", "description 3"],
            ],
            "keywords": ["keyword 1", "keyword 2"],
        }),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
    )

    params_2 = params_1.copy()
    if different_param:
      params_2[different_param] = dict(
          training_data=pd.DataFrame({
              "headlines": [
                  ["headline 1", "headline 4", "headline 3"],
                  ["headline 2", "headline 3", "headline 4"],
              ],
              "descriptions": [
                  ["description 1", "description 2"],
                  ["description 2", "description 5"],
              ],
              "keywords": ["keyword 1", "keyword 2"],
          }),
          embedding_model_name="text-multilingual-embedding-002",
          ad_format="responsive_search_ad",
          embedding_model_dimensionality=500,
          vectorstore_max_initial_ads=20,
          vectorstore_max_exemplar_ads=30,
          vectorstore_affinity_preference=-2,
          embedding_model_batch_size=100,
      )[different_param]

    copycat_1 = copycat.Copycat.create_from_pandas(**params_1)

    copycat_2 = copycat.Copycat.create_from_pandas(**params_2)

    self.assertEqual(
        testing_utils.copycat_instances_are_equal(copycat_1, copycat_2),
        expected,
    )

  def test_copycat_instances_are_equal_returns_false_for_different_types(
      self,
  ):
    copycat_1 = copycat.Copycat.create_from_pandas(
        training_data=pd.DataFrame({
            "headlines": [["headline 1"], ["headline 2"]],
            "descriptions": [["description 1"], ["description 2"]],
            "keywords": ["keyword 1", "keyword 2"],
        }),
        embedding_model_name="text-embedding-004",
        ad_format="text_ad",
        embedding_model_dimensionality=256,
        vectorstore_max_initial_ads=10,
        vectorstore_max_exemplar_ads=10,
        vectorstore_affinity_preference=-1,
        embedding_model_batch_size=50,
    )

    not_copycat = "not a copycat instance"

    self.assertFalse(
        testing_utils.copycat_instances_are_equal(copycat_1, not_copycat)
    )
    self.assertFalse(
        testing_utils.copycat_instances_are_equal(not_copycat, copycat_1)
    )


if __name__ == "__main__":
  absltest.main()
