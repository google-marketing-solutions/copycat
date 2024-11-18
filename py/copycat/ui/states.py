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

"""States for the Copycat UI."""
import dataclasses
import logging

import mesop as me

from copycat import ad_copy_generator
from copycat import google_ads


DEFAULT_GCP_PROJECT_ID = ""


def set_default_gcp_project_id(project_id: str) -> None:
  """Sets the default GCP project ID."""
  global DEFAULT_GCP_PROJECT_ID
  DEFAULT_GCP_PROJECT_ID = project_id


@me.stateclass
class AppState:
  highlighted_url: str = "/setup"
  new_google_sheet_name: str = ""
  new_google_sheet_url: str = ""
  new_google_sheet_include_demo_data: bool = True
  google_sheet_name: str = ""
  google_sheet_url: str = ""
  display_google_sheet: bool = False
  show_starting_dialog: bool = True
  google_sheet_is_valid: bool = False
  has_copycat_instance: bool = False
  new_ad_preview_request: str = ""
  log_level: int = logging.INFO
  show_copycat_instance_created_snackbar: bool = False
  show_ad_copy_generated_snackbar: bool = False


@me.stateclass
class CopycatParamsState:
  vertex_ai_project_id: str = dataclasses.field(
      default_factory=lambda: DEFAULT_GCP_PROJECT_ID
  )
  vertex_ai_location: str = "us-central1"

  company_name: str = ""
  ad_format: str = "responsive_search_ad"
  max_headlines: int = google_ads.get_google_ad_format(
      "responsive_search_ad"
  ).max_headlines
  max_descriptions: int = google_ads.get_google_ad_format(
      "responsive_search_ad"
  ).max_descriptions
  language: str = "English"
  embedding_model_name: str = (
      ad_copy_generator.EmbeddingModelName.TEXT_EMBEDDING.value
  )
  how_to_handle_special_variables: str = "replace"
  on_invalid_ad: str = "drop"
  embedding_model_dimensionality: float = 768
  embedding_model_batch_size: int = 50
  max_initial_ads: int = 2000
  max_exemplar_ads: int = 200
  exemplar_selection_method: str = (
      ad_copy_generator.ExemplarSelectionMethod.AFFINITY_PROPAGATION.value
  )
  custom_affinity_preference: float = -0.5
  use_custom_affinity_preference: bool = False
  min_ad_strength: str = "POOR"

  style_guide_chat_model_name: str = (
      ad_copy_generator.ModelName.GEMINI_1_5_PRO.value
  )
  style_guide_temperature: float = 0.95
  style_guide_top_k: int = 40
  style_guide_top_p: float = 0.95
  style_guide_files_uri: str = ""
  style_guide_additional_instructions: str = ""
  style_guide_use_exemplar_ads: bool = True
  style_guide: str = ""
  generated_style_guide: str = ""

  new_ads_use_style_guide: bool = True
  new_ads_num_in_context_examples: int = 5
  new_ads_chat_model_name: str = (
      ad_copy_generator.ModelName.GEMINI_1_5_FLASH.value
  )
  new_ads_temperature: float = 0.95
  new_ads_top_k: int = 40
  new_ads_top_p: float = 0.95
  new_ads_allow_memorised_headlines: bool = False
  new_ads_allow_memorised_descriptions: bool = False
  new_ads_batch_size: int = 15
  new_ads_generation_limit: int = 30
  new_ads_fill_gaps: bool = True
  new_ads_number_of_versions: int = 1
