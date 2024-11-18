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

from collections.abc import Mapping
import dataclasses
import json
import logging
from typing import Any, Callable
import warnings

from vertexai import generative_models
import pandas as pd
import pydantic

from copycat import ad_copy_evaluator
from copycat import ad_copy_generator
from copycat import google_ads
from copycat import keyword_organiser
from copycat import style_guide as style_guide_generator

GoogleAd = google_ads.GoogleAd
GoogleAdFormat = google_ads.GoogleAdFormat
ValidationError = pydantic.ValidationError
ModelName = ad_copy_generator.ModelName
EmbeddingModelName = ad_copy_generator.EmbeddingModelName
TextGenerationRequest = ad_copy_generator.TextGenerationRequest
ExemplarSelectionMethod = ad_copy_generator.ExemplarSelectionMethod
EvaluationResults = ad_copy_evaluator.EvaluationResults
StyleGuideGenerator = style_guide_generator.StyleGuideGenerator
BirchAgglomerativeKeywordClusterer = keyword_organiser.BirchAgglomerativeKeywordClusterer

# Below are not used in this file, they are included for the user to easily
# adjust the safety settings in copycat without having to import
# generative_models from vertex ai.
HarmCategory = ad_copy_generator.generative_models.HarmCategory
HarmBlockThreshold = ad_copy_generator.generative_models.HarmBlockThreshold
ALL_SAFETY_SETTINGS_OFF = {
    harm_category: HarmBlockThreshold.BLOCK_NONE
    for harm_category in HarmCategory
}

ALL_SAFETY_SETTINGS_ONLY_HIGH = {
    harm_category: HarmBlockThreshold.BLOCK_ONLY_HIGH
    for harm_category in HarmCategory
}

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


DEFAULT_SYSTEM_INSTRUCTION = """\
You are an expert marketing professional, working for {company_name}. You are
tasked with writing new headlines and descriptions for Google Ads in {language},
given a new set of keywords, that will maximize engagement and clicks.
Keywords are words or phrases that are used to match ads with the terms that
people are searching for, so the copy should be engaging for someone searching
for those keywords. For each ad you must produce a list of headlines and a list
of descriptions, and those headlines and descriptions should be varied, while 
making sense in any combination together - Google Ads will select different 
combinations of headlines and descriptions to display to users. Each headline 
must be no longer than {max_headline_length} characters, and each description 
must be no longer than {max_description_length} characters.
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

  @property
  def warning_message(self) -> str:
    return "\n".join(
        map(lambda x: f"- {x}", sorted(self.evaluation_results.warnings))
    )

  def raise_if_not_success(self) -> None:
    if not self.success:
      LOGGER.error("CopycatResponse is not successful: %s", self.error_message)
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
    style_guide: The style guide to use to generate the ad copies.
  """

  ad_copy_vectorstore: ad_copy_generator.AdCopyVectorstore
  ad_format: GoogleAdFormat
  style_guide: str = ""

  @property
  def ad_copy_evaluator(self) -> ad_copy_evaluator.AdCopyEvaluator:
    return ad_copy_evaluator.AdCopyEvaluator(
        self.ad_format,
        ad_copy_vectorstore=self.ad_copy_vectorstore,
    )

  @classmethod
  def _clean_invalid_ads(
      cls,
      data: pd.DataFrame,
      ad_format: GoogleAdFormat,
      on_invalid_ad: str,
      replace_special_variables_with_default: bool,
  ) -> pd.DataFrame:
    """Cleans the invalid ads from the training data.

    Args:
      data: The training data containing the headlines, descriptions and
        keywords.
      ad_format: The ad format used in this vectorstore.
      on_invalid_ad: The action to take on invalid ads. Must be one of "raise",
        "skip", or "drop".
      replace_special_variables_with_default: Whether to replace Google Ads
        special variables with their default values.

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
    LOGGER.info(
        "Cleaning invalid ads from the training data. Will %s invalid ads.",
        on_invalid_ad,
    )

    if on_invalid_ad not in ["raise", "skip", "drop"]:
      LOGGER.error("Invalid value for on_invalid_ad: %s", on_invalid_ad)
      raise ValueError(
          f"Invalid value for on_invalid_ad: {on_invalid_ad}. Must be one of"
          " 'raise', 'skip', or 'drop'."
      )

    if replace_special_variables_with_default:
      data["headlines"] = data["headlines"].apply(
          lambda headlines: list(
              map(google_ads.parse_google_ads_special_variables, headlines)
          )
      )
      data["descriptions"] = data["descriptions"].apply(
          lambda descriptions: list(
              map(google_ads.parse_google_ads_special_variables, descriptions)
          )
      )
      is_invalid = data.apply(
          lambda row: not evaluator.is_valid(
              GoogleAd(
                  headlines=row["headlines"], descriptions=row["descriptions"]
              )
          )
          or evaluator.has_unfillable_google_ads_special_variables(
              GoogleAd(
                  headlines=row["headlines"], descriptions=row["descriptions"]
              )
          ),
          axis=1,
      )
    else:
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
        LOGGER.error(error_message)
        raise ValueError(error_message)
      elif on_invalid_ad == "skip":
        LOGGER.warning("%s Keeping them in the training data.", error_message)
        warnings.warn(error_message + " Keeping them in the training data.")
      elif on_invalid_ad == "drop":
        LOGGER.warning(
            "%s Dropping them from the training data.", error_message
        )
        warnings.warn(error_message + " Dropping them from the training data.")
        data = data[~is_invalid]
    else:
      LOGGER.info("No invalid ads found in the training data.")

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
      replace_special_variables_with_default: bool = False,
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
      replace_special_variables_with_default: Whether to replace Google Ads
        special variables with their default values. These are things like
        Dynamic Keyword Insertion and Customizers. If you replace them with
        their default values then Copycat won't try to learn them, and it will
        just generate generic ads without DKI or Customizers. If you keep them
        then it might try to generate them, but this can sometimes not work
        well.

    Returns:
      A Copycat model.

    Raises:
      ValueError: If the training data does not contain the required columns.
    """
    training_data = training_data.copy()

    if isinstance(ad_format, str):
      ad_format = google_ads.get_google_ad_format(ad_format)

    required_columns = {"headlines", "descriptions", "keywords"}
    missing_columns = required_columns - set(training_data.columns)
    if missing_columns:
      LOGGER.error(
          "Training data must contain the columns %s. Missing columns: %s.",
          sorted(required_columns),
          sorted(missing_columns),
      )
      raise ValueError(
          f"Training data must contain the columns {sorted(required_columns)}."
          f" Missing columns: {sorted(missing_columns)}."
      )

    training_data = cls._clean_invalid_ads(
        training_data,
        ad_format,
        on_invalid_ad,
        replace_special_variables_with_default,
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
  def from_dict(cls, params: dict[str, Any]) -> "Copycat":
    """Loads the model from the provided dict.

    Schema of params:
      ad_copy_vectorstore: The ad copy vectorstore to use. This is a dict
        containing the parameters to use to create the ad copy vectorstore. See
        AdCopyVectorstore.from_dict for the required keys.
      ad_format_params: The parameters to use to create the ad format. Must
        include the following keys:
        - max_headlines: The maximum number of headlines to generate.
        - max_descriptions: The maximum number of descriptions to generate.

    Args:
      params: The dict containing the parameters to use to create the Copycat
        model. See above for the schema.

    Returns:
      A Copycat model.

    Raises:
      KeyError: If any of the required keys are missing from the dict.
    """
    required_keys = {
        "ad_copy_vectorstore",
        "ad_format_params",
    }
    missing_keys = required_keys - set(params.keys())
    if missing_keys:
      LOGGER.error("Missing required keys: %s", missing_keys)
      raise KeyError(f"Missing required keys: {missing_keys}")

    return cls(
        ad_copy_vectorstore=ad_copy_generator.AdCopyVectorstore.from_dict(
            params["ad_copy_vectorstore"]
        ),
        ad_format=GoogleAdFormat(**params["ad_format_params"]),
        style_guide=params.get("style_guide", ""),
    )

  def to_dict(self) -> dict[str, Any]:
    """Serializes the model to a dict."""
    return {
        "ad_format_params": self.ad_format.model_dump(),
        "ad_copy_vectorstore": self.ad_copy_vectorstore.to_dict(),
        "style_guide": self.style_guide,
    }

  @classmethod
  def from_json(cls, json_string: str) -> "Copycat":
    """Loads the model from the provided json string.

    Schema of params:
      ad_copy_vectorstore: The ad copy vectorstore to use. This is a dict
        containing the parameters to use to create the ad copy vectorstore. See
        AdCopyVectorstore.from_dict for the required keys.
      ad_format_params: The parameters to use to create the ad format. Must
        include the following keys:
        - max_headlines: The maximum number of headlines to generate.
        - max_descriptions: The maximum number of descriptions to generate.

    Args:
      json_string: The json string containing the parameters to use to create
        the Copycat model. See above for the schema.

    Returns:
      A Copycat model.

    Raises:
      KeyError: If any of the required keys are missing from the dict.
    """
    return cls.from_dict(json.loads(json_string))

  def to_json(self) -> str:
    """Serializes the model to a json string."""
    return json.dumps(self.to_dict())

  def construct_responses(
      self,
      raw_generated_ads: list[generative_models.Candidate],
      keywords: list[str],
      existing_ad_copies: list[GoogleAd],
  ) -> list[CopycatResponse]:
    """Constructs a CopycatResponse from a generated GoogleAd.

    Args:
      raw_generated_ads: The unprocessed generated ads as a generation
        candidates.
      keywords: The keywords used to generate the ads.
      existing_ad_copies: The existing ad copies if they exist, to be merged
        with the generated ad copies.

    Returns:
      A CopycatResponse object.
    """
    empty_evaluation_results = ad_copy_evaluator.EvaluationResults(
        errors=[],
        warnings=[],
        headlines_are_memorised=None,
        descriptions_are_memorised=None,
        keyword_similarity=None,
        style_similarity=None,
    )

    responses = []
    for keywords_i, raw_generated_ad_i, existing_ad_copy_i in zip(
        keywords, raw_generated_ads, existing_ad_copies
    ):
      if (
          raw_generated_ad_i.finish_reason
          is not ad_copy_generator.FinishReason.STOP
      ):
        responses.append(
            CopycatResponse(
                google_ad=existing_ad_copy_i.model_copy(),
                keywords=keywords_i,
                evaluation_results=empty_evaluation_results.model_copy(
                    update=dict(errors=[str(raw_generated_ad_i)])
                ),
            )
        )
        LOGGER.error(
            "Generated ad did not finish. Complete response: %s.",
            raw_generated_ad_i,
        )
        continue

      try:
        LOGGER.debug(
            "Generation for keywords %s\n\n%s",
            keywords_i,
            raw_generated_ad_i.content.parts[0].text,
        )
        generated_ad_copy = GoogleAd.model_validate_json(
            raw_generated_ad_i.content.parts[0].text
        )
      except ValidationError as e:
        responses.append(
            CopycatResponse(
                google_ad=existing_ad_copy_i.model_copy(),
                keywords=keywords_i,
                evaluation_results=empty_evaluation_results.model_copy(
                    update=dict(errors=[str(e)])
                ),
            )
        )
        LOGGER.error(
            "Generated ad was not matching the expected json format."
            " Error: %s.",
            e,
        )
        continue

      ad_copy = existing_ad_copy_i.model_copy() + generated_ad_copy
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
        merged_evaluation_results = evaluation_results.model_copy(
            update=dict(
                warnings=response.evaluation_results.warnings
                + evaluation_results.warnings,
                errors=response.evaluation_results.errors
                + evaluation_results.errors,
            )
        )
        evaluated_responses.append(
            response.model_copy(
                update=dict(evaluation_results=merged_evaluation_results)
            )
        )
    return evaluated_responses

  def construct_text_generation_requests_for_new_ad_copy(
      self,
      *,
      keywords: list[str],
      keywords_specific_instructions: list[str] | None = None,
      style_guide: str | None = None,
      system_instruction: str = DEFAULT_SYSTEM_INSTRUCTION,
      num_in_context_examples: int = 10,
      model_name: ModelName | str = ModelName.GEMINI_1_5_FLASH,
      temperature: float = 0.95,
      top_k: int = 20,
      top_p: float = 0.95,
      safety_settings: ad_copy_generator.SafetySettingsType | None = None,
      system_instruction_kwargs: dict[str, Any] | None = None,
      existing_headlines: list[list[str]] | None = None,
      existing_descriptions: list[list[str]] | None = None,
  ) -> list[TextGenerationRequest]:
    """Constructs a request for generating a new ad copy.

    This prompt consists of a system prompt, a style guide, and a number of
    in context examples. The in context examples are retrieved from the ad copy
    vectorstore.

    If there are already some headlines or descriptions, then the prompt will
    ask Copycat to extend the ad copy to the required number of headlines and
    descriptions for the ad format.

    Args:
      keywords: The list of keywords to use to generate the ad copies. This
        should be a list of strings, where each string is a comma separated list
        of keywords.
      keywords_specific_instructions: The list of keywords specific instructions
        to use. Defaults to a list of empty strings.
      style_guide: The style guide to use. If None, then the style guide from
        the Copycat model will be used.
      system_instruction: The system instruction to use.
      num_in_context_examples: The number of in context examples to use.
      model_name: The name of the gemini model to use.
      temperature: The temperature to use for the chat model.
      top_k: The top-k to use for the chat model.
      top_p: The top-p to use for the chat model.
      safety_settings: The safety settings for the chat model.
      system_instruction_kwargs: Additional arguments to pass to the system
        instruction.
      existing_headlines: The existing headlines for the ad copy. If no
        headlines then pass None.
      existing_descriptions: The existing descriptions for the ad copy. If no
        descriptions then pass None.

    Returns:
      A text generation request, containing the prompt, system instruction, and
      model parameters.
    """
    if keywords_specific_instructions is None:
      keywords_specific_instructions = [""] * len(keywords)
    if existing_headlines is None:
      existing_headlines = [None] * len(keywords)
    if existing_descriptions is None:
      existing_descriptions = [None] * len(keywords)

    system_instruction_kwargs = system_instruction_kwargs or {}
    default_system_instruction_kwargs = {
        "max_headline_length": self.ad_format.max_headline_length,
        "max_description_length": self.ad_format.max_description_length,
    }
    system_instruction_kwargs = (
        default_system_instruction_kwargs | system_instruction_kwargs
    )
    if style_guide is None:
      style_guide = self.style_guide
    system_instruction = ad_copy_generator.construct_system_instruction(
        system_instruction=system_instruction,
        style_guide=style_guide,
        system_instruction_kwargs=system_instruction_kwargs,
    )

    relavent_example_ads = self.ad_copy_vectorstore.get_relevant_ads(
        keywords,
        k=num_in_context_examples,
    )

    existing_ad_copies = [
        GoogleAd(
            headlines=headlines_i or [],
            descriptions=descriptions_i or [],
        )
        for headlines_i, descriptions_i in zip(
            existing_headlines,
            existing_descriptions,
        )
    ]

    prompts = [
        ad_copy_generator.construct_new_ad_copy_prompt(
            example_ads=relevant_example_ads_i,
            keywords=keywords_i,
            ad_format=self.ad_format,
            existing_ad_copy=existing_ad_copy_i,
            keywords_specific_instructions=keywords_specific_instructions_i,
        )
        for keywords_i, keywords_specific_instructions_i, relevant_example_ads_i, existing_ad_copy_i in zip(
            keywords,
            keywords_specific_instructions,
            relavent_example_ads,
            existing_ad_copies,
        )
    ]

    requests = [
        TextGenerationRequest(
            keywords=keywords_i,
            existing_ad_copy=existing_ad_copy_i,
            prompt=prompt_i,
            system_instruction=system_instruction,
            chat_model_name=ModelName(model_name),
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            safety_settings=safety_settings,
        )
        for keywords_i, prompt_i, existing_ad_copy_i in zip(
            keywords, prompts, existing_ad_copies
        )
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
    existing_ad_copies = [request.existing_ad_copy for request in requests]

    responses = self.construct_responses(
        generations,
        keywords,
        existing_ad_copies,
    )
    return responses

  def generate_new_ad_copy(
      self,
      *,
      keywords: list[str],
      keywords_specific_instructions: list[str] | None = None,
      style_guide: str | None = None,
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
      existing_headlines: list[list[str]] | None = None,
      existing_descriptions: list[list[str]] | None = None,
  ) -> list[CopycatResponse]:
    """Generates a new ad copy.

    Args:
      keywords: The list of keywords to use to generate the ad copies. This
        should be a list of strings, where each string is a comma separated list
        of keywords.
      keywords_specific_instructions: The list of keywords specific instructions
        to use. Defaults to a list of empty strings.
      style_guide: The style guide to use. If None, then the style guide from
        the Copycat model will be used.
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
      existing_headlines: The existing headlines for the ad copy. If no
        headlines then pass None.
      existing_descriptions: The existing descriptions for the ad copy. If no
        descriptions then pass None.

    Returns:
      A CopycatResponse object.

    Raises:
      ValueError: If keywords, keywords_specific_instructions, existing
        headlines or existing descriptions have different lengths.
      RuntimeError: If the number of responses does not match the number of
        keywords. This shouldn't happen, if it happens it indicates a bug in the
        code.
    """
    if keywords_specific_instructions is None:
      keywords_specific_instructions = [""] * len(keywords)
    if existing_headlines is None:
      existing_headlines = [None] * len(keywords)
    if existing_descriptions is None:
      existing_descriptions = [None] * len(keywords)

    if len(keywords) != len(keywords_specific_instructions):
      LOGGER.error(
          "keywords and keywords_specific_instructions must have the same"
          " length."
      )
      raise ValueError(
          "keywords and keywords_specific_instructions must have the same"
          " length."
      )
    if len(existing_headlines) != len(keywords):
      LOGGER.error("keywords and existing_headlines must have the same length.")
      raise ValueError(
          "keywords and existing_headlines must have the same length."
      )
    if len(existing_descriptions) != len(keywords):
      LOGGER.error(
          "keywords and existing_descriptions must have the same length."
      )
      raise ValueError(
          "keywords and existing_descriptions must have the same length."
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
        existing_headlines=existing_headlines,
        existing_descriptions=existing_descriptions,
    )

    responses = self._generate_new_ad_copy_from_requests(requests)

    evaluated_responses = self._evaluate_responses(
        responses,
        allow_memorised_headlines=allow_memorised_headlines,
        allow_memorised_descriptions=allow_memorised_descriptions,
    )

    if len(evaluated_responses) != len(keywords):
      LOGGER.error(
          "The number of responses does not match the number of keywords."
      )
      raise RuntimeError(
          "The number of responses does not match the number of keywords."
      )

    return evaluated_responses

  def generate_new_ad_copy_for_dataframe(
      self,
      data: pd.DataFrame,
      *,
      keywords_column: str = "keywords",
      keywords_specific_instructions_column: (
          str
      ) = "keywords_specific_instructions",
      existing_headlines_column: str = "existing_headlines",
      existing_descriptions_column: str = "existing_descriptions",
      **static_params: Any,
  ) -> pd.Series:
    """Applies the generate new ad copy function to a dataframe.

    This will generate a new ad copy for each row in the dataframe, using the
    keywords, keywords_specific_instructions, existing_headlines and
    existing_descriptions columns from that row. All other parameters are
    static and will be passed to the generate_new_ad_copy function.

    Args:
      data: The dataframe to apply the generate new ad copy function to.
      keywords_column: The name of the column containing the keywords.
      keywords_specific_instructions_column: The name of the column containing
        the keywords specific instructions. If the column is not present then
        None will be used as the value.
      existing_headlines_column: The name of the column containing the existing
        headlines. If the column is not present then None will be used as the
        value.
      existing_descriptions_column: The name of the column containing the
        existing descriptions. If the column is not present then None will be
        used as the value.
      **static_params: The static parameters to pass to the generate new ad copy
        function. See the generate_new_ad_copy function for the list of
        available parameters.

    Returns:
      A series of CopycatResponses.

    Raises:
      ValueError: If the dataframe does not contain the required keywords
        column.
    """
    if keywords_column in data.columns:
      keywords = data[keywords_column]
    else:
      LOGGER.error(
          "The dataframe does not contain the required column: %s",
          keywords_column,
      )
      raise ValueError(
          "The dataframe does not contain the required column:"
          f" {keywords_column}"
      )

    if keywords_specific_instructions_column in data.columns:
      keywords_specific_instructions = data[
          keywords_specific_instructions_column
      ]
    else:
      LOGGER.warning(
          "The dataframe does not contain the optional column: %s",
          keywords_specific_instructions_column,
      )
      keywords_specific_instructions = [None] * len(keywords)

    if existing_headlines_column in data.columns:
      existing_headlines = data[existing_headlines_column]
    else:
      LOGGER.warning(
          "The dataframe does not contain the optional column: %s",
          existing_headlines_column,
      )
      existing_headlines = [None] * len(keywords)

    if existing_descriptions_column in data.columns:
      existing_descriptions = data[existing_descriptions_column]
    else:
      LOGGER.warning(
          "The dataframe does not contain the optional column: %s",
          existing_descriptions_column,
      )
      existing_descriptions = [None] * len(keywords)

    generated_responses = self.generate_new_ad_copy(
        keywords=keywords,
        keywords_specific_instructions=keywords_specific_instructions,
        existing_headlines=existing_headlines,
        existing_descriptions=existing_descriptions,
        **static_params,
    )
    return pd.Series(generated_responses, index=data.index)

  def generate_style_guide(
      self,
      *,
      company_name: str,
      files_uri: str = "",
      additional_style_instructions: str = "",
      model_name: ModelName | str = ModelName.GEMINI_1_5_PRO,
      safety_settings: ad_copy_generator.SafetySettingsType | None = None,
      temperature: float = 0.95,
      top_k: int = 20,
      top_p: float = 0.95,
      use_exemplar_ads: bool = True,
  ) -> str:
    """Generates a style guide for the ad copy.

    The style guide is returned and also stored in the Copycat instance.

    Args:
      company_name: The name of the company.
      files_uri: The URI of the files to use to generate the style guide.
      additional_style_instructions: Additional instructions to use to generate
        the style guide.
      model_name: The name of the chat model to use.
      safety_settings: The safety settings for the chat model.
      temperature: The temperature to use for the chat model.
      top_k: The top-k to use for the chat model.
      top_p: The top-p to use for the chat model.
      use_exemplar_ads: Whether to use exemplar ads to generate the style guide.

    Returns:
      The generated style guide.

    Raises:
      ValueError: If the company name is not provided.
      ValueError: If the files URI is not provided and use_exemplar_ads is
        False.
      RuntimeError: If the style guide generation was not successful.
    """
    if not use_exemplar_ads and not files_uri:
      raise ValueError(
          "Must either provide a files URI or set use_exemplar_ads to True."
      )
    if not company_name:
      raise ValueError("Must provide a company name.")

    generator = StyleGuideGenerator()
    if files_uri:
      LOGGER.info("Checking for files in the GCP bucket %s", files_uri)
      generator.get_all_files(files_uri)

    model_response = generator.generate_style_guide(
        brand_name=company_name,
        ad_copy_vectorstore=self.ad_copy_vectorstore,
        additional_style_instructions=additional_style_instructions,
        model_name=model_name,
        safety_settings=safety_settings,
        temperature=temperature,
        top_k=top_k,
        top_p=top_p,
    ).candidates[0]
    if model_response.finish_reason is not ad_copy_generator.FinishReason.STOP:
      message = (
          "Style guide generation was not successful, complete response:"
          f" {model_response}"
      )
      LOGGER.error(message)
      raise RuntimeError(message)

    self.style_guide = model_response.content.text
    return self.style_guide
