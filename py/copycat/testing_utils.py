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

"""Models used for testing, which don't require a real VertexAI call."""

from typing import Any, Callable

from vertexai import language_models
from vertexai.generative_models import _generative_models as generative_models
import mock
import numpy as np
import pandas as pd

from copycat import ad_copy_generator
from copycat import copycat


GenerationConfigType = generative_models.GenerationConfigType
SafetySettingsType = generative_models.SafetySettingsType
PartsType = generative_models.PartsType
Tool = generative_models.Tool
ToolConfig = generative_models.ToolConfig
GenerationResponse = generative_models.GenerationResponse
ContentsType = generative_models.ContentsType


def _random_embedding(
    text: language_models.TextEmbeddingInput, output_dimensionality: int
) -> language_models.TextEmbedding:
  seed = int.from_bytes(
      (text.text + text.task_type).encode("utf-8"), byteorder="big"
  )
  embeddings = (
      np.random.Generator(np.random.MT19937(seed))
      .normal(size=output_dimensionality)
      .tolist()
  )
  return language_models.TextEmbedding(
      values=embeddings,
  )


def random_embeddings(
    texts: list[language_models.TextEmbeddingInput], output_dimensionality: int
) -> list[language_models.TextEmbedding]:
  return list(map(lambda x: _random_embedding(x, output_dimensionality), texts))


class PatchEmbeddingsModel:
  """This objects handles the patching of vertex ai embeddings models.

  This allows us to run tests without connecting to vertex ai. It will return
  a random embedding for any text.

  Context manager:
  ```
  with testing_utils.PatchEmbeddingsModel() as embeddings_model_patcher:
    model = models.VertexAIEmbeddings(model_name="test-model")
    response = model.embed_documents(["Example prompt"])
  ```

  Decorator:
  ```
  @testing_utils.PatchEmbeddingsModel()
  def test_example(self, embeddings_model_patcher):
    model = models.VertexAIEmbeddings(model_name="test-model")
    response = model.embed_documents(["Example prompt"])
  ```
  """

  def __init__(self):
    self.mock_embeddings_model = mock.MagicMock(
        spec=language_models.TextEmbeddingModel
    )

    self.mock_embeddings_model.get_embeddings.side_effect = random_embeddings
    self._from_pretrained_patcher = mock.patch(
        "vertexai.language_models.TextEmbeddingModel.from_pretrained",
        return_value=self.mock_embeddings_model,
    )

  def start(self):
    self.mock_from_pretrained = self._from_pretrained_patcher.start()

  def stop(self):
    self._from_pretrained_patcher.stop()

  def __call__(
      self, test_function: Callable[[Any], Any]
  ) -> Callable[[Any], Any]:
    def wrapped_test_function(*args, **kwargs):
      self.start()
      kwargs["embeddings_model_patcher"] = self
      test_function(*args, **kwargs)
      self.stop()

    return wrapped_test_function

  def __enter__(self) -> "PatchEmbeddingsModel":
    self.start()
    return self

  def __exit__(self, *args, **kwargs):
    self.stop()


class PatchGenerativeModel:
  """This objects handles the patching of vertex ai generative models.

  This allows us to run tests without connecting to vertex ai. It will
  always return the same response for any prompt. It can be used
  as either a decorator or a context manager:

  Context manager:
  ```
  with testing_utils.PatchGenerativeModel(
      response="Response text",
  ) as generative_model_patcher:
    model = generative_models.GenerativeModel(model_name="test-model")
    response = model.generate_content("Example prompt")
  ```

  Decorator:
  ```
  @testing_utils.PatchGenerativeModel(
      response="Response text",
  )
  def test_example(self, generative_model_patcher):
    model = generative_models.GenerativeModel(model_name="test-model")
    response = model.generate_content("Example prompt")
  ```
  """

  def __init__(self, response: str | GenerationResponse):
    self.mock_generative_model = mock.MagicMock(
        spec=generative_models.GenerativeModel
    )
    if isinstance(response, str):
      response = GenerationResponse.from_dict({
          "candidates": [
              {
                  "finish_reason": generative_models.FinishReason.STOP,
                  "content": {
                      "role": "model",
                      "parts": [{"text": response}],
                  }
              }
          ]
      })

    self.mock_generative_model.generate_content.return_value = response
    self.mock_generative_model.generate_content_async = mock.AsyncMock(
        return_value=response
    )

    self._model_init_patcher = mock.patch(
        "vertexai.generative_models.GenerativeModel",
        return_value=self.mock_generative_model,
    )

  def start(self):
    self.mock_init = self._model_init_patcher.start()

  def stop(self):
    self._model_init_patcher.stop()

  def __call__(
      self, test_function: Callable[[Any], Any]
  ) -> Callable[[Any], Any]:
    def wrapped_test_function(*args, **kwargs):
      self.start()
      kwargs["generative_model_patcher"] = self
      test_function(*args, **kwargs)
      self.stop()

    return wrapped_test_function

  def __enter__(self) -> "PatchGenerativeModel":
    self.start()
    return self

  def __exit__(self, *args, **kwargs):
    self.stop()


def values_are_equal(x: Any, y: Any) -> bool:
  """Recursively checks if the values of two iterables are equal."""
  if isinstance(x, str):
    # If the objects are strings, compare them directly
    return x == y

  if not hasattr(x, "__iter__") and not hasattr(y, "__iter__"):
    # If they are not iterables, compare them directly
    return x == y
  elif not hasattr(x, "__iter__") or not hasattr(y, "__iter__"):
    # Only one of them is an iterable, so they can't be equal
    return False

  # Otherwise, check they have the same length and compare them element-wise
  if len(x) != len(y):
    return False

  # If they are dicts, check they have the same keys and that the values are
  # equal.
  if isinstance(x, dict):
    for key in x.keys():
      if key not in y:
        return False
      if not values_are_equal(x[key], y[key]):
        return False
    return True

  # Finally, assume they are iterables and check they have the same elements.
  for x_i, y_i in zip(x, y):
    if not values_are_equal(x_i, y_i):
      return False

  return True


def vectorstore_instances_are_equal(
    ad_copy_vectorstore_1: ad_copy_generator.AdCopyVectorstore,
    ad_copy_vectorstore_2: ad_copy_generator.AdCopyVectorstore,
) -> bool:
  """Checks if two AdCopyVectorstores are equal.

  Args:
    ad_copy_vectorstore_1: The first AdCopyVectorstore to compare.
    ad_copy_vectorstore_2: The second AdCopyVectorstore to compare.

  Returns:
    True if the two AdCopyVectorstores are equal, False otherwise.
  """
  if not isinstance(ad_copy_vectorstore_1, ad_copy_generator.AdCopyVectorstore):
    return False

  if not isinstance(ad_copy_vectorstore_2, ad_copy_generator.AdCopyVectorstore):
    return False

  params_1 = {
      "embedding_model_name": ad_copy_vectorstore_1.embedding_model_name.value,
      "dimensionality": ad_copy_vectorstore_1.dimensionality,
      "embeddings_batch_size": ad_copy_vectorstore_1.embeddings_batch_size,
  }
  params_2 = {
      "embedding_model_name": ad_copy_vectorstore_2.embedding_model_name.value,
      "dimensionality": ad_copy_vectorstore_2.dimensionality,
      "embeddings_batch_size": ad_copy_vectorstore_2.embeddings_batch_size,
  }

  if not values_are_equal(params_1, params_2):
    return False

  try:
    pd.testing.assert_frame_equal(
        ad_copy_vectorstore_1.ad_exemplars,
        ad_copy_vectorstore_2.ad_exemplars,
        check_like=True,
    )
  except AssertionError:
    return False

  return True


def copycat_instances_are_equal(
    copycat_1: copycat.Copycat, copycat_2: copycat.Copycat
) -> bool:
  """Checks if two Copycat models are equal.

  Args:
    copycat_1: The first Copycat model to compare.
    copycat_2: The second Copycat model to compare.

  Returns:
    True if the two Copycat models are equal, False otherwise.
  """
  if not isinstance(copycat_1, copycat.Copycat):
    return False

  if not isinstance(copycat_2, copycat.Copycat):
    return False

  if not vectorstore_instances_are_equal(
      copycat_1.ad_copy_vectorstore, copycat_2.ad_copy_vectorstore
  ):
    return False

  if copycat_1.ad_format != copycat_2.ad_format:
    return False

  if copycat_1.style_guide != copycat_2.style_guide:
    return False

  return True
