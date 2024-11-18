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

"""A collection of re-usable event handlers for the Copycat UI."""

import dataclasses
import json
import logging

import vertexai
import mesop as me
import pandas as pd

from copycat import copycat
from copycat.data import sheets
from copycat.data import utils as data_utils
from copycat.ui import states


def update_copycat_parameter(event: me.InputEvent) -> None:
  """Updates a parameter in the CopycatParamsState.

  Args:
    event: The input event to handle. This can be any event where the key is
      set.

  Raises:
    ValueError: If the key is not a field in CopycatParamsState.
  """
  params = me.state(states.CopycatParamsState)
  for field in dataclasses.fields(params):
    if field.name == event.key:
      setattr(params, event.key, field.type(event.value))
      return
  raise ValueError(f"Field {event.key} does not exist in CopycatParamsState.")


def update_app_state_parameter(event: me.InputEvent) -> None:
  """Updates a parameter in the AppState.

  Args:
    event: The input event to handle. This can be any event where the key is
      set.

  Raises:
    ValueError: If the key is not a field in AppState.
  """
  state = me.state(states.AppState)
  for field in dataclasses.fields(state):
    if field.name == event.key:
      setattr(state, event.key, field.type(event.value))
      return
  raise ValueError(f"Field {event.key} does not exist in AppState.")


def update_copycat_parameter_from_slide_toggle(
    event: me.SlideToggleChangeEvent,
) -> None:
  """Updates a copycat parameter from a slide toggle change event.

  Args:
    event: The slide toggle change event to handle.
  """
  state = me.state(states.CopycatParamsState)
  setattr(state, event.key, not getattr(state, event.key))


def update_app_state_parameter_checkbox(
    event: me.CheckboxChangeEvent,
) -> None:
  """Updates a app state parameter from a checkbox change event.

  Args:
    event: The checkbox change event to handle.
  """
  state = me.state(states.AppState)
  setattr(state, event.key, not getattr(state, event.key))


def language_on_blur(event: me.InputBlurEvent) -> None:
  """Updates the language and the embedding model name based on the language.

  Args:
    event: The input blur event to handle.
  """
  state = me.state(states.CopycatParamsState)
  state.language = event.value

  if "english" in event.value.lower():
    state.embedding_model_name = copycat.EmbeddingModelName.TEXT_EMBEDDING.value
  else:
    state.embedding_model_name = (
        copycat.EmbeddingModelName.TEXT_MULTILINGUAL_EMBEDDING.value
    )

  send_log(
      f"Updating embedding model name to {state.embedding_model_name} for"
      f" language = {state.language}"
  )


def ad_format_on_change(event: me.RadioChangeEvent) -> None:
  """Updates the ad format and related parameters in the CopycatParamsState.

  Args:
    event: The radio change event to handle.
  """
  state = me.state(states.CopycatParamsState)
  state.ad_format = event.value

  if state.ad_format != "custom":
    send_log(
        f"Updating max headlines and descriptions for {state.ad_format} ad"
        " format"
    )
    ad_format = copycat.google_ads.get_google_ad_format(event.value)
    state.max_headlines = ad_format.max_headlines
    state.max_descriptions = ad_format.max_descriptions
  else:
    send_log(
        f"Max headlines and descriptions not updated for {state.ad_format} ad"
        " format"
    )


def embedding_model_dimensionality_on_blur(event: me.InputBlurEvent) -> None:
  """Updates the embedding model dimensionality based on the input value.

  The value is clamped to the range [10, 768].

  Args:
    event: The input blur event to handle.
  """
  state = me.state(states.CopycatParamsState)
  raw_value = int(event.value)
  if raw_value > 786:
    state.embedding_model_dimensionality = 768
  elif raw_value < 10:
    state.embedding_model_dimensionality = 10
  else:
    state.embedding_model_dimensionality = raw_value


def close_starting_dialog(event: me.ClickEvent) -> None:
  """Closes the starting dialog.

  This clears the new Google Sheet URL and name, and sets the
  show_starting_dialog state to False.

  Args:
    event: The click event to handle.
  """
  state = me.state(states.AppState)
  state.new_google_sheet_url = ""
  state.new_google_sheet_name = ""
  state.show_starting_dialog = False


def open_starting_dialog(event: me.ClickEvent) -> None:
  """Opens the starting dialog by setting show_starting_dialog to True.

  Args:
    event: The click event to handle.
  """
  state = me.state(states.AppState)
  state.show_starting_dialog = True


def reset_state(
    state: type[states.AppState] | type[states.CopycatParamsState],
) -> None:
  """Resets a state to its default values.

  Args:
    state: The state to reset.
  """
  send_log(f"Resetting state: {state}")
  params = me.state(state)

  for field in dataclasses.fields(params):
    if field.default is not dataclasses.MISSING:
      setattr(params, field.name, field.default)
    elif field.default_factory is not dataclasses.MISSING:
      setattr(params, field.name, field.default_factory())
    else:
      setattr(params, field.name, field.type())


def save_params_to_google_sheet(event: me.ClickEvent) -> None:
  """Saves the Copycat parameters to the Google Sheet.

  The parameters are written to a tab named "READ ONLY: Copycat Params".

  Args:
    event: The click event to handle.
  """
  state = me.state(states.AppState)
  params = me.state(states.CopycatParamsState)

  params_table = pd.DataFrame([dataclasses.asdict(params)])
  params_table["Parameter Name"] = "Parameter Value"
  params_table = params_table.set_index("Parameter Name")

  sheet = sheets.GoogleSheet.load(state.google_sheet_url)
  sheet["READ ONLY: Copycat Params"] = params_table

  send_log("Copycat params saved to sheet")


def load_params_from_google_sheet(event: me.ClickEvent) -> None:
  """Loads the Copycat parameters from the Google Sheet.

  The parameters are read from a tab named "READ ONLY: Copycat Params".

  Args:
    event: The click event to handle.
  """
  state = me.state(states.AppState)
  params = me.state(states.CopycatParamsState)

  sheet = sheets.GoogleSheet.load(state.google_sheet_url)
  params_table = sheet["READ ONLY: Copycat Params"]

  for field in dataclasses.fields(params):
    if field.name in params_table:
      param_value = params_table[field.name].values[0]
      if field.type is bool and param_value == "TRUE":
        param_value = True
      elif field.type is bool and param_value == "FALSE":
        param_value = False
      else:
        param_value = field.type(param_value)
      setattr(params, field.name, param_value)

  state.has_copycat_instance = "READ ONLY: Copycat Instance Params" in sheet
  send_log("Loaded Copycat params from sheet")


def create_new_google_sheet(event: me.ClickEvent) -> None:
  """Creates a new Google Sheet and initializes it with the default tabs.

  The default tabs are:
    - Training Ads
    - New Keywords
    - Extra Instructions for New Ads

  Args:
    event: The click event to handle.
  """
  state = me.state(states.AppState)
  new_sheet_url = sheets.create_template_copycat_sheet(
      state.new_google_sheet_name, state.new_google_sheet_include_demo_data
  )
  start_logger(new_sheet_url)
  send_log(
      f"Created new Google Sheet: {state.new_google_sheet_name}. Include demo"
      f" data: {state.new_google_sheet_include_demo_data}."
  )

  reset_state(states.AppState)
  reset_state(states.CopycatParamsState)
  state = me.state(states.AppState)

  sheet = sheets.GoogleSheet.load(new_sheet_url)
  state.google_sheet_url = sheet.url
  state.google_sheet_name = sheet.title
  save_params_to_google_sheet(event)
  close_starting_dialog(event)
  send_log("New Google Sheet created")


def load_existing_google_sheet(event: me.ClickEvent) -> None:
  """Loads an existing Google Sheet.

  The sheet should contain the following tabs:
    - Training Ads
    - New Keywords
    - Extra Instructions for New Ads

  Args:
    event: The click event to handle.
  """
  state = me.state(states.AppState)
  sheet = sheets.GoogleSheet.load(state.new_google_sheet_url)
  start_logger(sheet.url)

  reset_state(states.AppState)
  reset_state(states.CopycatParamsState)
  state = me.state(states.AppState)

  # Load sheet
  state.google_sheet_url = sheet.url
  state.google_sheet_name = sheet.title

  if "READ ONLY: Copycat Params" in sheet:
    load_params_from_google_sheet(event)
  else:
    save_params_to_google_sheet(event)

  close_starting_dialog(event)
  send_log("Existing Google Sheet loaded")


def start_logger(url: str) -> None:
  """Starts the logger and writes logs to a Google Sheet.

  Args:
    url: The URL of the Google Sheet to write logs to.
  """
  handler = sheets.GoogleSheetsHandler(sheet_url=url, log_worksheet_name="Logs")
  handler.setLevel(logging.INFO)


  logger = logging.getLogger("copycat")
  logger.handlers = []
  logger.addHandler(handler)
  logger.setLevel(logging.INFO)
  logger.info("Logger Started")


def send_log(message: str, level: int = logging.INFO) -> None:
  """Sends a log message to the logger.

  Args:
    message: The log message to send.
    level: The level of the log message. Defaults to INFO.
  """
  logger = logging.getLogger("copycat.ui")
  logger.log(level=level, msg=message)


def update_log_level(event: me.SelectSelectionChangeEvent) -> None:
  """Updates the log level of the logger.

  Args:
    event: The select selection change event to handle.
  """
  state = me.state(states.AppState)
  state.log_level = int(event.value)

  loggers = [
      logging.getLogger(name) for name in logging.root.manager.loggerDict
  ]
  for logger in loggers:
    if "copycat" in logger.name:
      logger.setLevel(state.log_level)
      for handler in logger.handlers:
        if isinstance(handler, sheets.GoogleSheetsHandler):
          handler.setLevel(state.log_level)


def show_hide_google_sheet(event: me.ClickEvent) -> None:
  """Shows or hides the Google Sheet preview panel.

  Args:
    event: The click event to handle.
  """
  state = me.state(states.AppState)
  state.display_google_sheet = not state.display_google_sheet


def on_click_snackbar_close(event: me.ClickEvent):
  state = me.state(states.AppState)
  setattr(state, event.key, False)


def validate_sheet(event: me.ClickEvent) -> None:
  """Validates the Google Sheet.

  The sheet is validated by checking that it contains the required tabs,
  index columns, and columns, and that it has the minimum number of rows.

  Args:
    event: The click event to handle.
  """
  state = me.state(states.AppState)
  sheet_url = state.google_sheet_url
  send_log(f"Validating {sheet_url}")

  sheet = sheets.GoogleSheet.load(sheet_url)
  send_log(f"Sheet Name = {sheet.title}")

  # Validate all required sheets exist, have the correct index and columns,
  # and have the minimum number of rows.
  required_index_names = {
      sheets.TEMPLATE_EXISTING_ADS_WORKSHEET_NAME: ["Campaign ID", "Ad Group"],
      sheets.TEMPLATE_NEW_KEYWORDS_WORKSHEET_NAME: ["Campaign ID", "Ad Group"],
      sheets.TEMPLATE_EXTRA_INSTRUCTIONS_WORKSHEET_NAME: [
          "Campaign ID",
          "Ad Group",
          "Version",
      ],
  }
  required_columns = {
      sheets.TEMPLATE_EXISTING_ADS_WORKSHEET_NAME: set([
          "URL",
          "Ad Strength",
          "Keywords",
          "Headline 1",
          "Description 1",
      ]),
      sheets.TEMPLATE_NEW_KEYWORDS_WORKSHEET_NAME: set([
          "Keyword",
      ]),
      sheets.TEMPLATE_EXTRA_INSTRUCTIONS_WORKSHEET_NAME: set([
          "Extra Instructions",
      ]),
  }
  min_rows = {
      sheets.TEMPLATE_EXISTING_ADS_WORKSHEET_NAME: 1,
      sheets.TEMPLATE_NEW_KEYWORDS_WORKSHEET_NAME: 1,
      sheets.TEMPLATE_EXTRA_INSTRUCTIONS_WORKSHEET_NAME: 0,
  }

  state.google_sheet_is_valid = True
  for sheet_name in required_columns:
    if sheet_name in sheet:
      send_log(f"{sheet_name} sheet found")
    else:
      send_log(
          f"VALIDATION FAILED: {sheet_name} sheet not found.", logging.ERROR
      )
      state.google_sheet_is_valid = False
      continue

    worksheet = sheet[sheet_name]
    actual_index_names = list(worksheet.index.names)
    if required_index_names[sheet_name] != actual_index_names:
      send_log(
          f"VALIDATION FAILED: {sheet_name} requires index columns:"
          f" {required_index_names[sheet_name]}, but found"
          f" {actual_index_names}.",
          logging.ERROR,
      )
      state.google_sheet_is_valid = False

    actual_columns = set(worksheet.columns.values.tolist())
    extra_columns = actual_columns - required_columns[sheet_name]
    missing_columns = required_columns[sheet_name] - actual_columns

    if missing_columns:
      send_log(
          f"VALIDATION FAILED: Missing columns in {sheet_name}:"
          f" {missing_columns}",
          logging.ERROR,
      )
      state.google_sheet_is_valid = False
    else:
      send_log(f"All required columns in {sheet_name}")

    if extra_columns:
      send_log(f"{sheet_name} has the following extra columns: {extra_columns}")

    n_rows = len(worksheet)
    if n_rows < min_rows[sheet_name]:
      send_log(
          f"VALIDATION FAILED: {sheet_name} sheet has fewer than the minimum"
          f" number of rows: min={min_rows[sheet_name]}.",
          logging.ERROR,
      )
      state.google_sheet_is_valid = False
    else:
      send_log(f"{sheet_name} has {n_rows:,} rows")

  # Log the number of headline and description columns in the training ads
  training_ads = sheet["Training Ads"]
  n_headline_columns = len(
      [c for c in training_ads.columns if c.startswith("Headline")]
  )
  n_description_columns = len(
      [c for c in training_ads.columns if c.startswith("Description")]
  )
  send_log(f"Training Ads have up to {n_headline_columns} headlines.")
  send_log(f"Training Ads have up to {n_description_columns} descriptions.")

  # Completed validation
  if state.google_sheet_is_valid:
    send_log("VALIDATION COMPLETED: Google Sheet is valid")
  else:
    send_log("VALIDATION COMPLETED: Google Sheet is invalid", logging.ERROR)


def save_copycat_to_sheet(
    sheet: sheets.GoogleSheet, model: copycat.Copycat
) -> None:
  """Saves the Copycat model to the Google Sheet.

  The model is saved in two tabs:
    - READ ONLY: Training Ad Exemplars: Contains the exemplar ads.
    - READ ONLY: Copycat Instance Params: Contains the other model parameters.

  Args:
    sheet: The Google Sheet to save the model to.
    model: The Copycat model to save.
  """
  send_log("Saving Copycat instance to sheet")
  model_params = model.to_dict()

  # Store the exemplar ads in their own sheet
  exemplars_dict = model_params["ad_copy_vectorstore"].pop("ad_exemplars")
  ad_exemplars = pd.DataFrame.from_dict(exemplars_dict, orient="tight")
  ad_exemplars["embeddings"] = ad_exemplars["embeddings"].apply(
      lambda x: ", ".join(list(map(str, x)))
  )
  ad_exemplars = data_utils.explode_headlines_and_descriptions(ad_exemplars)
  ad_exemplars.index.name = "Exemplar Number"
  sheet["READ ONLY: Training Ad Exemplars"] = ad_exemplars

  # Store the other params as a json string
  other_params = pd.DataFrame([{
      "params_json": json.dumps(model_params),
  }])
  sheet["READ ONLY: Copycat Instance Params"] = other_params


def load_copycat_from_sheet(sheet: sheets.GoogleSheet) -> copycat.Copycat:
  """Loads a Copycat instance from the Google Sheet.

  The instance is loaded from two tabs:
    - READ ONLY: Training Ad Exemplars: Contains the exemplar ads.
    - READ ONLY: Copycat Instance Params: Contains the other model parameters.

  Args:
    sheet: The Google Sheet to load the instance from.

  Returns:
    The Copycat instance.
  """
  send_log("Loading Copycat instance from sheet")
  instance_json = sheet["READ ONLY: Copycat Instance Params"].loc[
      0, "params_json"
  ]
  instance_dict = json.loads(instance_json)

  ad_exemplars = sheet["READ ONLY: Training Ad Exemplars"]
  ad_exemplars["embeddings"] = ad_exemplars["embeddings"].apply(
      lambda x: list(map(float, x.split(", ")))
  )
  ad_exemplars = data_utils.collapse_headlines_and_descriptions(ad_exemplars)
  ad_exemplars_dict = ad_exemplars.to_dict(orient="tight")

  instance_dict["ad_copy_vectorstore"]["ad_exemplars"] = ad_exemplars_dict
  copycat_instance = copycat.Copycat.from_dict(instance_dict)
  return copycat_instance


def build_new_copycat_instance(event: me.ClickEvent):
  """Builds a new Copycat instance from the Google Sheet.

  The Copycat instance is created using the parameters from the Google Sheet
  and the CopycatParamsState. The instance is then saved to the Google Sheet.

  Args:
    event: The click event to handle.
  """
  state = me.state(states.AppState)
  params = me.state(states.CopycatParamsState)
  sheet = sheets.GoogleSheet.load(state.google_sheet_url)
  save_params_to_google_sheet(event)

  vertexai.init(
      project=params.vertex_ai_project_id, location=params.vertex_ai_location
  )

  train_data = data_utils.collapse_headlines_and_descriptions(
      sheet["Training Ads"]
  )
  train_data = train_data.rename({"Keywords": "keywords"}, axis=1)
  train_data = train_data[["headlines", "descriptions", "keywords"]]
  train_data = train_data.loc[train_data["headlines"].apply(len) > 0]

  send_log(f"Loaded {len(train_data)} rows of raw data from the Google Sheet.")

  if params.ad_format == "custom":
    ad_format = copycat.google_ads.GoogleAdFormat(
        name="custom",
        max_headlines=params.max_headlines,
        max_descriptions=params.max_descriptions,
        min_headlines=1,
        min_descriptions=1,
        max_headline_length=30,
        max_description_length=90,
    )
    send_log("Using a custom ad format.")
  else:
    ad_format = copycat.google_ads.get_google_ad_format(params.ad_format)
    send_log(f"Using the following ad format: {ad_format.name}")

  affinity_preference = (
      params.custom_affinity_preference
      if params.use_custom_affinity_preference
      else None
  )
  send_log(
      "Affinity preference:"
      f" {affinity_preference} (custom={params.use_custom_affinity_preference})"
  )

  send_log("Creating Copycat.")

  model = copycat.Copycat.create_from_pandas(
      training_data=train_data,
      ad_format=ad_format,
      on_invalid_ad=params.on_invalid_ad,
      embedding_model_name=params.embedding_model_name,
      embedding_model_dimensionality=params.embedding_model_dimensionality,
      embedding_model_batch_size=params.embedding_model_batch_size,
      vectorstore_exemplar_selection_method=params.exemplar_selection_method,
      vectorstore_max_initial_ads=params.max_initial_ads,
      vectorstore_max_exemplar_ads=params.max_exemplar_ads,
      vectorstore_affinity_preference=affinity_preference,
      replace_special_variables_with_default=params.how_to_handle_special_variables
      == "replace",
  )
  send_log(
      "Copycat instance created with"
      f" {model.ad_copy_vectorstore.n_exemplars} exemplar ads."
  )

  save_copycat_to_sheet(sheet, model)
  state.has_copycat_instance = True

  send_log("Copycat instance stored in google sheet.")
  state.show_copycat_instance_created_snackbar = True


def generate_style_guide(event: me.ClickEvent):
  """Generates a style guide from the Google Sheet.

  The style guide is generated using the parameters from the Google Sheet
  and the CopycatParamsState. The style guide is then saved to the Google Sheet.

  Args:
    event: The click event to handle.
  """
  send_log("Generating style guide")
  state = me.state(states.AppState)
  params = me.state(states.CopycatParamsState)
  sheet = sheets.GoogleSheet.load(state.google_sheet_url)

  vertexai.init(
      project=params.vertex_ai_project_id,
      location=params.vertex_ai_location,
  )

  send_log("Preparing to generate style guide")
  if params.style_guide_files_uri:
    send_log(
        f"Checking for files in the GCP bucket {params.style_guide_files_uri}"
    )

  copycat_instance = load_copycat_from_sheet(sheet)
  params.style_guide = copycat_instance.generate_style_guide(
      company_name=params.company_name,
      additional_style_instructions=params.style_guide_additional_instructions,
      model_name=params.style_guide_chat_model_name,
      safety_settings=copycat.ALL_SAFETY_SETTINGS_ONLY_HIGH,
      temperature=params.style_guide_temperature,
      top_k=params.style_guide_top_k,
      top_p=params.style_guide_top_p,
      use_exemplar_ads=params.style_guide_use_exemplar_ads,
      files_uri=params.style_guide_files_uri,
  )
  send_log("Style guide generated")

  save_params_to_google_sheet(event)


def _prepare_new_ads_for_generation(
    sheet: sheets.GoogleSheet,
    n_versions: int,
    fill_gaps: bool,
    copycat_instance: copycat.Copycat,
) -> tuple[pd.DataFrame, pd.DataFrame]:
  """Prepares new ads for generation.

  This function prepares new ads for generation by loading the data from the
  Google Sheet, constructing the complete data, and filtering out any ads that
  have already been generated.

  Args:
    sheet: The Google Sheet to load the data from.
    n_versions: The number of versions to generate for each ad.
    fill_gaps: Whether to fill gaps in the existing generations.
    copycat_instance: The Copycat instance to use for generation.

  Returns:
    A tuple containing the new generations data and the complete data.
  """
  new_keywords_data = sheet["New Keywords"]
  additional_instructions_data = sheet["Extra Instructions for New Ads"]
  additional_instructions_data.index = (
      additional_instructions_data.index.set_levels(
          additional_instructions_data.index.get_level_values("Version").astype(
              str
          ),
          level="Version",
          verify_integrity=False,
      )
  )

  if "Generated Ads" in sheet:
    existing_generations_data = sheet["Generated Ads"]
    if "Headline 1" not in existing_generations_data.columns:
      existing_generations_data = None
  else:
    existing_generations_data = None

  if existing_generations_data is None:
    complete_data = data_utils.construct_generation_data(
        new_keywords_data=new_keywords_data,
        additional_instructions_data=additional_instructions_data,
        n_versions=n_versions,
        keyword_column="Keyword",
        version_column="Version",
        additional_instructions_column="Extra Instructions",
    )
    complete_data["existing_headlines"] = [[]] * len(complete_data)
    complete_data["existing_descriptions"] = [[]] * len(complete_data)
    new_generations_data = complete_data.copy()
    return new_generations_data, complete_data

  existing_generations_data = data_utils.collapse_headlines_and_descriptions(
      existing_generations_data
  ).rename(
      columns={
          "headlines": "existing_headlines",
          "descriptions": "existing_descriptions",
      }
  )
  existing_generations_data.index = existing_generations_data.index.set_levels(
      existing_generations_data.index.get_level_values("Version").astype(str),
      level="Version",
      verify_integrity=False,
  )

  complete_data = data_utils.construct_generation_data(
      new_keywords_data=new_keywords_data,
      additional_instructions_data=additional_instructions_data,
      existing_generations_data=existing_generations_data,
      n_versions=n_versions,
      existing_headlines_column="existing_headlines",
      existing_descriptions_column="existing_descriptions",
      keyword_column="Keyword",
      version_column="Version",
      additional_instructions_column="Extra Instructions",
  )
  missing_columns = [
      column
      for column in existing_generations_data.columns
      if column not in complete_data.columns
  ]
  if missing_columns:
    complete_data = complete_data.join(
        existing_generations_data[missing_columns],
        how="left",
    )

  generation_not_required = complete_data.index.isin(
      existing_generations_data.index
  )
  if fill_gaps:
    generation_not_required = generation_not_required & complete_data.apply(
        lambda row: copycat_instance.ad_copy_evaluator.is_complete(
            copycat.GoogleAd(
                headlines=row["existing_headlines"],
                descriptions=row["existing_descriptions"],
            )
        ),
        axis=1,
    )
  else:
    generation_not_required = generation_not_required & complete_data.apply(
        lambda row: not copycat_instance.ad_copy_evaluator.is_empty(
            copycat.GoogleAd(
                headlines=row["existing_headlines"],
                descriptions=row["existing_descriptions"],
            )
        ),
        axis=1,
    )

  new_generations_data = complete_data.loc[~generation_not_required].copy()

  return new_generations_data, complete_data


def generate_new_ad_preview(event: me.ClickEvent):
  """Generates a preview of the prompt to be used to generate a new ad.

  The preview is generated using the parameters from the Google Sheet
  and the CopycatParamsState. The preview is then saved to the Google Sheet.

  Args:
    event: The click event to handle.
  """
  state = me.state(states.AppState)
  params = me.state(states.CopycatParamsState)
  sheet = sheets.GoogleSheet.load(state.google_sheet_url)
  copycat_instance = load_copycat_from_sheet(sheet)

  generation_data, complete_data = _prepare_new_ads_for_generation(
      sheet,
      params.new_ads_number_of_versions,
      params.new_ads_fill_gaps,
      copycat_instance,
  )

  if len(generation_data) > 0:
    first_row = generation_data.iloc[0].to_dict()
  elif len(complete_data) > 0:
    send_log(
        "No ads to generate, generating a preview for an existing ad",
        logging.WARNING,
    )
    first_row = complete_data.iloc[0].to_dict()
  else:
    send_log(
        "No new or existing ads to generate, no preview will be generated",
        logging.ERROR,
    )
    return

  vertexai.init(
      project=params.vertex_ai_project_id,
      location=params.vertex_ai_location,
  )

  style_guide = params.style_guide if params.new_ads_use_style_guide else ""
  headlines = (
      [first_row["existing_headlines"]]
      if "existing_headlines" in first_row
      else [[]]
  )
  descriptions = (
      [first_row["existing_descriptions"]]
      if "existing_descriptions" in first_row
      else [[]]
  )

  request = copycat_instance.construct_text_generation_requests_for_new_ad_copy(
      keywords=[first_row["keywords"]],
      keywords_specific_instructions=[first_row["additional_instructions"]],
      system_instruction_kwargs=dict(
          company_name=params.company_name,
          language=params.language,
      ),
      style_guide=style_guide,
      num_in_context_examples=params.new_ads_num_in_context_examples,
      model_name=params.new_ads_chat_model_name,
      temperature=params.new_ads_temperature,
      top_k=params.new_ads_top_k,
      top_p=params.new_ads_top_p,
      safety_settings=copycat.ALL_SAFETY_SETTINGS_ONLY_HIGH,
      existing_headlines=headlines,
      existing_descriptions=descriptions,
  )[0]

  state.new_ad_preview_request = request.to_markdown()
  save_params_to_google_sheet(event)


def generate_ads(event: me.ClickEvent):
  """Generates ads from the Google Sheet.

  The ads are generated using the parameters from the Google Sheet
  and the CopycatParamsState. The ads are then saved to the Google Sheet.

  The ads are generated in batches and the batches are written immediately to
  the Google Sheet once they are generated.

  Args:
    event: The click event to handle.
  """
  state = me.state(states.AppState)
  params = me.state(states.CopycatParamsState)
  sheet = sheets.GoogleSheet.load(state.google_sheet_url)
  copycat_instance = load_copycat_from_sheet(sheet)

  save_params_to_google_sheet(event)

  vertexai.init(
      project=params.vertex_ai_project_id,
      location=params.vertex_ai_location,
  )

  generation_data, complete_data = _prepare_new_ads_for_generation(
      sheet,
      params.new_ads_number_of_versions,
      params.new_ads_fill_gaps,
      copycat_instance,
  )
  updated_complete_data = data_utils.explode_headlines_and_descriptions(
      complete_data.copy().rename(
          columns={
              "existing_headlines": "headlines",
              "existing_descriptions": "descriptions",
          }
      ),
      max_headlines=params.max_headlines,
      max_descriptions=params.max_descriptions,
  )

  send_log("Loaded generation and complete data")

  if len(generation_data) == 0:
    send_log("No ads to generate", logging.WARNING)
    return

  generation_params = dict(
      system_instruction_kwargs=dict(
          company_name=params.company_name,
          language=params.language,
      ),
      num_in_context_examples=params.new_ads_num_in_context_examples,
      model_name=params.new_ads_chat_model_name,
      temperature=params.new_ads_temperature,
      top_k=params.new_ads_top_k,
      top_p=params.new_ads_top_p,
      allow_memorised_headlines=params.new_ads_allow_memorised_headlines,
      allow_memorised_descriptions=params.new_ads_allow_memorised_descriptions,
      safety_settings=copycat.ALL_SAFETY_SETTINGS_ONLY_HIGH,
      style_guide=params.style_guide if params.new_ads_use_style_guide else "",
  )
  limit = params.new_ads_generation_limit
  if limit == 0:
    limit = None
  data_iterator = data_utils.iterate_over_batches(
      generation_data,
      batch_size=params.new_ads_batch_size,
      limit_rows=limit,
  )
  for batch_number, generation_batch in enumerate(data_iterator):
    send_log(f"Generating batch {batch_number+1}")
    generation_batch["generated_ad_object"] = (
        copycat_instance.generate_new_ad_copy_for_dataframe(
            data=generation_batch,
            keywords_specific_instructions_column="additional_instructions",
            **generation_params,
        )
    )
    generation_batch = (
        generation_batch.pipe(data_utils.explode_generated_ad_object)
        .pipe(
            data_utils.explode_headlines_and_descriptions,
            max_headlines=params.max_headlines,
            max_descriptions=params.max_descriptions,
        )
        .drop(
            columns=[
                "generated_ad_object",
                "existing_headlines",
                "existing_descriptions",
            ],
            errors="ignore",
        )
    )

    isin_batch = updated_complete_data.index.isin(generation_batch.index)

    updated_complete_data = updated_complete_data.loc[~isin_batch]
    updated_complete_data = pd.concat([updated_complete_data, generation_batch])
    updated_complete_data = updated_complete_data.fillna("").loc[
        complete_data.index
    ]

    column_order = ["keywords", "additional_instructions"]
    column_order.extend(
        col
        for col in updated_complete_data.columns
        if col.startswith("Headline ")
    )
    column_order.extend(
        col
        for col in updated_complete_data.columns
        if col.startswith("Description ")
    )
    column_order.extend(
        col for col in updated_complete_data.columns if col not in column_order
    )

    sheet["Generated Ads"] = updated_complete_data[column_order]

  send_log("Generation Complete")
  state.show_ad_copy_generated_snackbar = True
