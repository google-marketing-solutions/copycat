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

"""A python library to generate ad copy that matches an advertisers style."""

from copycat import copycat

Copycat = copycat.Copycat
CopycatResponse = copycat.CopycatResponse
StyleGuideGenerator = copycat.StyleGuideGenerator

GoogleAd = copycat.GoogleAd
GoogleAdFormat = copycat.GoogleAdFormat
ValidationError = copycat.ValidationError
ModelName = copycat.ModelName
EmbeddingModelName = copycat.EmbeddingModelName
TextGenerationRequest = copycat.TextGenerationRequest
ExemplarSelectionMethod = copycat.ExemplarSelectionMethod
EvaluationResults = copycat.EvaluationResults
BirchAgglomerativeKeywordClusterer = copycat.BirchAgglomerativeKeywordClusterer

HarmCategory = copycat.generative_models.HarmCategory
HarmBlockThreshold = copycat.generative_models.HarmBlockThreshold
ALL_SAFETY_SETTINGS_OFF = copycat.ALL_SAFETY_SETTINGS_OFF
ALL_SAFETY_SETTINGS_ONLY_HIGH = copycat.ALL_SAFETY_SETTINGS_ONLY_HIGH


__version__ = "0.0.1"
