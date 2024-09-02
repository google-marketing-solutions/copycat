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

"""The main module for Copycat.

Contains the code to generate copycat ad copies.
"""

import dataclasses
import json
from typing import Any
import warnings

from vertexai import generative_models
import pandas as pd
import pydantic

from copycat import ad_copy_evaluator
from copycat import ad_copy_generator
from copycat import google_ads

GoogleAd = google_ads.GoogleAd
GoogleAdFormat = google_ads.GoogleAdFormat
ValidationError = pydantic.ValidationError
ModelName = ad_copy_generator.ModelName
EmbeddingModelName = ad_copy_generator.EmbeddingModelName
TextGenerationRequest = ad_copy_generator.TextGenerationRequest
ExemplarSelectionMethod = ad_copy_generator.ExemplarSelectionMethod
EvaluationResults = ad_copy_evaluator.EvaluationResults

# Below are not used in this file, they are included for the user to easily
# adjust the safety settings in copycat without having to import
# generative_models from vertex ai.
HarmCategory = ad_copy_generator.generative_models.HarmCategory
HarmBlockThreshold = ad_copy_generator.generative_models.HarmBlockThreshold
ALL_SAFETY_SETTINGS_OFF = {
    harm_category: HarmBlockThreshold.BLOCK_NONE
    for harm_category in HarmCategory
}


DEFAULT_SYSTEM_INSTRUCTION = """\
You are an expert marketing professional, working for {company_name}. You are
tasked with writing new headlines and descriptions for Google Ads in {language},
given a new set of keywords, that will maximize engagement and clicks.
Keywords are words or phrases that are used to match ads with the terms that
people are searching for, so the copy should be engaging for someone searching
for those keywords. Each ad must have a list of {max_headlines} headlines 
and a list of {max_descriptions} descriptions. Each headline must be no 
longer than 30 characters, and each description must be no longer than 90 
characters.
""".replace("\n", " ").replace("  ", " ")

COPYCAT_PARAMS_FILE_NAME = "copycat_params.json"


class CopycatResponseError(ValueError):
  """The error raised when the CopycatResponse is not successful."""


class CopycatResponse(pydantic.BaseModel):
  """The response from Copycat.

  Attributes:
    google_ad: The generated ad.
    keywords: The keywords used to generate the ad, as a comma separated string.
    evaluation_results: The evaluation results of the ad, including whether it
      is memorised from the training data, and it's style and keyword similarity
      metrics.
    success: Whether the generation was successful.
    error_message: The error message if the generation was not successful.
  """

  google_ad: GoogleAd
  keywords: str
  evaluation_results: ad_copy_evaluator.EvaluationResults

  @property
  def success(self) -> bool:
    return not self.error_message

  @property
  def error_message(self) -> str:
    return "\n".join(
        map(lambda x: f"- {x}", sorted(self.evaluation_results.errors))
    )

  def raise_if_not_success(self) -> None:
    if not self.success:
      raise CopycatResponseError(self.error_message)


@dataclasses.dataclass
class Copycat:
  """The Copycat model which generates ad copies in the advertisers style.

  Attributes:
    ad_copy_vectorstore: The vectorstore containing the training ad copies.
    ad_format: The ad format that copycat will generate (same as the ad format
      of the examples in the vectorstore).
    output_parser: The output parser to use to parse the output of the chat
      model to a GoogleAd.
    ad_copy_evaluator: The ad copy evaluator to use to evaluate the generated ad
      copies.
  """

  ad_copy_vectorstore: ad_copy_generator.AdCopyVectorstore
  ad_format: GoogleAdFormat

  @property
  def ad_copy_evaluator(self) -> ad_copy_evaluator.AdCopyEvaluator:
    return ad_copy_evaluator.AdCopyEvaluator(
        self.ad_format,
        ad_copy_vectorstore=self.ad_copy_vectorstore,
    )

  @classmethod
  def _clean_invalid_ads(
      cls, data: pd.DataFrame, ad_format: GoogleAdFormat, on_invalid_ad: str
  ) -> pd.DataFrame:
    """Cleans the invalid ads from the training data.

    Args:
      data: The training data containing the headlines, descriptions and
        keywords.
      ad_format: The ad format used in this vectorstore.
      on_invalid_ad: The action to take on invalid ads. Must be one of "raise",
        "skip", or "drop".

    Returns:
      The training data with the invalid ads handled. If on_invalid_ad is
      "raise", then an error is raised. If on_invalid_ad is "skip", then the
      invalid ads are kept in the training data. If on_invalid_ad is "drop",
      then the invalid ads are dropped from the training data.

    Raises:
      ValueError: If on_invalid_ad is not one of "raise", "skip", or "drop".
      ValueError: If there are invalid ads in the training data and
        on_invalid_ad is "raise".
    """
    evaluator = ad_copy_evaluator.AdCopyEvaluator(ad_format)

    if on_invalid_ad not in ["raise", "skip", "drop"]:
      raise ValueError(
          f"Invalid value for on_invalid_ad: {on_invalid_ad}. Must be one of"
          " 'raise', 'skip', or 'drop'."
      )

    is_invalid = data.apply(
        lambda row: not evaluator.is_valid(
            GoogleAd(
                headlines=row["headlines"], descriptions=row["descriptions"]
            )
        ),
        axis=1,
    )
    n_invalid_ads = is_invalid.sum()
    frac_invalid_ads = n_invalid_ads / len(data)
    error_message = (
        f"{n_invalid_ads:,} ({frac_invalid_ads:.2%}) invalid ads found in the"
        " training data."
    )

    if n_invalid_ads > 0:
      if on_invalid_ad == "raise":
        raise ValueError(error_message)
      elif on_invalid_ad == "skip":
        warnings.warn(error_message + " Keeping them in the training data.")
      elif on_invalid_ad == "drop":
        warnings.warn(error_message + " Dropping them from the training data.")
        data = data[~is_invalid]

    return data

  @classmethod
  def create_from_pandas(
      cls,
      *,
      training_data: pd.DataFrame,
      embedding_model_name: str | EmbeddingModelName,
      ad_format: str | GoogleAdFormat,
      on_invalid_ad: str = "drop",
      embedding_model_dimensionality: int = 256,
      vectorstore_max_initial_ads: int = 2000,
      vectorstore_max_exemplar_ads: int = 200,
      vectorstore_affinity_preference: float | None = None,
      vectorstore_exemplar_selection_method: (
          str | ExemplarSelectionMethod
      ) = "affinity_propagation",
      embedding_model_batch_size: int = 50,
  ) -> "Copycat":
    """Creates a Copycat model from a pandas dataframe.

    The pandas dataframe must contain the columns "headline", "description", and
    "keywords", with a different row per ad.

    Args:
      training_data: The historical ad copies to learn the style from. Must
        contain the columns "headline", "description", and "keywords".
      embedding_model_name: The name of the embedding model to use to create the
        ad copy vectorstore.
      ad_format: The ad format that copycat will generate (same as the ad format
        of the examples in the training data).
      on_invalid_ad: How to handle invalid ads in the training data. Must be one
        of "drop", "raise", or "skip". "drop" means that the invalid ads will be
        dropped. "raise" means that an exception will be raised. "skip" means
        that the invalid ads will remain in the training data.
      embedding_model_dimensionality: The dimensionality of the embedding model.
      vectorstore_max_initial_ads: The maximum number of ads to use from the
        training data when creating the ad copy vectorstore.
      vectorstore_max_exemplar_ads: The maximum number of exemplar ads to use in
        the ad copy vectorstore.
      vectorstore_affinity_preference: The affinity preference to use when
        finding exemplar ads.
      vectorstore_exemplar_selection_method: The method to use to select the
        exemplar ads. Either "affinity_propagation" or "random". Defaults to
        "affinity_propagation".
      embedding_model_batch_size: The batch size to use when generating
        embeddings.

    Returns:
      A Copycat model.

    Raises:
      ValueError: If the training data does not contain the required columns.
    """
    if isinstance(ad_format, str):
      ad_format = google_ads.get_google_ad_format(ad_format)

    required_columns = {"headlines", "descriptions", "keywords"}
    missing_columns = required_columns - set(training_data.columns)
    if missing_columns:
      raise ValueError(
          f"Training data must contain the columns {sorted(required_columns)}."
          f" Missing columns: {sorted(missing_columns)}."
      )

    training_data = cls._clean_invalid_ads(
        training_data, ad_format, on_invalid_ad
    )

    ad_copy_vectorstore = (
        ad_copy_generator.AdCopyVectorstore.create_from_pandas(
            training_data=training_data,
            embedding_model_name=embedding_model_name,
            dimensionality=embedding_model_dimensionality,
            max_initial_ads=vectorstore_max_initial_ads,
            max_exemplar_ads=vectorstore_max_exemplar_ads,
            affinity_preference=vectorstore_affinity_preference,
            embeddings_batch_size=embedding_model_batch_size,
            exemplar_selection_method=vectorstore_exemplar_selection_method,
        )
    )

    return cls(
        ad_copy_vectorstore=ad_copy_vectorstore,
        ad_format=ad_format,
    )

  @classmethod
  def load(cls, path: str) -> "Copycat":
    """Loads an existing Copycat model from a file.

    Args:
      path: The path to the directory containing the Copycat model.

    Returns:
      A Copycat model.
    """

    with open(f"{path}/{COPYCAT_PARAMS_FILE_NAME}", "r") as f:
      params = json.load(f)

    ad_copy_vectorstore = ad_copy_generator.AdCopyVectorstore.load(path)

    return cls(
        ad_copy_vectorstore=ad_copy_vectorstore,
        ad_format=GoogleAdFormat(**params["ad_format_params"]),
    )

  def write(self, path: str) -> None:
    """Writes the model to the persist path specified in the constructor.

    Args:
      path: The path to write the model to.
    """
    params = {"ad_format_params": self.ad_format.model_dump()}

    with open(f"{path}/{COPYCAT_PARAMS_FILE_NAME}", "w") as f:
      json.dump(params, f)

    self.ad_copy_vectorstore.write(path)

  def construct_responses(
      self,
      raw_generated_ads: list[generative_models.Candidate],
      keywords: list[str],
  ) -> list[CopycatResponse]:
    """Constructs a CopycatResponse from a generated GoogleAd.

    Args:
      raw_generated_ads: The unprocessed generated ads as a generation
        candidates.
      keywords: The keywords used to generate the ads.

    Returns:
      A CopycatResponse object.
    """
    empty_ad_copy = GoogleAd(headlines=[], descriptions=[])
    empty_evaluation_results = ad_copy_evaluator.EvaluationResults(
        errors=[],
        warnings=[],
        headlines_are_memorised=None,
        descriptions_are_memorised=None,
        keyword_similarity=None,
        style_similarity=None,
    )

    responses = []
    for keywords_i, raw_ad_i in zip(keywords, raw_generated_ads):
      if raw_ad_i.finish_reason is not ad_copy_generator.FinishReason.STOP:
        responses.append(
            CopycatResponse(
                google_ad=empty_ad_copy.model_copy(),
                keywords=keywords_i,
                evaluation_results=empty_evaluation_results.model_copy(
                    update=dict(errors=[str(raw_ad_i)])
                ),
            )
        )
        continue

      try:
        ad_copy = GoogleAd.model_validate_json(raw_ad_i.content.parts[0].text)
      except ValidationError as e:
        responses.append(
            CopycatResponse(
                google_ad=empty_ad_copy,
                keywords=keywords_i,
                evaluation_results=empty_evaluation_results.model_copy(
                    update=dict(errors=[str(e)])
                ),
            )
        )
        continue

      ad_copy_generator.remove_invalid_headlines_and_descriptions(
          ad_copy, self.ad_format
      )

      responses.append(
          CopycatResponse(
              google_ad=ad_copy,
              keywords=keywords_i,
              evaluation_results=empty_evaluation_results,
          )
      )

    return responses

  def _evaluate_responses(
      self,
      responses: list[CopycatResponse],
      allow_memorised_headlines: bool,
      allow_memorised_descriptions: bool,
  ) -> list[CopycatResponse]:
    """Evaluates the responses if the ad copy is not empty.

    If the ad copy is empty, then it is not evaluated.

    Args:
      responses: The responses to evaluate.
      allow_memorised_headlines: Whether to allow memorised headlines.
      allow_memorised_descriptions: Whether to allow memorised descriptions.

    Returns:
      The evaluated responses.
    """
    evaluation_results_list = self.ad_copy_evaluator.evaluate_batch(
        ad_copies=[response.google_ad for response in responses],
        allow_memorised_headlines=allow_memorised_headlines,
        allow_memorised_descriptions=allow_memorised_descriptions,
        keywords=[response.keywords for response in responses],
    )
    evaluated_responses = []
    for response, evaluation_results in zip(responses, evaluation_results_list):
      if self.ad_copy_evaluator.is_empty(response.google_ad):
        evaluated_responses.append(response.model_copy())
      else:
        evaluated_responses.append(
            response.model_copy(
                update=dict(evaluation_results=evaluation_results)
            )
        )
    return evaluated_responses

  def construct_text_generation_requests_for_new_ad_copy(
      self,
      *,
      keywords: list[str],
      keywords_specific_instructions: list[str] | None = None,
      style_guide: str = "",
      system_instruction: str = DEFAULT_SYSTEM_INSTRUCTION,
      num_in_context_examples: int = 10,
      model_name: ModelName | str = ModelName.GEMINI_1_5_FLASH,
      temperature: float = 0.95,
      top_k: int = 20,
      top_p: float = 0.95,
      safety_settings: ad_copy_generator.SafetySettingsType | None = None,
      system_instruction_kwargs: dict[str, Any] | None = None,
  ) -> list[TextGenerationRequest]:
    """Constructs a request for generating a new ad copy.

    This prompt consists of a system prompt, a style guide, and a number of
    in context examples. The in context examples are retrieved from the ad copy
    vectorstore.

    Args:
      keywords: The list of keywords to use to generate the ad copies. This
        should be a list of strings, where each string is a comma separated list
        of keywords.
      keywords_specific_instructions: The list of keywords specific instructions
        to use. Defaults to a list of empty strings.
      style_guide: The style guide to use.
      system_instruction: The system instruction to use.
      num_in_context_examples: The number of in context examples to use.
      model_name: The name of the gemini model to use.
      temperature: The temperature to use for the chat model.
      top_k: The top-k to use for the chat model.
      top_p: The top-p to use for the chat model.
      safety_settings: The safety settings for the chat model.
      system_instruction_kwargs: Additional arguments to pass to the system
        instruction.

    Returns:
      A text generation request, containing the prompt, system instruction, and
      model parameters.
    """
    if keywords_specific_instructions is None:
      keywords_specific_instructions = [""] * len(keywords)

    system_instruction_kwargs = system_instruction_kwargs or {}
    default_system_instruction_kwargs = {
        "max_headlines": self.ad_format.max_headlines,
        "max_descriptions": self.ad_format.max_descriptions,
    }
    system_instruction_kwargs = (
        default_system_instruction_kwargs | system_instruction_kwargs
    )
    system_instruction = (
        ad_copy_generator.construct_system_instruction(
            system_instruction=system_instruction,
            style_guide=style_guide,
            system_instruction_kwargs=system_instruction_kwargs,
        )
    )

    relavent_example_ads = self.ad_copy_vectorstore.get_relevant_ads(
        keywords,
        k=num_in_context_examples,
    )

    prompts = [
        ad_copy_generator.construct_new_ad_copy_prompt(
            example_ads=relevant_example_ads_i,
            keywords=keywords_i,
            keywords_specific_instructions=keywords_specific_instructions_i,
        )
        for keywords_i, keywords_specific_instructions_i, relevant_example_ads_i in zip(
            keywords,
            keywords_specific_instructions,
            relavent_example_ads,
        )
    ]

    requests = [
        TextGenerationRequest(
            keywords=keywords_i,
            prompt=prompt_i,
            system_instruction=system_instruction,
            chat_model_name=ModelName(model_name),
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            safety_settings=safety_settings,
        )
        for keywords_i, prompt_i in zip(keywords, prompts)
    ]

    return requests

  def _generate_new_ad_copy_from_requests(
      self,
      requests: list[TextGenerationRequest],
  ) -> list[CopycatResponse]:
    """Generates a new ad copy from a list of requests.

    Args:
      requests: The requests to generate the ad copy from.

    Returns:
      A list of CopycatResponses.
    """
    generations = [
        response.candidates[0]
        for response in ad_copy_generator.generate_google_ad_json_batch(
            requests
        )
    ]
    keywords = [request.keywords for request in requests]

    responses = self.construct_responses(
        generations,
        keywords,
    )
    return responses

  def generate_new_ad_copy(
      self,
      *,
      keywords: list[str],
      keywords_specific_instructions: list[str] | None = None,
      style_guide: str = "",
      system_instruction: str = DEFAULT_SYSTEM_INSTRUCTION,
      num_in_context_examples: int = 10,
      model_name: ModelName | str = ModelName.GEMINI_1_5_FLASH,
      temperature: float = 0.95,
      top_k: int = 20,
      top_p: float = 0.95,
      allow_memorised_headlines: bool = True,
      allow_memorised_descriptions: bool = False,
      safety_settings: ad_copy_generator.SafetySettingsType | None = None,
      system_instruction_kwargs: dict[str, Any] | None = None,
  ) -> list[CopycatResponse]:
    """Generates a new ad copy.

    Args:
      keywords: The list of keywords to use to generate the ad copies. This
        should be a list of strings, where each string is a comma separated list
        of keywords.
      keywords_specific_instructions: The list of keywords specific instructions
        to use. Defaults to a list of empty strings.
      style_guide: The style guide to use.
      system_instruction: The system instruction to use.
      num_in_context_examples: The number of in context examples to use.
      model_name: The name of the chat model to use.
      temperature: The temperature to use for the chat model.
      top_k: The top-k to use for the chat model.
      top_p: The top-p to use for the chat model.
      allow_memorised_headlines: Whether to allow memorised headlines.
      allow_memorised_descriptions: Whether to allow memorised descriptions.
      safety_settings: The safety settings for the chat model.
      system_instruction_kwargs: Additional arguments to pass to the system
        instruction.

    Returns:
      A CopycatResponse object.

    Raises:
      ValueError: If keywords and keywords_specific_instructions have different
        lengths.
      RuntimeError: If the number of responses does not match the number of
        keywords. This shouldn't happen, if it happens it indicates a bug in the
        code.
    """
    if keywords_specific_instructions is None:
      keywords_specific_instructions = [""] * len(keywords)

    if len(keywords) != len(keywords_specific_instructions):
      raise ValueError(
          "keywords and keywords_specific_instructions must have the same"
          " length."
      )

    requests = self.construct_text_generation_requests_for_new_ad_copy(
        keywords=keywords,
        keywords_specific_instructions=keywords_specific_instructions,
        num_in_context_examples=num_in_context_examples,
        style_guide=style_guide,
        system_instruction=system_instruction,
        model_name=model_name,
        temperature=temperature,
        top_k=top_k,
        top_p=top_p,
        safety_settings=safety_settings,
        system_instruction_kwargs=system_instruction_kwargs,
    )

    responses = self._generate_new_ad_copy_from_requests(requests)

    evaluated_responses = self._evaluate_responses(
        responses,
        allow_memorised_headlines=allow_memorised_headlines,
        allow_memorised_descriptions=allow_memorised_descriptions,
    )

    if len(evaluated_responses) != len(keywords):
      raise RuntimeError(
          "The number of responses does not match the number of keywords."
      )

    return evaluated_responses
