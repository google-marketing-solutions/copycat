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

import asyncio
from collections.abc import Sequence
import dataclasses
import enum
import functools
import json
import logging
import re
from typing import Any, AsyncIterable, Coroutine, Hashable, TypeVar

import bs4
from vertexai import generative_models
from vertexai import language_models
import numpy as np
import pandas as pd
import pydantic
import requests
from sklearn import cluster
from sklearn import neighbors
import tqdm

from copycat import google_ads


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class TqdmLogger:
  """File-like class redirecting tqdm progress bar to LOGGER."""

  def write(self, msg: str) -> None:
    LOGGER.info(msg.lstrip("\r"))

  def flush(self) -> None:
    pass


AsyncGenerationResponse = Coroutine[
    Any,
    Any,
    generative_models.GenerationResponse
    | AsyncIterable[generative_models.GenerationResponse],
]

GoogleAd = google_ads.GoogleAd
GoogleAdFormat = google_ads.GoogleAdFormat

ValidationError = pydantic.ValidationError
FinishReason = generative_models.FinishReason

SafetySettingsType = (
    dict[generative_models.HarmCategory, generative_models.HarmBlockThreshold]
    | list[generative_models.SafetySetting]
)

VECTORSTORE_PARAMS_FILE_NAME = "vectorstore_params.json"
VECTORSTORE_AD_EXEMPLARS_FILE_NAME = "vectorstore_ad_exemplars.csv"


class ModelName(enum.Enum):
  GEMINI_1_0_PRO = "gemini-pro"
  GEMINI_1_5_PRO_PREVIEW = "gemini-1.5-pro-preview-0514"
  GEMINI_1_5_PRO_001 = "gemini-1.5-pro-001"
  GEMINI_1_5_PRO_002 = "gemini-1.5-pro-002"
  GEMINI_1_5_PRO = "gemini-1.5-pro-002"
  GEMINI_1_5_FLASH_PREVIEW = "gemini-1.5-flash-preview-0514"
  GEMINI_1_5_FLASH_001 = "gemini-1.5-flash-001"
  GEMINI_1_5_FLASH_002 = "gemini-1.5-flash-002"
  GEMINI_1_5_FLASH = "gemini-1.5-flash-002"


class EmbeddingModelName(enum.Enum):
  TEXT_EMBEDDING = "text-embedding-004"
  TEXT_MULTILINGUAL_EMBEDDING = "text-multilingual-embedding-002"


class ExemplarSelectionMethod(enum.Enum):
  AFFINITY_PROPAGATION = "affinity_propagation"
  RANDOM = "random"


class TextGenerationRequest(pydantic.BaseModel):
  """The request to generate text."""

  keywords: str
  existing_ad_copy: GoogleAd
  system_instruction: str
  prompt: list[generative_models.Content]
  chat_model_name: ModelName
  temperature: float
  top_k: int
  top_p: float
  safety_settings: SafetySettingsType | None

  class Config:
    arbitrary_types_allowed = True

  def to_markdown(self):
    lines = [
        "**Keywords:**",
        self.keywords,
    ]

    if self.existing_ad_copy.headlines:
      lines.extend(
          ["**Existing headlines:**", f"{self.existing_ad_copy.headlines}"]
      )
    if self.existing_ad_copy.descriptions:
      lines.extend([
          "**Existing descriptions:**",
          f"{self.existing_ad_copy.descriptions}",
      ])

    lines.extend([
        "**Model Parameters:**",
        f"Model name: {self.chat_model_name.value}",
        f"Temperature: {self.temperature}",
        f"Top K: {self.top_k}",
        f"Top P: {self.top_p}",
        f"Safety settings: {self.safety_settings}",
        "**System instruction:**",
        self.system_instruction,
    ])

    for content in self.prompt:
      lines.append(f"**{content.role.title()}:**")
      lines.append(content.parts[0].text)

    return "\n\n".join(lines)


class ExampleAd(pydantic.BaseModel):
  """An example ad.

  Attributes:
    google_ad: The google ad containing the headlines and descriptions.
    keywords: The keywords this ad was used for.
  """

  google_ad: GoogleAd
  keywords: str

  @classmethod
  def from_flat_values(
      cls, keywords: str, headlines: list[str], descriptions: list[str]
  ) -> "ExampleAd":
    """Creates an ExampleAd from keywords, headlines and descriptions."""
    return cls(
        google_ad=GoogleAd(headlines=headlines, descriptions=descriptions),
        keywords=keywords,
    )


@dataclasses.dataclass
class AdCopyVectorstore:
  """The vector store containing the ad copies.

  Each record contains both a text that will be matched to queries and some
  metadata. The text is either a headline or a description that exists in the
  ad, and the metadata contains the full list of headlines, descriptions and
  keywords for that ad. Each ad will appear in the vectorstore multiple times,
  once for each headline and description it uses. This allows the ads to be
  matched to the query based on the most relavent individual headline or
  description, rather than an average over all of them.

  Attributes:
    embedding_model_name: The name of the embedding model to use.
    ad_exemplars: The example ads available to be used as in context examples.
    dimensionality: The dimensionality of the embedding model.
    embeddings_batch_size: The batch size to use when generating embeddings.
    unique_headlines: The unique headlines in the vectorstore.
    unique_descriptions: The unique descriptions in the vectorstore.
    n_exemplars: The total number of exemplars in the vectorstore.
  """

  embedding_model_name: EmbeddingModelName
  ad_exemplars: pd.DataFrame
  dimensionality: int
  embeddings_batch_size: int

  @classmethod
  def _generate_embeddings(
      cls,
      texts: list[str],
      *,
      embedding_model_name: EmbeddingModelName,
      dimensionality: int,
      batch_size: int,
      task_type: str,
      progress_bar: bool = False,
  ) -> list[list[float]]:
    """Generates embeddings for the provided texts.

    Args:
      texts: The texts to generate embeddings for.
      embedding_model_name: The name of the embedding model to use.
      dimensionality: The dimensionality of the embedding model.
      batch_size: The batch size to use when generating embeddings.
      task_type: The task type to use when generating embeddings.
      progress_bar: Whether to show a progress bar.

    Returns:
      The generated embeddings.
    """
    embedding_model = language_models.TextEmbeddingModel.from_pretrained(
        embedding_model_name.value
    )
    n_batches = np.ceil(len(texts) / batch_size)
    LOGGER.debug(
        "Using embedding model: %s, dimensionality: %d, task type: %s",
        embedding_model_name.value,
        dimensionality,
        task_type,
    )
    LOGGER.debug(
        "Generating %d embeddings in %d batches.", len(texts), n_batches
    )

    embeddings = []

    texts_batch_iterator = np.array_split(texts, n_batches)
    if progress_bar:
      texts_batch_iterator = tqdm.tqdm(
          texts_batch_iterator,
          desc="Generating embeddings",
          file=TqdmLogger(),
          mininterval=5,
      )

    for texts_batch in texts_batch_iterator:
      embedding_inputs = [
          language_models.TextEmbeddingInput(ad_markdown, task_type)
          for ad_markdown in texts_batch
      ]
      embedding_outputs = embedding_model.get_embeddings(
          embedding_inputs, output_dimensionality=dimensionality
      )
      embeddings.extend([emb.values for emb in embedding_outputs])

    LOGGER.debug("Embeddings generated.")
    return embeddings

  def embed_documents(self, texts: list[str]) -> list[list[float]]:
    """Generates embeddings for the provided texts."""
    return self._generate_embeddings(
        texts,
        embedding_model_name=self.embedding_model_name,
        dimensionality=self.dimensionality,
        batch_size=self.embeddings_batch_size,
        task_type="RETRIEVAL_DOCUMENT",
        progress_bar=False,
    )

  def embed_queries(self, texts: list[str]) -> list[list[float]]:
    """Generates embeddings for the provided texts."""
    return self._generate_embeddings(
        texts,
        embedding_model_name=self.embedding_model_name,
        dimensionality=self.dimensionality,
        batch_size=self.embeddings_batch_size,
        task_type="RETRIEVAL_QUERY",
        progress_bar=False,
    )

  @classmethod
  def _get_exemplars(
      cls,
      data: pd.DataFrame,
      *,
      embeddings_column: str,
      affinity_preference: float | None,
      max_exemplars: int,
  ) -> pd.DataFrame:
    """Uses Affinity Propagation to find exemplar ads."""
    LOGGER.info("Getting exemplars with Affinity Propagation.")
    embeddings = np.asarray(data[embeddings_column].values.tolist())

    clusterer = cluster.AffinityPropagation(preference=affinity_preference)
    clusterer.fit(embeddings)
    exemplars = (
        data.iloc[clusterer.cluster_centers_indices_]
        .copy()
        .reset_index(drop=True)
    )

    if len(exemplars) > max_exemplars:
      LOGGER.info(
          "Affinity Propagation returned too many exemplars (%d). Sampling to"
          " get %d.",
          len(exemplars),
          max_exemplars,
      )
      exemplars = exemplars.sample(max_exemplars)

    LOGGER.info("Got %d exemplars with Affinity Propagation.", len(exemplars))
    return exemplars

  @classmethod
  def _deduplicate_ads(cls, data: pd.DataFrame) -> pd.DataFrame:
    """Deduplicates the ads in the training data.

    If the same ads are used for multiple sets of keywords, select just one
    random keywords set for each ad. We don't need to have identical ads in
    the vectorstore.

    Args:
      data: The training data containing the headlines, descriptions and
        keywords.

    Returns:
      The deduplicated training data.
    """
    n_starting_rows = len(data)
    LOGGER.info("Deduplicating ads (starting with %d rows).", n_starting_rows)

    data = data.copy()
    data["headlines"] = data["headlines"].apply(tuple)
    data["descriptions"] = data["descriptions"].apply(tuple)
    data = (
        data.groupby(["headlines", "descriptions"], group_keys=False)
        .sample(1)
        .reset_index(drop=True)
    )
    data["headlines"] = data["headlines"].apply(list)
    data["descriptions"] = data["descriptions"].apply(list)

    n_deduped_rows = len(data)
    LOGGER.info(
        "Deduplication removed %d rows.", n_starting_rows - n_deduped_rows
    )

    return data

  @classmethod
  def create_from_pandas(
      cls,
      training_data: pd.DataFrame,
      *,
      embedding_model_name: str | EmbeddingModelName,
      dimensionality: int,
      max_initial_ads: int,
      max_exemplar_ads: int,
      affinity_preference: float | None,
      embeddings_batch_size: int,
      exemplar_selection_method: (
          str | ExemplarSelectionMethod
      ) = "affinity_propagation",
  ) -> "AdCopyVectorstore":
    """Creates a vector store containing the ad copies from pandas.

    The vectorstore is created from the provided training data. The training
    data contains the real ad copies and keywords they were used for. Make sure
    the ad copy is high quality as this is what the model will learn from.

    The training_data must contain the following columns:
      - headlines: The headlines of the ad copy. This should be a list of
        strings.
      - descriptions: The descriptions of the ad copy. This should be a list of
        strings.
      - keywords: The keywords the ad copy was used for. This should be a
        string of comma separated keywords.

    The vectorstore is created by:
      1.  Deduplicating the ads in the training data. This ensures that each ad
          is only used once in the vectorstore.
      2.  Sampling the training data to a maximum of max_initial_ads. This
          ensures that the next steps are not too slow.
      3.  Generating embeddings for the ads. This is done using the provided
          embedding model name.
      4.  Applying affinity propogation to find "exemplar ads", which are
          ads that are representative of the training data, but are not too
          similar to each other.
      5.  Sampling the exemplar ads to a maximum of max_exemplar_ads. This
          ensures that the vectorstore does not become too large.

    The affinity propogation algorithm depends on the affinity_preference
    parameter. A higher affinity_preference will result in more exemplar ads
    being selected, while a lower affinity_preference will result in fewer
    exemplar ads being selected. The affinity preference should be a negative
    number. If set to None it automatically selects the number of
    exemplar ads based on the data.

    Args:
      training_data: The training data containing the real ad copies and
        keywords.
      embedding_model_name: The name of the embedding model to use.
      dimensionality: The dimensionality of the embedding model.
      max_initial_ads: The maximum number of ads to use from the training data.
        This is used to speed up the process of creating the vectorstore.
      max_exemplar_ads: The maximum number of exemplar ads to use in the
        vectorstore.
      affinity_preference: The affinity preference to use when finding exemplar
        ads.
      embeddings_batch_size: The batch size to use when generating embeddings.
      exemplar_selection_method: The method to use to select the exemplar ads.
        Either "affinity_propagation" or "random". Defaults to
        "affinity_propagation".

    Returns:
      An instance of the AdCopyVectorstore containing the exemplar ads.

    Raises:
      ValueError: If the exemplar selection method is not supported.
    """
    embedding_model_name = EmbeddingModelName(embedding_model_name)
    exemplar_selection_method = ExemplarSelectionMethod(
        exemplar_selection_method
    )
    LOGGER.info(
        "Creating AdCopyVectorstore from %d rows of training data.",
        len(training_data),
    )

    data = (
        training_data[["headlines", "descriptions", "keywords"]]
        .copy()
        .pipe(cls._deduplicate_ads)
    )

    if len(data) > max_initial_ads:
      LOGGER.info("Sampling %d ads from %d ads.", max_initial_ads, len(data))
      data = data.sample(max_initial_ads)

    data["ad_markdown"] = data.apply(lambda x: str(GoogleAd(**x)), axis=1)
    LOGGER.info(
        "Finding exemplar ads with method = %s.",
        exemplar_selection_method.value,
    )
    if (
        exemplar_selection_method
        is ExemplarSelectionMethod.AFFINITY_PROPAGATION
    ):
      data["embeddings"] = cls._generate_embeddings(
          data["ad_markdown"].values.tolist(),
          embedding_model_name=embedding_model_name,
          dimensionality=dimensionality,
          batch_size=embeddings_batch_size,
          task_type="RETRIEVAL_DOCUMENT",
          progress_bar=True,
      )

      ad_exemplars = cls._get_exemplars(
          data,
          embeddings_column="embeddings",
          affinity_preference=affinity_preference,
          max_exemplars=max_exemplar_ads,
      )
    elif exemplar_selection_method is ExemplarSelectionMethod.RANDOM:
      if len(data) > max_exemplar_ads:
        ad_exemplars = data.sample(max_exemplar_ads)
      else:
        ad_exemplars = data

      ad_exemplars["embeddings"] = cls._generate_embeddings(
          ad_exemplars["ad_markdown"].values.tolist(),
          embedding_model_name=embedding_model_name,
          dimensionality=dimensionality,
          batch_size=embeddings_batch_size,
          task_type="RETRIEVAL_DOCUMENT",
          progress_bar=True,
      )

    else:
      LOGGER.error(
          "Unsupported exemplar selection method: %s",
          exemplar_selection_method.value,
      )
      raise ValueError(
          f"Unsupported exemplar selection method: {exemplar_selection_method}"
      )

    LOGGER.info(
        "Reduced %d total ads to %d exemplar ads.",
        len(training_data),
        len(ad_exemplars),
    )

    return cls(
        embedding_model_name=embedding_model_name,
        ad_exemplars=ad_exemplars,
        dimensionality=dimensionality,
        embeddings_batch_size=embeddings_batch_size,
    )

  @classmethod
  def from_dict(cls, params: dict[str, Any]) -> "AdCopyVectorstore":
    """Loads the vectorstore from the provided dict.

    Schema of params:
      embedding_model_name: The name of the embedding model to use.
      ad_exemplars: The ad exemplars to use in the vectorstore, as a pandas
        dataframe that has been converted to a dict with to_dict("tight").
      dimensionality: The dimensionality of the embedding model.
      embeddings_batch_size: The batch size to use when generating embeddings.

    Args:
      params: The dict containing the parameters to use to create the
        AdCopyVectorstore. See above for the schema.

    Returns:
      An instance of the AdCopyVectorstore.

    Raises:
      KeyError: If any of the required keys are missing from the dict.
    """
    required_keys = {
        "embedding_model_name",
        "ad_exemplars",
        "dimensionality",
        "embeddings_batch_size",
    }
    missing_keys = required_keys - set(params.keys())
    if missing_keys:
      LOGGER.error("Missing required keys: %s", missing_keys)
      raise KeyError(f"Missing required keys: {missing_keys}")

    params = params.copy()
    params["embedding_model_name"] = EmbeddingModelName(
        params["embedding_model_name"]
    )
    params["ad_exemplars"] = pd.DataFrame.from_dict(
        params["ad_exemplars"], orient="tight"
    )
    return cls(**params)

  @classmethod
  def from_json(cls, json_string: str) -> "AdCopyVectorstore":
    """Loads the vectorstore from the provided json string.

    Schema of params:
      embedding_model_name: The name of the embedding model to use.
      ad_exemplars: The ad exemplars to use in the vectorstore, as a pandas
        dataframe that has been converted to a dict with to_dict("tight").
      dimensionality: The dimensionality of the embedding model.
      embeddings_batch_size: The batch size to use when generating embeddings.

    Args:
      json_string: The json string containing the parameters to use to create
        the AdCopyVectorstore. See above for the schema.

    Returns:
      An instance of the AdCopyVectorstore.

    Raises:
      KeyError: If any of the required keys are missing from the dict.
    """
    return cls.from_dict(json.loads(json_string))

  def to_dict(self) -> dict[str, Any]:
    """Serializes the vectorstore to a dict."""
    return {
        "embedding_model_name": self.embedding_model_name.value,
        "dimensionality": self.dimensionality,
        "embeddings_batch_size": self.embeddings_batch_size,
        "ad_exemplars": self.ad_exemplars.to_dict(orient="tight"),
    }

  def to_json(self) -> str:
    """Serializes the vectorstore to a json string."""
    return json.dumps(self.to_dict())

  @functools.cached_property
  def nearest_neighbors(self) -> neighbors.NearestNeighbors:
    """The nearest neighbors model used to find similar ads."""
    embeddings = np.asarray(self.ad_exemplars["embeddings"].values.tolist())
    model = neighbors.NearestNeighbors()
    model.fit(embeddings)
    return model

  @functools.cached_property
  def unique_headlines(self) -> set[str]:
    return set(self.ad_exemplars["headlines"].explode().unique().tolist())

  @functools.cached_property
  def unique_descriptions(self) -> set[str]:
    return set(self.ad_exemplars["descriptions"].explode().unique().tolist())

  @property
  def n_exemplars(self) -> int:
    """The total number of exemplars in the vectorstore."""
    return len(self.ad_exemplars)

  def get_relevant_ads_and_embeddings_from_embeddings(
      self,
      query_embeddings: list[list[float]],
      k: int,
  ) -> tuple[list[list[ExampleAd]], list[list[float]]]:
    """Gets the most relevant ads and their embeddings for the query embeddings.

    Args:
      query_embeddings: The list of query embeddings to use to retrieve the ads.
        These are typically the embeddings of the keywords used to generate the
        ad copy.
      k: The number of ads to return for each query.

    Returns:
      The k most relevant ads and their embeddings for each query as two lists.
    """
    k = min(self.n_exemplars, k)

    similar_ad_ids = self.nearest_neighbors.kneighbors(
        query_embeddings, n_neighbors=k, return_distance=False
    )
    similar_ads = [
        list(
            map(
                lambda x: ExampleAd.from_flat_values(**x),
                self.ad_exemplars.iloc[ids][
                    ["headlines", "descriptions", "keywords"]
                ].to_dict("records"),
            )
        )
        for ids in similar_ad_ids
    ]
    similar_ad_embeddings = [
        self.ad_exemplars.iloc[ids]["embeddings"].values.tolist()
        for ids in similar_ad_ids
    ]
    return similar_ads, similar_ad_embeddings

  def get_relevant_ads(
      self, queries: list[str], k: int
  ) -> list[list[ExampleAd]]:
    """Returns the k most relevant ads for the provided query.

    Args:
      queries: The list of queries to use to retrieve the ads. These are
        typically the keywords used to generate the ad copy.
      k: The number of ads to return for each query.

    Returns:
      The k most relavent ads for each query
    """
    query_embeddings = self.embed_queries(queries)
    relevant_ads, _ = self.get_relevant_ads_and_embeddings_from_embeddings(
        query_embeddings, k
    )
    return relevant_ads


def _construct_instruction_for_number_of_headlines_and_descriptions(
    existing_ad_copy: GoogleAd,
    ad_format: GoogleAdFormat,
) -> str:
  """Returns the instruction with how many headlines / descriptions to generate.

  If the ad already has some headlines and descriptions, then the prompt needs
  to inclide them and explain to Copycat that it should just generate the
  missing headlines and descriptions.

  If the existing headlines and descriptions are empty then it just needs to
  explain the number of headlines and descriptions required for the format.

  If the ad is already complete, then it should raise an error.

  Args:
    existing_ad_copy: The existing headlines and descriptions.
    ad_format: The ad format to generate.

  Returns:
    The instruction for extending the ad copy.

  Raises:
    ValueError: If the ad is already complete, meaning there is nothing to
      generate.
  """
  n_existing_headlines = len(existing_ad_copy.headlines)
  n_existing_descriptions = len(existing_ad_copy.descriptions)
  n_required_headlines = ad_format.max_headlines - n_existing_headlines
  n_required_descriptions = ad_format.max_descriptions - n_existing_descriptions

  no_headlines = n_existing_headlines == 0
  no_descriptions = n_existing_descriptions == 0
  complete_headlines = n_existing_headlines >= ad_format.max_headlines
  complete_descriptions = n_existing_descriptions >= ad_format.max_descriptions

  # If the ad is already complete, then there is nothing to generate.
  if complete_headlines and complete_descriptions:
    LOGGER.error("Trying to generate an ad that is already complete.")
    raise ValueError("Trying to generate an ad that is already complete.")

  # If the ad is empty, then we need to generate the required headlines and
  # descriptions.
  if no_headlines and no_descriptions:
    return (
        f"Please write {n_required_headlines} headlines and"
        f" {n_required_descriptions} descriptions for this ad."
    )

  instructions = []
  # First, if there are already some headlines and descriptions, explain this
  # to Copycat.
  if not no_headlines and not no_descriptions:
    instructions.extend([
        (
            f"This ad already has {n_existing_headlines} headlines and"
            f" {n_existing_descriptions} descriptions:\n"
        ),
        f"- headlines: {existing_ad_copy.headlines}",
        f"- descriptions: {existing_ad_copy.descriptions}\n",
    ])
  elif not no_headlines:
    instructions.extend([
        f"This ad already has {n_existing_headlines} headlines.\n",
        f"- headlines: {existing_ad_copy.headlines}\n",
    ])
  elif not no_descriptions:
    instructions.extend([
        f"This ad already has {n_existing_descriptions} descriptions.\n",
        f"- descriptions: {existing_ad_copy.descriptions}\n",
    ])

  # If the ad still needs to generate more headlines and descriptions, make it
  # clear how many are required.
  if not complete_headlines and not complete_descriptions:
    instructions.append(
        f"Please write {n_required_headlines} more headlines and"
        f" {n_required_descriptions} more descriptions to complete this ad."
    )
  elif not complete_headlines and complete_descriptions:
    instructions.append(
        f"Please write {n_required_headlines} more headlines to complete this"
        " ad. You do not need to write any descriptions, as there are enough"
        " already."
    )
  elif not complete_descriptions and complete_headlines:
    instructions.append(
        f"Please write {n_required_descriptions} more descriptions to complete"
        " this ad. You do not need to write any headlines, as there are enough"
        " already."
    )

  return "\n".join(instructions)


def _construct_new_ad_copy_user_message(
    keywords: str,
    ad_format: GoogleAdFormat,
    existing_ad_copy: GoogleAd | None = None,
    keywords_specific_instructions: str = "",
) -> generative_models.Content:
  """Returns the user message for generating new ad copy.

  Args:
    keywords: The keywords to generate the ad copy for.
    ad_format: The ad format to generate.
    existing_ad_copy: The existing headlines and descriptions for this ad. The
      prompt will ask Copycat to extend this ad copy to the required number of
      headlines and descriptions for the ad format. If None, then the ad copy is
      empty.
    keywords_specific_instructions: Any additional context to use for the new
      keywords. This could include things like information from the landing
      page, information about specific discounts or promotions, or any other
      relevant information.
  """
  if existing_ad_copy is None:
    existing_ad_copy = GoogleAd(headlines=[], descriptions=[])

  content = ""
  if keywords_specific_instructions:
    content += (
        "For the next set of keywords, please consider the following additional"
        f" instructions:\n\n{keywords_specific_instructions}\n\n"
    )
  content += _construct_instruction_for_number_of_headlines_and_descriptions(
      existing_ad_copy=existing_ad_copy,
      ad_format=ad_format,
  )
  content += f"\n\nKeywords: {keywords}"

  return generative_models.Content(
      role="user",
      parts=[generative_models.Part.from_text(content)],
  )


def construct_system_instruction(
    system_instruction: str,
    style_guide: str,
    system_instruction_kwargs: dict[str, Any],
) -> str:
  """Constructs the system instruction by adding the style guide and kwargs.

  Args:
    system_instruction: The system instruction to use. This should explain the
      task to the model.
    style_guide: The style guide to use.
    system_instruction_kwargs: The keyword arguments are used to replace any
      placeholders in the system prompt.

  Returns:
  The formatted system prompt.
  """
  if system_instruction_kwargs:
    system_instruction = system_instruction.format(**system_instruction_kwargs)
  if style_guide:
    system_instruction += "\n\n" + style_guide
  return system_instruction


def construct_new_ad_copy_prompt(
    example_ads: list[ExampleAd],
    keywords: str,
    ad_format: GoogleAdFormat,
    existing_ad_copy: GoogleAd | None = None,
    keywords_specific_instructions: str = "",
) -> list[generative_models.Content]:
  """Constructs the full copycat prompt for generating new ad copy.

  The prompt consists of a list of in-context examples for new ad copy
  generation. This is a list of messages, alternating between the keywords and
  expected response from each example ad. The expected response is a json string
  containing the headlines and descriptions of the ad copy. The messages are
  sorted so that the most relevant examples are last. This ensures the model
  see's the most relevant examples last, making them more likely to influence
  the model's output. The final message contains the keywords to generate the ad
  copy for, and the additional context for the new keywords from the
  keywords_specific_instructions if it exists.

  Args:
    example_ads: The list of example ads to use as in-context examples.
    keywords: The keywords to generate the ad copy for.
    ad_format: The ad format to generate.
    existing_ad_copy: The existing headlines and descriptions for this ad. The
      prompt will ask Copycat to extend this ad copy to the required number of
      headlines and descriptions for the ad format. If None, then the ad copy is
      empty.
    keywords_specific_instructions: Any additional context to use for the new
      keywords. This could include things like information from the landing
      page, information about specific discounts or promotions, or any other
      relevant information.

  Returns:
    A list of Content representing the prompt.
  """
  prompt = []
  for example in reversed(example_ads):
    example_ad_format = ad_format.model_copy(
        update={
            "max_headlines": example.google_ad.headline_count,
            "max_descriptions": example.google_ad.description_count,
        }
    )
    prompt.append(
        _construct_new_ad_copy_user_message(
            example.keywords, ad_format=example_ad_format
        )
    )
    prompt.append(
        generative_models.Content(
            role="model",
            parts=[
                generative_models.Part.from_text(
                    example.google_ad.model_dump_json()
                )
            ],
        )
    )

  prompt.append(
      _construct_new_ad_copy_user_message(
          keywords,
          ad_format=ad_format,
          existing_ad_copy=existing_ad_copy,
          keywords_specific_instructions=keywords_specific_instructions,
      )
  )

  return prompt


HashableTypeVar = TypeVar("HashableTypeVar", bound=Hashable)


def _deduplicate_list_keep_order(
    seq: Sequence[HashableTypeVar],
) -> list[HashableTypeVar]:
  seen = set()
  seen_add = seen.add
  return [x for x in seq if not (x in seen or seen_add(x))]


def remove_invalid_headlines_and_descriptions(
    google_ad: GoogleAd, google_ad_format: GoogleAdFormat
) -> None:
  """Removes invalid headlines and descriptions from the ad.

  First it removes any duplicate headlines or descriptions, then removes any
  headlines or descriptions that are too long. Then it removes any headlines or
  descriptions that are not in the first k headlines or descriptions.

  Args:
    google_ad: The ad to remove the invalid headlines and descriptions from.
    google_ad_format: The format of the ad.
  """
  google_ad.headlines = _deduplicate_list_keep_order(google_ad.headlines)
  google_ad.descriptions = _deduplicate_list_keep_order(google_ad.descriptions)

  google_ad.headlines = [
      headline
      for headline in google_ad.headlines
      if len(google_ads.parse_google_ads_special_variables(headline))
      <= google_ad_format.max_headline_length
  ]
  google_ad.descriptions = [
      description
      for description in google_ad.descriptions
      if len(google_ads.parse_google_ads_special_variables(description))
      <= google_ad_format.max_description_length
  ]

  if len(google_ad.headlines) > google_ad_format.max_headlines:
    google_ad.headlines = google_ad.headlines[: google_ad_format.max_headlines]
  if len(google_ad.descriptions) > google_ad_format.max_descriptions:
    google_ad.descriptions = google_ad.descriptions[
        : google_ad_format.max_descriptions
    ]


def async_generate_google_ad_json(
    request: TextGenerationRequest,
) -> AsyncGenerationResponse:
  """Generates a GoogleAd from the text generation request asynchronously.

  This function ensures that the generated response is a valid json
  representation of a GoogleAd, by appending formatting instructions to the
  system instruction and including a response schema in the generation config
  for models that accept it.

  Args:
    request: The text generation request, containing the prompt, system
      instruction, style guide, and other parameters.

  Returns:
    The generated response, which is a valid json representation of a GoogleAd.
  """
  generation_config_params = dict(
      temperature=request.temperature,
      top_k=request.top_k,
      top_p=request.top_p,
      response_mime_type="application/json",
  )

  generation_config_params["response_schema"] = {
      "type": "OBJECT",
      "properties": {
          "headlines": {
              "type": "ARRAY",
              "items": {
                  "type": "string",
                  "description": (
                      "The headlines for the ad. Must be fewer than 30"
                      " characters."
                  ),
              },
          },
          "descriptions": {
              "type": "ARRAY",
              "items": {
                  "type": "string",
                  "description": (
                      "The descriptions for the ad. Must be fewer than 90"
                      " characters."
                  ),
              },
          },
      },
      "required": ["headlines", "descriptions"],
  }

  generation_config = generative_models.GenerationConfig(
      **generation_config_params
  )

  LOGGER.debug("System instruction: %s", request.system_instruction)
  LOGGER.debug("Prompt: %s", request.prompt)

  model = generative_models.GenerativeModel(
      model_name=request.chat_model_name.value,
      generation_config=generation_config,
      system_instruction=request.system_instruction,
      safety_settings=request.safety_settings,
  )

  response = model.generate_content_async(request.prompt)

  return response


def generate_google_ad_json_batch(
    requests: list[TextGenerationRequest],
) -> list[generative_models.GenerationResponse]:
  """Generates a GoogleAd from the provided text generation request.

  This function ensures that the generated response is a valid json
  representation of a GoogleAd, by appending formatting instructions to the
  system instruction and including a response schema in the generation config
  for models that accept it.

  Args:
    requests: A list of text generation requests, containing the prompts, system
      instructions, style guides, and other parameters.

  Returns:
    The generated responses, which are valid json representations of GoogleAds.

  Raises:
    RuntimeError: If one of the responses is not a valid json representation of
    a GoogleAd. This shouldn't happen unless the gemini api changes.
  """
  try:
    loop = asyncio.get_running_loop()
  except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

  outputs = loop.run_until_complete(
      asyncio.gather(*list(map(async_generate_google_ad_json, requests)))
  )
  for output in outputs:
    if not isinstance(output, generative_models.GenerationResponse):
      LOGGER.error(
          "One of the responses is not a GenerationResponse. Instead got: %s",
          output,
      )
      raise RuntimeError(
          "One of the responses is not a GenerationResponse. Instead got:"
          f" {output}"
      )

  return outputs


def extract_urls_for_keyword_instructions(
    keyword_instructions: list[str],
) -> list[str]:
  """Extracts pages from keyword instructions.

  Args:
      keyword_instructions: keyword instructions or a string that may contain a
        URL.

  Returns:
      list of keyword instructions with retrieved web page content if a URL is
      found and successfully fetched.
  """
  pages = []
  for instruction in keyword_instructions:
    url = extract_url_from_string(instruction)
    if url and is_valid_url(url):
      try:
        response = requests.get(url)
        response.raise_for_status()
        soup = bs4.BeautifulSoup(response.content, "html.parser")
        if len(instruction) == len(url):  # if the instruction is only the url
          pages.append(f"Web page content of {url}: {soup.get_text()}")
        else:
          pages.append(f"{instruction} ## Content of {url}: {soup.get_text()}")
      except requests.exceptions.RequestException as e:
        pages.append(
            instruction
        )  # Keep the original instruction if there's an error
    else:
      pages.append(instruction)
  return pages


def extract_url_from_string(text: str) -> str | None:
  """Extracts a URL from a string.

  Args:
      text: The string that may contain a URL.

  Returns:
      The extracted URL if found, otherwise None.
  """
  url_pattern = re.compile(
      r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
  )
  match = url_pattern.search(text)
  return match.group() if match else None


def is_valid_url(url: str) -> bool:
  """Checks if a url is valid.

  Args:
      url: to check if valid url.

  Returns:
      Boolean dependent on if it is a valid url
  """
  regex = re.compile(
      r"^(https?):\/\/" r"([a-zA-Z0-9.-]+)\." r"([a-zA-Z]{2,})" r"(\/[^\s]*)?$",
      re.IGNORECASE,
  )

  return re.fullmatch(regex, url) is not None
