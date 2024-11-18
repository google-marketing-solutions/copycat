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

import dataclasses
import re

import pydantic
from sklearn.metrics import pairwise

from copycat import ad_copy_generator
from copycat import google_ads


GoogleAd = google_ads.GoogleAd
GoogleAdFormat = google_ads.GoogleAdFormat


class EvaluationResults(pydantic.BaseModel):
  """The metrics used to evaluate the generated ad."""

  headlines_are_memorised: bool | None
  descriptions_are_memorised: bool | None
  errors: list[str]
  warnings: list[str]
  style_similarity: float | None
  keyword_similarity: float | None


def _normalized_cosine_similarity(
    embedding_1: list[float], embedding_2: list[float]
) -> float:
  """Calculate the cosine similarity normalized to a value between 0 and 1."""
  similarity = float(
      pairwise.cosine_similarity([embedding_1], [embedding_2])[0][0]
  )
  return min(max((1.0 + similarity) / 2.0, 0.0), 1.0)


@dataclasses.dataclass
class AdCopyEvaluator:
  """Evaluates the ad copy.

  Attributes:
    ad_format: The ad format.
    ad_copy_vectorstore: The vectorstore containing the training ads, if
      provided. Defaults to None.
    training_headlines: The headlines in the training data.
    training_descriptions: The descriptions in the training data.
  """

  ad_format: GoogleAdFormat
  ad_copy_vectorstore: ad_copy_generator.AdCopyVectorstore | None = None

  @property
  def training_headlines(self) -> set[str]:
    if self.ad_copy_vectorstore is None:
      return set()
    return self.ad_copy_vectorstore.unique_headlines

  @property
  def training_descriptions(self) -> set[str]:
    if self.ad_copy_vectorstore is None:
      return set()
    return self.ad_copy_vectorstore.unique_descriptions

  def has_valid_number_of_headlines(self, ad_copy: GoogleAd) -> bool:
    """Returns true if the number of headlines is valid.

    The number of headlines is valid if it is less than or equal to the maximum
    number of headlines for the ad format, and greater than or equal the minimum
    number of headlines for the ad format.

    Args:
      ad_copy: The ad copy to evaluate.
    """
    return (ad_copy.headline_count <= self.ad_format.max_headlines) and (
        ad_copy.headline_count >= self.ad_format.min_headlines
    )

  def has_valid_number_of_descriptions(self, ad_copy: GoogleAd) -> bool:
    """Returns true if the number of descriptions is valid.

    The number of descriptions is valid if it is less than or equal to the
    maximum number of descriptions for the ad format, and greater than or equal
    to the minimum number of descriptions for the ad format.

    Args:
      ad_copy: The ad copy to evaluate.
    """
    return (ad_copy.description_count <= self.ad_format.max_descriptions) and (
        ad_copy.description_count >= self.ad_format.min_descriptions
    )

  def has_valid_headline_lengths(self, ad_copy: GoogleAd) -> bool:
    """Returns true if the lengths of the headlines are valid.

    The lengths of the headlines are valid if they are all less than or equal to
    the maximum length for a headline.

    Args:
      ad_copy: The ad copy to evaluate.
    """
    return all(
        len(google_ads.parse_google_ads_special_variables(headline))
        <= self.ad_format.max_headline_length
        for headline in ad_copy.headlines
    )

  def has_valid_description_lengths(self, ad_copy: GoogleAd) -> bool:
    """Returns true if the lengths of the descriptions are valid.

    The lengths of the descriptions are valid if they are all less than or equal
    to the maximum length for a description.

    Args:
      ad_copy: The ad copy to evaluate.
    """
    return all(
        len(google_ads.parse_google_ads_special_variables(description))
        <= self.ad_format.max_description_length
        for description in ad_copy.descriptions
    )

  def has_unique_headlines(self, ad_copy: GoogleAd) -> bool:
    """Returns true if there are no duplicate headlines.

    Args:
      ad_copy: The ad copy to evaluate.
    """
    return len(set(ad_copy.headlines)) == len(ad_copy.headlines)

  def has_unique_descriptions(self, ad_copy: GoogleAd) -> bool:
    """Returns true if there are no duplicate descriptions.

    Args:
      ad_copy: The ad copy to evaluate.
    """
    return len(set(ad_copy.descriptions)) == len(ad_copy.descriptions)

  def is_valid(self, ad_copy: GoogleAd) -> bool:
    """Returns true if the ad copy is valid.

    This checks that the number of headlines and descriptions is within the
    limits for the ad format, the headlines and descriptions are unique, and
    that the length of each headline and description is within the limits.

    Args:
      ad_copy: The ad copy to evaluate.
    """

    return (
        self.has_valid_number_of_headlines(ad_copy)
        and self.has_valid_number_of_descriptions(ad_copy)
        and self.has_valid_headline_lengths(ad_copy)
        and self.has_valid_description_lengths(ad_copy)
        and self.has_unique_headlines(ad_copy)
        and self.has_unique_descriptions(ad_copy)
    )

  def has_unfillable_google_ads_special_variables(
      self, ad_copy: GoogleAd
  ) -> bool:
    """Returns true if the ad contains special variables that cannot be filled.

    Special variables are things like Dynamic Keyword Insertion (DKI) and
    Customizers, and they are always filled with their default if possible
    before being sent to Copycat.

    If a special variable cant be filled because it doesn't have a default,
    then it will be left as it is. This function checks for this case,
    because these ads should not be sent to Copycat, but will need to be
    handled manually by the user.

    Args:
      ad_copy: The ad copy to evaluate.
    """
    for headline in ad_copy.headlines:
      cleaned_headline = google_ads.parse_google_ads_special_variables(headline)
      unfilled_variables = re.findall(r"({.*?})", cleaned_headline)
      if unfilled_variables:
        return True

    for description in ad_copy.descriptions:
      cleaned_description = google_ads.parse_google_ads_special_variables(
          description
      )
      unfilled_variables = re.findall(r"({.*?})", cleaned_description)
      if unfilled_variables:
        return True

    return False

  def is_complete(self, ad_copy: GoogleAd) -> bool:
    """Returns true if the ad copy is complete.

    A complete ad copy contains the maximum number of headlines and
    descriptions.

    Args:
      ad_copy: The ad copy to evaluate.
    """
    complete_headlines = len(ad_copy.headlines) == self.ad_format.max_headlines
    complete_descriptions = (
        len(ad_copy.descriptions) == self.ad_format.max_descriptions
    )
    return complete_headlines and complete_descriptions

  def is_empty(self, ad_copy: GoogleAd) -> bool:
    """Returns true if the ad copy is empty."""
    return not ad_copy.headlines and not ad_copy.descriptions

  def is_underpopulated(self, ad_copy: GoogleAd) -> bool:
    """Returns true if the ad copy is underpopulated.

    This means the ad copy has fewer than the minimum number of headlines or
    descriptions.

    Args:
      ad_copy: The ad copy to evaluate.
    """
    return (len(ad_copy.headlines) < self.ad_format.min_headlines) or (
        len(ad_copy.descriptions) < self.ad_format.min_descriptions
    )

  def headlines_are_memorised(self, ad_copy: GoogleAd) -> bool:
    """Returns true if all the headlines exist in the training data."""
    if not ad_copy.headlines:
      # There are no headlines, so they cannot be memorised.
      return False

    return not (set(ad_copy.headlines) - self.training_headlines)

  def descriptions_are_memorised(self, ad_copy: GoogleAd) -> bool:
    """Returns true if all the descriptions exist in the training data."""
    if not ad_copy.descriptions:
      # There are no descriptions, so they cannot be memorised.
      return False

    return not (set(ad_copy.descriptions) - self.training_descriptions)

  def calculate_similarity_metrics_batch(
      self,
      *,
      ad_copies: list[GoogleAd],
      keywords: list[str],
  ) -> list[dict[str, float]]:
    """Evaluates the generated ad copies against the training data and keywords.

    This calculates two metrics:
      - The style similarity, which is how similar the style of the generated ad
        is to the style of the training ads. It is calculated as the similarity
        of the generated ad to the most similar training ad.
      - The keyword similarity, which is how similar the generated ad is to the
        keywords.

    The similarity in both cases is calculated using the cosine similarity, and
    normalising it between 0 and 1, so 0 is the least similar and 1 is the most
    similar.

    Args:
      ad_copies: The generated ads.
      keywords: The keywords used to generate the ads.

    Returns:
      A list of dicts containing the style_similarity and keyword_similarity for
      each ad. The dict will be empty if the vectorstore is not provided or
      if the ad has no headlines and descriptions.
    """
    if self.ad_copy_vectorstore is None:
      return [dict()] * len(ad_copies)

    keywords_embeddings = self.ad_copy_vectorstore.embed_queries(keywords)
    ad_embeddings = self.ad_copy_vectorstore.embed_documents(
        list(map(str, ad_copies))
    )

    _, similar_training_ads_embeddings = (
        self.ad_copy_vectorstore.get_relevant_ads_and_embeddings_from_embeddings(
            ad_embeddings, k=1
        )
    )
    most_similar_training_ads_embeddings = [
        similar_embeddings[0]
        for similar_embeddings in similar_training_ads_embeddings
    ]

    similarity_metrics = []
    for (
        keywords_embedding,
        ad_embedding,
        ad_copy,
        most_similar_training_ad_embeddings,
    ) in zip(
        keywords_embeddings,
        ad_embeddings,
        ad_copies,
        most_similar_training_ads_embeddings,
    ):
      if self.is_empty(ad_copy):
        similarity_metrics.append(dict())
        continue

      keyword_similarity = _normalized_cosine_similarity(
          keywords_embedding, ad_embedding
      )

      style_similarity = _normalized_cosine_similarity(
          most_similar_training_ad_embeddings, ad_embedding
      )

      similarity_metrics.append({
          "style_similarity": style_similarity,
          "keyword_similarity": keyword_similarity,
      })

    return similarity_metrics

  def _evaluate_simple_metrics(
      self,
      ad_copy: GoogleAd,
      *,
      allow_memorised_headlines: bool = False,
      allow_memorised_descriptions: bool = False,
  ) -> EvaluationResults:
    """Evaluates the generated ad copy.

    This checks that the number of headlines and descriptions is within the
    limits for the ad format, the headlines and descriptions are unique, and
    that the length of each headline and description is within the limits.

    Args:
      ad_copy: The ad copy to evaluate.
      allow_memorised_headlines: Whether to allow the headlines to be memorised.
      allow_memorised_descriptions: Whether to allow the descriptions to be
        memorised.

    Returns:
      The evaluation results for the ad copy.
    """
    errors = []
    warnings = []

    if not self.has_valid_number_of_headlines(ad_copy):
      errors.append("Invalid number of headlines for the ad format.")
    if not self.has_valid_number_of_descriptions(ad_copy):
      errors.append("Invalid number of descriptions for the ad format.")
    if not self.has_valid_headline_lengths(ad_copy):
      errors.append("At least one headline too long for the ad format.")
    if not self.has_valid_description_lengths(ad_copy):
      errors.append("At least one description too long for the ad format.")
    if not self.has_unique_headlines(ad_copy):
      errors.append("Duplicate headlines found.")
    if not self.has_unique_descriptions(ad_copy):
      errors.append("Duplicate descriptions found.")

    headlines_are_memorised = self.headlines_are_memorised(ad_copy)
    descriptions_are_memorised = self.descriptions_are_memorised(ad_copy)

    if headlines_are_memorised:
      if allow_memorised_headlines:
        warnings.append("All headlines are memorised from the training data.")
      else:
        errors.append("All headlines are memorised from the training data.")
    if descriptions_are_memorised:
      if allow_memorised_descriptions:
        warnings.append(
            "All descriptions are memorised from the training data."
        )
      else:
        errors.append("All descriptions are memorised from the training data.")

    return EvaluationResults(
        errors=errors,
        warnings=warnings,
        headlines_are_memorised=headlines_are_memorised,
        descriptions_are_memorised=descriptions_are_memorised,
        style_similarity=None,
        keyword_similarity=None,
    )

  def evaluate_batch(
      self,
      ad_copies: list[GoogleAd],
      *,
      allow_memorised_headlines: bool = False,
      allow_memorised_descriptions: bool = False,
      keywords: list[str] | None = None,
  ) -> list[EvaluationResults]:
    """Evaluates the generated ad copies.

    Args:
      ad_copies: The generated ads.
      allow_memorised_headlines: Whether to allow the headlines to be memorised.
      allow_memorised_descriptions: Whether to allow the descriptions to be
        memorised.
      keywords: The list of keywords used to generate the ads. Only required for
        the style and keyword similarity metrics. If not provided, these metrics
        will be None.

    Returns:
      The list of evaluation results for each ad.
    """

    results = [
        self._evaluate_simple_metrics(
            ad_copy=ad_copy,
            allow_memorised_headlines=allow_memorised_headlines,
            allow_memorised_descriptions=allow_memorised_descriptions,
        )
        for ad_copy in ad_copies
    ]

    if keywords is None:
      return results

    similarity_metrics = self.calculate_similarity_metrics_batch(
        ad_copies=ad_copies, keywords=keywords
    )

    results = [
        results_i.model_copy(
            update=dict(
                style_similarity=similarity_metrics_i.get("style_similarity"),
                keyword_similarity=similarity_metrics_i.get(
                    "keyword_similarity"
                ),
            )
        )
        for results_i, similarity_metrics_i in zip(results, similarity_metrics)
    ]
    return results
