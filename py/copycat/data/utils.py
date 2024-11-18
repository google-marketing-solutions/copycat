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

"""Utility functions for working with data."""

import itertools
import logging
from typing import Any, Callable, Generator

import numpy as np
import pandas as pd


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


def collapse_headlines_and_descriptions(
    data: pd.DataFrame,
) -> pd.DataFrame:
  """Collapses headline and description columns into two new columns.

  Assumes that the headline and description column names have the format
  "Headline {i}" and "Description {i}", where {i} is the headline number, with
  a single headline or description per column.

  Then collapses them into two new columns, "headlines" and "descriptions",
  containing lists of headlines and descriptions respectively.

  Args:
    data: The input DataFrame.

  Returns:
    A new DataFrame with the headline and description columns collapsed into two
    new columns, "headlines" and "descriptions".
  """
  output_data = data.copy()

  headline_cols = [
      c
      for c in output_data.columns
      if c.startswith("Headline ")
      and c.split(" ")[1].isdigit()
      and len(c.split(" ")) == 2
  ]
  description_cols = [
      c
      for c in output_data.columns
      if c.startswith("Description ")
      and c.split(" ")[1].isdigit()
      and len(c.split(" ")) == 2
  ]
  output_data["headlines"] = pd.Series(
      {
          k: list(
              filter(lambda x: x != "--" and x, v),
          )
          for k, v in output_data[headline_cols].T.to_dict("list").items()
      },
      index=output_data.index,
  )
  output_data["descriptions"] = pd.Series(
      {
          k: list(filter(lambda x: x != "--" and x, v))
          for k, v in output_data[description_cols].T.to_dict("list").items()
      },
      index=output_data.index,
  )

  output_data = output_data.drop(columns=headline_cols + description_cols)

  return output_data


def _explode_to_columns(
    output_name: str, max_columns: int | None = None
) -> Callable[[list[Any]], pd.Series]:
  """Returns a function that explodes a list into a Series of columns.

  The returned function takes a list as input and returns a Series where each
  element of the list is assigned to a separate column, with the column names
  having the format f"{output_name} {i}", where i is the index of the element
  in the list and starts at 1.

  Args:
    output_name: The name of the output columns.
    max_columns: The maximum number of columns to create. If None, then the
      number of columns will be equal to the length of the input list.

  Returns:
    A function that explodes a list into a Series of columns.

  Raises:
    ValueError: If the input to the function is not a list or if the length of
    the list is greater than the maximum number of columns.
  """

  def apply_explode_to_columns(list_col: list[Any]) -> pd.Series:
    nonlocal max_columns
    nonlocal output_name
    if max_columns is None:
      max_columns = len(list_col)
    elif len(list_col) > max_columns:
      raise ValueError(
          "The input to the explode_to_columns function must be a list of"
          f" length {max_columns} or less, got {len(list_col)} instead."
      )

    if not isinstance(list_col, list):
      raise ValueError(
          "The input to the explode_to_columns function must be a list, got"
          f" {type(list_col)} instead."
      )
    return pd.Series(
        list_col + ["--" for _ in range(max_columns - len(list_col))],
        index=[f"{output_name} {i+1}" for i in range(max_columns)],
    )

  return apply_explode_to_columns


def explode_headlines_and_descriptions(
    data: pd.DataFrame,
    max_headlines: int | None = None,
    max_descriptions: int | None = None,
) -> pd.DataFrame:
  """Explodes headline and description columns into separate columns.

  Assumes that the headline and description columns have been collapsed into two
  new columns, "headlines" and "descriptions", containing lists of headlines and
  descriptions respectively.

  Then explodes them into separate columns, with the column names having the
  format "Headline {i}" and "Description {i}", where {i} is the index of the
  headline or description and starts at 1.

  Args:
    data: The input DataFrame.
    max_headlines: The maximum number of headlines to explode. If None, then the
      number of headlines will be equal to the length of the input list.
    max_descriptions: The maximum number of descriptions to explode. If None,
      then the number of descriptions will be equal to the length of the input
      list.

  Returns:
    A new DataFrame with the headline and description columns exploded into
    separate columns.

  Raises:
    ValueError: If the index of the input data is not unique.
  """
  if not data.index.is_unique:
    raise ValueError(
        "The index of the input data is not unique, cannot explode headlines"
        " and descriptions."
    )

  if "headlines" in data:
    headlines = (
        data["headlines"]
        .apply(_explode_to_columns("Headline", max_headlines))
        .fillna("--")
    )
  elif max_headlines is not None:
    headlines = data.apply(
        lambda x: _explode_to_columns("Headline", max_headlines)([]), axis=1
    ).fillna("--")
  else:
    headlines = pd.DataFrame()

  if "descriptions" in data:
    descriptions = (
        data["descriptions"]
        .apply(_explode_to_columns("Description", max_descriptions))
        .fillna("--")
    )
  elif max_descriptions is not None:
    descriptions = data.apply(
        lambda x: _explode_to_columns("Description", max_descriptions)([]),
        axis=1,
    ).fillna("--")
  else:
    descriptions = pd.DataFrame()

  output_data = (
      data.copy()
      .drop(columns=["headlines", "descriptions"])
      .merge(headlines, left_index=True, right_index=True)
      .merge(descriptions, left_index=True, right_index=True)
  )

  return output_data


def iterate_over_batches(
    data: pd.DataFrame, batch_size: int, limit_rows: int | None = None
) -> Generator[pd.DataFrame, None, None]:
  """Iterates over batches of data.

  Args:
    data: The input DataFrame.
    batch_size: The size of each batch.
    limit_rows: The maximum number of rows to iterate over. If None, all rows
      will be iterated over.

  Yields:
    A generator that yields batches of data.
  """
  if limit_rows is None or limit_rows > len(data):
    limit_rows = len(data)

  n_regular_batches = limit_rows // batch_size
  final_batch_size = limit_rows % batch_size

  for i in range(n_regular_batches):
    yield data.iloc[i * batch_size : (i + 1) * batch_size]

  if final_batch_size:
    yield data.iloc[
        n_regular_batches * batch_size : n_regular_batches * batch_size
        + final_batch_size
    ]


def _join_additional_instructions_data(
    additional_instructions_data: pd.DataFrame,
    target_data: pd.DataFrame,
    additional_instructions_column: str,
) -> pd.DataFrame:
  """Prepares the additional instructions data for merging.

  The additional instructions are joined onto the target data on the join
  columns. If the value of a join column in the additional instructions data is
  set to __ALL__, then it will be merged with all values of that column in the
  target data. If there are duplicates in the additional instructions data then
  they are joined together on separate lines.

  Args:
    additional_instructions_data: The additional instructions data.
    target_data: The target data to join the additional instructions data to.
    additional_instructions_column: The column in the additional instructions
      data that contains the additional instructions.

  Returns:
    A new DataFrame with the additional instructions data joined onto the target
    data.
  """
  join_columns = list(additional_instructions_data.index.names)
  complete_index = target_data.reset_index()[join_columns].copy()
  additional_instructions_data = additional_instructions_data.reset_index()

  exploded_additional_instructions = []
  for n_join_columns in range(len(join_columns) + 1):
    for selected_join_columns in itertools.combinations(
        join_columns, n_join_columns
    ):
      selected_join_columns = list(selected_join_columns)
      unselected_join_columns = [
          col for col in join_columns if col not in selected_join_columns
      ]
      mask = np.array([True] * len(additional_instructions_data))
      if selected_join_columns:
        mask &= np.all(
            additional_instructions_data[selected_join_columns].values
            != "__ALL__",
            axis=1,
        )
      if unselected_join_columns:
        mask &= np.all(
            additional_instructions_data[unselected_join_columns].values
            == "__ALL__",
            axis=1,
        )

      if not mask.any():
        continue

      data_to_merge = additional_instructions_data.loc[
          mask, selected_join_columns + [additional_instructions_column]
      ]
      if selected_join_columns:
        exploded_additional_instructions.append(
            complete_index.merge(
                data_to_merge,
                on=selected_join_columns,
                how="inner",
            )
        )
      else:
        exploded_additional_instructions.append(
            complete_index.merge(
                data_to_merge,
                how="cross",
            )
        )

  final_additional_instructions = (
      pd.concat(exploded_additional_instructions)
      .groupby(join_columns)
      .agg(
          additional_instructions=(
              additional_instructions_column,
              lambda x: "\n".join(sorted(list(set(x)))),
          )
      )
  )
  merged_data = target_data.join(
      final_additional_instructions,
      how="left",
  )
  merged_data["additional_instructions"] = merged_data[
      "additional_instructions"
  ].fillna("")
  return merged_data


def construct_generation_data(
    *,
    new_keywords_data: pd.DataFrame,
    additional_instructions_data: pd.DataFrame | None = None,
    existing_generations_data: pd.DataFrame | None = None,
    keyword_column: str = "keyword",
    additional_instructions_column: str = "additional_instructions",
    existing_headlines_column: str = "existing_headlines",
    existing_descriptions_column: str = "existing_descriptions",
    version_column: str = "version",
    n_versions: int = 1,
) -> pd.DataFrame:
  """Constructs the generation data.

  The new keywords data should contain the following columns:
    - The columns in the index_columns list.
    - The column specified by the keyword_column, containing a single keyword
      per row.

  (Optionl) The additional instructions data should contain the following
  columns:
    - The columns in the index_columns list.
    - The column specified by the version_column, containing the version number
    of the ad.
    - The column specified by the additional_instructions_column, containing a
      single additional instruction per row.
  For the additional instructions data, if any of the values of the index
  columns or the version column is set to __ALL__, then it will be merged with
  all values of those columns in the target data.

  (Optional) The existing generations data should contain the following columns:
    - The columns in the index_columns list.
    - The column specified by the version_column, containing the version number
    of the ad.
    - The column specified by the existing_headlines_column, containing a list
      of previously generated headlines.
    - The column specified by the existing_descriptions_column, containing a
      list of previously generated descriptions.
  For the existing generations data, the index and versions columns must be
  unique.

  Args:
    new_keywords_data: The new keywords data.
    additional_instructions_data: The additional instructions data.
    existing_generations_data: The existing generations data.
    keyword_column: The column in the new keywords data that contains the
      keywords.
    additional_instructions_column: The column in the additional instructions
      data that contains the additional instructions.
    existing_headlines_column: The column in the existing generations data that
      contains the existing headlines.
    existing_descriptions_column: The column in the existing generations data
      that contains the existing descriptions.
    version_column: The column in the additional instructions data and the
      existing generations data that contains the version number of the ad.
    n_versions: The number of versions to generate for each new ad.

  Returns:
    A new DataFrame with the generation data.

  Raises:
    ValueError: If the index columns are not unique in the existing generations
    data.
  """
  index_columns = list(new_keywords_data.index.names)
  join_columns = index_columns + [version_column]

  generation_data = (
      new_keywords_data.reset_index()
      .groupby(index_columns)
      .agg(keywords=(keyword_column, ", ".join))
      .reset_index()
  )
  generation_data[version_column] = [list(range(1, n_versions + 1))] * len(
      generation_data
  )

  generation_data = generation_data.explode(version_column, ignore_index=True)
  generation_data[version_column] = generation_data[version_column].astype(str)
  generation_data.set_index(join_columns, inplace=True)

  if (
      existing_generations_data is not None
      and len(existing_generations_data) > 0
  ):
    if set(existing_generations_data.index.names) != set(join_columns):
      error_message = (
          "The index columns of the existing_generations_data do not match the"
          f" expected columns, expected: {join_columns}, got:"
          f" {existing_generations_data.index.names}"
      )
      LOGGER.error(error_message)
      raise ValueError(error_message)

    if not existing_generations_data.index.is_unique:
      error_message = (
          "The index columns of the existing_generations_data are not unique,"
          " cannot merge with the new keywords data."
      )
      LOGGER.error(error_message)
      raise ValueError(error_message)

    generation_data = generation_data.join(
        existing_generations_data[
            [existing_headlines_column, existing_descriptions_column]
        ],
        how="left",
    ).rename(
        columns={
            existing_headlines_column: "existing_headlines",
            existing_descriptions_column: "existing_descriptions",
        }
    )
    generation_data[["existing_headlines", "existing_descriptions"]] = (
        generation_data[["existing_headlines", "existing_descriptions"]]
        .fillna("")
        .map(list)
    )
  else:
    generation_data["existing_headlines"] = ""
    generation_data["existing_descriptions"] = ""
    generation_data[["existing_headlines", "existing_descriptions"]] = (
        generation_data[["existing_headlines", "existing_descriptions"]].map(
            list
        )
    )

  if (
      additional_instructions_data is not None
      and len(additional_instructions_data) > 0
  ):
    if set(additional_instructions_data.index.names) != set(join_columns):
      error_message = (
          "The index columns of the additional_instructions_data do not match"
          f" the expected columns, expected: {join_columns}, got:"
          f" {additional_instructions_data.index.names}"
      )
      LOGGER.error(error_message)
      raise ValueError(error_message)

    generation_data = _join_additional_instructions_data(
        additional_instructions_data=additional_instructions_data[
            [additional_instructions_column]
        ],
        target_data=generation_data,
        additional_instructions_column=additional_instructions_column,
    )
  else:
    generation_data["additional_instructions"] = ""

  return generation_data


def explode_generated_ad_object(
    data: pd.DataFrame,
    *,
    generated_ad_object_column="generated_ad_object",
    headlines_column="headlines",
    descriptions_column="descriptions",
    success_column="Success",
    headlines_are_memorised_column="Headlines are Memorized",
    descriptions_are_memorised_column="Descriptions are Memorized",
    style_similarity_column="Style Similarity",
    keyword_similarity_column="Keyword Similarity",
    warning_message_column="Warnings",
    error_message_column="Errors",
):
  """Explodes the generated_ad_object column into separate columns.

  Args:
    data: The input DataFrame.
    generated_ad_object_column: The column in the data that contains the
      generated ad objects.
    headlines_column: The name of the column to store the headlines.
    descriptions_column: The name of the column to store the descriptions.
    success_column: The name of the column to store whether the generation was
      successful.
    headlines_are_memorised_column: The name of the column to store whether the
      headlines are memorized.
    descriptions_are_memorised_column: The name of the column to store whether
      the descriptions are memorized.
    style_similarity_column: The name of the column to store the style
      similarity.
    keyword_similarity_column: The name of the column to store the keyword
      similarity.
    warning_message_column: The name of the column to store the warning
      messages.
    error_message_column: The name of the column to store the error messages.

  Returns:
    A new DataFrame with the generated_ad_object column exploded into separate
    columns.
  """
  data = data.copy()
  data[headlines_column] = data[generated_ad_object_column].apply(
      lambda x: x.google_ad.headlines
  )
  data[descriptions_column] = data[generated_ad_object_column].apply(
      lambda x: x.google_ad.descriptions
  )
  data[success_column] = data[generated_ad_object_column].apply(
      lambda x: x.success
  )
  data[headlines_are_memorised_column] = data[generated_ad_object_column].apply(
      lambda x: x.evaluation_results.headlines_are_memorised
  )
  data[descriptions_are_memorised_column] = data[
      generated_ad_object_column
  ].apply(lambda x: x.evaluation_results.descriptions_are_memorised)
  data[style_similarity_column] = data[generated_ad_object_column].apply(
      lambda x: x.evaluation_results.style_similarity
  )
  data[keyword_similarity_column] = data[generated_ad_object_column].apply(
      lambda x: x.evaluation_results.keyword_similarity
  )
  data[warning_message_column] = data[generated_ad_object_column].apply(
      lambda x: x.warning_message
  )
  data[error_message_column] = data[generated_ad_object_column].apply(
      lambda x: x.error_message
  )

  return data
