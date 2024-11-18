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

try:
  from copycat.ui import main
  from copycat.ui import states

  set_default_gcp_project_id = states.set_default_gcp_project_id
except ImportError:
  # The UI may not be available if the user has not installed Mesop. In this
  # case, we will just ignore the import error.
  print("Copycat UI is not available. Please install Mesop to use the UI.")
  pass
