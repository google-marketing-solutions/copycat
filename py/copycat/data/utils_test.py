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

from absl.testing import absltest
from absl.testing import parameterized
import pandas as pd

from copycat import copycat
from copycat import google_ads
from copycat.data import utils


class ExplodeAndCollapseHeadlinesAndDescriptionsTest(parameterized.TestCase):

  @parameterized.named_parameters(
      dict(
          testcase_name="with_headlines_and_descriptions",
          data=pd.DataFrame({
              "Headline 1": ["a", "b"],
              "Headline 2": ["c", "--"],
              "Headline 3": ["d", ""],
              "Description 1": ["e", "f"],
              "Description 2": ["g", "--"],
              "Other column": [1, 2],
          }),
          expected=pd.DataFrame({
              "headlines": [["a", "c", "d"], ["b"]],
              "descriptions": [["e", "g"], ["f"]],
              "Other column": [1, 2],
          }),
      ),
      dict(
          testcase_name="with_no_headlines",
          data=pd.DataFrame({
              "Description 1": ["e", "f"],
              "Description 2": ["g", "--"],
              "Other column": [1, 2],
          }),
          expected=pd.DataFrame({
              "headlines": [[], []],
              "descriptions": [["e", "g"], ["f"]],
              "Other column": [1, 2],
          }),
      ),
      dict(
          testcase_name="with_no_descriptions",
          data=pd.DataFrame({
              "Headline 1": ["a", "b"],
              "Headline 2": ["c", "--"],
              "Headline 3": ["d", ""],
              "Other column": [1, 2],
          }),
          expected=pd.DataFrame({
              "headlines": [["a", "c", "d"], ["b"]],
              "descriptions": [[], []],
              "Other column": [1, 2],
          }),
      ),
      dict(
          testcase_name="with_no_headlines_or_descriptions",
          data=pd.DataFrame({"Other column": [1, 2]}),
          expected=pd.DataFrame({
              "headlines": [[], []],
              "descriptions": [[], []],
              "Other column": [1, 2],
          }),
      ),
  )
  def test_collapse_headlines_and_descriptions(self, data, expected):
    actual = utils.collapse_headlines_and_descriptions(data)
    pd.testing.assert_frame_equal(actual, expected, check_like=True)

  @parameterized.named_parameters(
      dict(
          testcase_name="with_headlines_and_descriptions",
          data=pd.DataFrame({
              "headlines": [["a", "c", "d"], ["b"]],
              "descriptions": [["e", "g"], ["f"]],
              "Other column": [1, 2],
          }),
          expected=pd.DataFrame({
              "Headline 1": ["a", "b"],
              "Headline 2": ["c", "--"],
              "Headline 3": ["d", "--"],
              "Description 1": ["e", "f"],
              "Description 2": ["g", "--"],
              "Other column": [1, 2],
          }),
      ),
      dict(
          testcase_name="with_no_headlines",
          data=pd.DataFrame({
              "headlines": [[], []],
              "descriptions": [["e", "g"], ["f"]],
              "Other column": [1, 2],
          }),
          expected=pd.DataFrame({
              "Description 1": ["e", "f"],
              "Description 2": ["g", "--"],
              "Other column": [1, 2],
          }),
      ),
      dict(
          testcase_name="with_no_descriptions",
          data=pd.DataFrame({
              "headlines": [["a", "c", "d"], ["b"]],
              "descriptions": [[], []],
              "Other column": [1, 2],
          }),
          expected=pd.DataFrame({
              "Headline 1": ["a", "b"],
              "Headline 2": ["c", "--"],
              "Headline 3": ["d", "--"],
              "Other column": [1, 2],
          }),
      ),
      dict(
          testcase_name="with_no_headlines_or_descriptions",
          data=pd.DataFrame({
              "headlines": [[], []],
              "descriptions": [[], []],
              "Other column": [1, 2],
          }),
          expected=pd.DataFrame({"Other column": [1, 2]}),
      ),
  )
  def test_explode_headlines_and_descriptions(self, data, expected):
    actual = utils.explode_headlines_and_descriptions(data)
    pd.testing.assert_frame_equal(actual, expected, check_like=True)

  @parameterized.named_parameters(
      dict(
          testcase_name="with_headlines_and_descriptions",
          data=pd.DataFrame({
              "headlines": [["a", "c", "d"], ["b"]],
              "descriptions": [["e", "g"], ["f"]],
              "Other column": [1, 2],
          }),
          expected=pd.DataFrame({
              "Headline 1": ["a", "b"],
              "Headline 2": ["c", "--"],
              "Headline 3": ["d", "--"],
              "Headline 4": ["--", "--"],
              "Headline 5": ["--", "--"],
              "Description 1": ["e", "f"],
              "Description 2": ["g", "--"],
              "Description 3": ["--", "--"],
              "Other column": [1, 2],
          }),
      ),
      dict(
          testcase_name="with_no_headlines",
          data=pd.DataFrame({
              "headlines": [[], []],
              "descriptions": [["e", "g"], ["f"]],
              "Other column": [1, 2],
          }),
          expected=pd.DataFrame({
              "Headline 1": ["--", "--"],
              "Headline 2": ["--", "--"],
              "Headline 3": ["--", "--"],
              "Headline 4": ["--", "--"],
              "Headline 5": ["--", "--"],
              "Description 1": ["e", "f"],
              "Description 2": ["g", "--"],
              "Description 3": ["--", "--"],
              "Other column": [1, 2],
          }),
      ),
      dict(
          testcase_name="with_no_descriptions",
          data=pd.DataFrame({
              "headlines": [["a", "c", "d"], ["b"]],
              "descriptions": [[], []],
              "Other column": [1, 2],
          }),
          expected=pd.DataFrame({
              "Headline 1": ["a", "b"],
              "Headline 2": ["c", "--"],
              "Headline 3": ["d", "--"],
              "Headline 4": ["--", "--"],
              "Headline 5": ["--", "--"],
              "Description 1": ["--", "--"],
              "Description 2": ["--", "--"],
              "Description 3": ["--", "--"],
              "Other column": [1, 2],
          }),
      ),
      dict(
          testcase_name="with_no_headlines_or_descriptions",
          data=pd.DataFrame({
              "headlines": [[], []],
              "descriptions": [[], []],
              "Other column": [1, 2],
          }),
          expected=pd.DataFrame({
              "Headline 1": ["--", "--"],
              "Headline 2": ["--", "--"],
              "Headline 3": ["--", "--"],
              "Headline 4": ["--", "--"],
              "Headline 5": ["--", "--"],
              "Description 1": ["--", "--"],
              "Description 2": ["--", "--"],
              "Description 3": ["--", "--"],
              "Other column": [1, 2],
          }),
      ),
  )
  def test_explode_headlines_and_descriptions_applies_max_headlines_and_descriptions(
      self, data, expected
  ):
    actual = utils.explode_headlines_and_descriptions(
        data, max_headlines=5, max_descriptions=3
    )
    pd.testing.assert_frame_equal(actual, expected, check_like=True)

  @parameterized.named_parameters(
      dict(
          testcase_name="too many headlines",
          max_headlines=2,
          max_descriptions=3,
      ),
      dict(
          testcase_name="too many descriptions",
          max_headlines=5,
          max_descriptions=1,
      ),
  )
  def test_explode_headlines_and_descriptions_raises_value_error_if_max_headlines_or_descriptions_too_small(
      self, max_headlines, max_descriptions
  ):
    data = pd.DataFrame({
        "headlines": [["a", "c", "d"], ["b"]],
        "descriptions": [["e", "g"], ["f"]],
        "Other column": [1, 2],
    })
    with self.assertRaises(ValueError):
      utils.explode_headlines_and_descriptions(
          data, max_headlines=max_headlines, max_descriptions=max_descriptions
      )

  def test_explode_headlines_and_descriptions_raises_value_error_if_index_not_unique(
      self,
  ):
    data = pd.DataFrame({
        "headlines": [["a", "c", "d"], ["b"]],
        "descriptions": [["e", "g"], ["f"]],
        "Other column": [1, 1],
    }).set_index("Other column")
    with self.assertRaises(ValueError):
      utils.explode_headlines_and_descriptions(data)

  @parameterized.parameters(
      "headlines",
      "descriptions",
  )
  def test_explode_headlines_and_descriptions_raises_value_error_if_headlines_or_descriptions_are_not_lists(
      self, column_name
  ):
    data = pd.DataFrame({
        "headlines": [["a", "c", "d"], ["b"]],
        "descriptions": [["e", "g"], ["f"]],
        "Other column": [1, 1],
    })
    data[column_name] = ["a", "b"]  # Column does not contain lists.
    with self.assertRaises(ValueError):
      utils.explode_headlines_and_descriptions(data)


class IterateOverBatchesTest(parameterized.TestCase):

  def test_iterate_over_batches(self):
    data = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6, 7]})
    batches = list(utils.iterate_over_batches(data, batch_size=3))

    self.assertLen(batches, 3)
    pd.testing.assert_frame_equal(batches[0], data.iloc[:3])
    pd.testing.assert_frame_equal(batches[1], data.iloc[3:6])
    pd.testing.assert_frame_equal(batches[2], data.iloc[6:7])

  def test_iterate_over_batches_with_limit_rows(self):
    data = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6, 7]})
    batches = list(utils.iterate_over_batches(data, batch_size=3, limit_rows=5))

    self.assertLen(batches, 2)
    pd.testing.assert_frame_equal(batches[0], data.iloc[:3])
    pd.testing.assert_frame_equal(batches[1], data.iloc[3:5])

  def test_iterate_over_batches_with_too_large_limit_rows(self):
    data = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6, 7]})
    batches = list(
        utils.iterate_over_batches(data, batch_size=3, limit_rows=20)
    )

    self.assertLen(batches, 3)
    pd.testing.assert_frame_equal(batches[0], data.iloc[:3])
    pd.testing.assert_frame_equal(batches[1], data.iloc[3:6])
    pd.testing.assert_frame_equal(batches[2], data.iloc[6:7])


class ConstructGenerationDataTest(parameterized.TestCase):

  def test_construct_generation_data_with_new_keywords_data_only(self):
    new_keywords_data = pd.DataFrame({
        "index_column_1": ["a", "a", "b", "b"],
        "index_column_2": ["c", "d", "d", "d"],
        "keyword": ["keyword 1", "keyword 2", "keyword 3", "keyword 4"],
    }).set_index(["index_column_1", "index_column_2"])

    actual = utils.construct_generation_data(
        new_keywords_data=new_keywords_data
    )

    expected = pd.DataFrame({
        "index_column_1": ["a", "a", "b"],
        "index_column_2": ["c", "d", "d"],
        "version": ["1", "1", "1"],
        "keywords": ["keyword 1", "keyword 2", "keyword 3, keyword 4"],
        "existing_headlines": [[], [], []],
        "existing_descriptions": [[], [], []],
        "additional_instructions": ["", "", ""],
    }).set_index(["index_column_1", "index_column_2", "version"])

    pd.testing.assert_frame_equal(actual, expected, check_like=True)

  def test_construct_generation_data_with_new_keywords_data_only_multiple_versions(
      self,
  ):
    new_keywords_data = pd.DataFrame({
        "index_column_1": ["a", "a", "b", "b"],
        "index_column_2": ["c", "d", "d", "d"],
        "keyword": ["keyword 1", "keyword 2", "keyword 3", "keyword 4"],
    }).set_index(["index_column_1", "index_column_2"])

    actual = utils.construct_generation_data(
        new_keywords_data=new_keywords_data,
        n_versions=2,
    )

    expected = pd.DataFrame({
        "index_column_1": ["a", "a", "a", "a", "b", "b"],
        "index_column_2": ["c", "c", "d", "d", "d", "d"],
        "version": ["1", "2", "1", "2", "1", "2"],
        "keywords": [
            "keyword 1",
            "keyword 1",
            "keyword 2",
            "keyword 2",
            "keyword 3, keyword 4",
            "keyword 3, keyword 4",
        ],
        "existing_headlines": [[], [], [], [], [], []],
        "existing_descriptions": [[], [], [], [], [], []],
        "additional_instructions": ["", "", "", "", "", ""],
    }).set_index(["index_column_1", "index_column_2", "version"])

    pd.testing.assert_frame_equal(actual, expected, check_like=True)

  def test_construct_generation_data_with_existing_generations_data(self):
    new_keywords_data = pd.DataFrame({
        "index_column_1": ["a", "a", "b", "b"],
        "index_column_2": ["c", "d", "d", "d"],
        "keyword": ["keyword 1", "keyword 2", "keyword 3", "keyword 4"],
    }).set_index(["index_column_1", "index_column_2"])

    existing_generations_data = pd.DataFrame({
        "index_column_1": ["a", "a"],
        "index_column_2": ["c", "d"],
        "version": ["1", "1"],
        "existing_headlines": [["headline 1"], ["headline 2"]],
        "existing_descriptions": [
            ["description 1"],
            ["description 2"],
        ],
    }).set_index(["index_column_1", "index_column_2", "version"])

    actual = utils.construct_generation_data(
        new_keywords_data=new_keywords_data,
        existing_generations_data=existing_generations_data,
    )

    expected = pd.DataFrame({
        "index_column_1": ["a", "a", "b"],
        "index_column_2": ["c", "d", "d"],
        "version": ["1", "1", "1"],
        "keywords": ["keyword 1", "keyword 2", "keyword 3, keyword 4"],
        "existing_headlines": [["headline 1"], ["headline 2"], []],
        "existing_descriptions": [
            ["description 1"],
            ["description 2"],
            [],
        ],
        "additional_instructions": ["", "", ""],
    }).set_index(["index_column_1", "index_column_2", "version"])

    pd.testing.assert_frame_equal(actual, expected, check_like=True)

  def test_construct_generation_data_raises_value_error_if_existing_generations_data_not_unique(
      self,
  ):
    new_keywords_data = pd.DataFrame({
        "index_column_1": ["a", "a", "b", "b"],
        "index_column_2": ["c", "d", "d", "d"],
        "keyword": ["keyword 1", "keyword 2", "keyword 3", "keyword 4"],
    }).set_index(["index_column_1", "index_column_2"])

    existing_generations_data = pd.DataFrame({
        "index_column_1": ["a", "a"],
        "index_column_2": ["c", "c"],
        "version": ["1", "1"],
        "existing_headlines": [["headline 1"], ["headline 2"]],
        "existing_descriptions": [
            ["description 1"],
            ["description 2"],
        ],
    }).set_index(["index_column_1", "index_column_2", "version"])

    with self.assertRaisesWithLiteralMatch(
        ValueError,
        "The index columns of the existing_generations_data are not unique,"
        " cannot merge with the new keywords data.",
    ):
      utils.construct_generation_data(
          new_keywords_data=new_keywords_data,
          existing_generations_data=existing_generations_data,
      )

  def test_construct_generation_data_with_additional_instructions(self):
    new_keywords_data = pd.DataFrame({
        "index_column_1": ["a", "a", "b", "b"],
        "index_column_2": ["c", "d", "d", "d"],
        "keyword": ["keyword 1", "keyword 2", "keyword 3", "keyword 4"],
    }).set_index(["index_column_1", "index_column_2"])

    additional_instructions_data = pd.DataFrame({
        "index_column_1": ["a", "a", "a", "a"],
        "index_column_2": ["c", "d", "c", "c"],
        "version": ["1", "1", "2", "2"],
        "additional_instructions": [
            "instruction 1",
            "instruction 2",
            "instruction 3",
            "instruction 4",
        ],
        "existing_headlines": [[], [], [], []],
        "existing_descriptions": [[], [], [], []],
    }).set_index(["index_column_1", "index_column_2", "version"])

    actual = utils.construct_generation_data(
        new_keywords_data=new_keywords_data,
        additional_instructions_data=additional_instructions_data,
        n_versions=2,
    )

    expected = pd.DataFrame({
        "index_column_1": ["a", "a", "a", "a", "b", "b"],
        "index_column_2": ["c", "c", "d", "d", "d", "d"],
        "version": ["1", "2", "1", "2", "1", "2"],
        "keywords": [
            "keyword 1",
            "keyword 1",
            "keyword 2",
            "keyword 2",
            "keyword 3, keyword 4",
            "keyword 3, keyword 4",
        ],
        "additional_instructions": [
            "instruction 1",
            "instruction 3\ninstruction 4",
            "instruction 2",
            "",
            "",
            "",
        ],
        "existing_headlines": [[], [], [], [], [], []],
        "existing_descriptions": [[], [], [], [], [], []],
    }).set_index(["index_column_1", "index_column_2", "version"])

    pd.testing.assert_frame_equal(actual, expected, check_like=True)

  def test_construct_generation_data_with_additional_instructions_with_all(
      self,
  ):
    new_keywords_data = pd.DataFrame({
        "index_column_1": ["a", "a", "b", "b"],
        "index_column_2": ["c", "d", "d", "d"],
        "keyword": ["keyword 1", "keyword 2", "keyword 3", "keyword 4"],
    }).set_index(["index_column_1", "index_column_2"])

    additional_instructions_data = pd.DataFrame({
        "index_column_1": [
            "a",
            "__ALL__",
            "b",
            "__ALL__",
            "a",
            "__ALL__",
            "b",
            "__ALL__",
        ],
        "index_column_2": [
            "c",
            "d",
            "__ALL__",
            "__ALL__",
            "c",
            "d",
            "__ALL__",
            "__ALL__",
        ],
        "version": [
            "1",
            "1",
            "1",
            "1",
            "__ALL__",
            "__ALL__",
            "__ALL__",
            "__ALL__",
        ],
        "additional_instructions": [
            "(a,c,1)",
            "(all,d,1)",
            "(b,all,1)",
            "(all,all,1)",
            "(a,c,all)",
            "(all,d,all)",
            "(b,all,all)",
            "(all,all,all)",
        ],
    }).set_index(["index_column_1", "index_column_2", "version"])

    actual = utils.construct_generation_data(
        new_keywords_data=new_keywords_data,
        additional_instructions_data=additional_instructions_data,
        n_versions=2,
    )

    expected = pd.DataFrame({
        "index_column_1": ["a", "a", "a", "a", "b", "b"],
        "index_column_2": ["c", "c", "d", "d", "d", "d"],
        "version": ["1", "2", "1", "2", "1", "2"],
        "keywords": [
            "keyword 1",
            "keyword 1",
            "keyword 2",
            "keyword 2",
            "keyword 3, keyword 4",
            "keyword 3, keyword 4",
        ],
        "additional_instructions": [
            "(a,c,1)\n(a,c,all)\n(all,all,1)\n(all,all,all)",
            "(a,c,all)\n(all,all,all)",
            "(all,all,1)\n(all,all,all)\n(all,d,1)\n(all,d,all)",
            "(all,all,all)\n(all,d,all)",
            "(all,all,1)\n(all,all,all)\n(all,d,1)\n(all,d,all)\n(b,all,1)\n(b,all,all)",
            "(all,all,all)\n(all,d,all)\n(b,all,all)",
        ],
        "existing_headlines": [[], [], [], [], [], []],
        "existing_descriptions": [[], [], [], [], [], []],
    }).set_index(["index_column_1", "index_column_2", "version"])

    pd.testing.assert_frame_equal(actual, expected, check_like=True)

  def test_construct_generation_data_with_empty_additional_instructions(
      self,
  ):
    new_keywords_data = pd.DataFrame({
        "index_column_1": ["a", "a", "b", "b"],
        "index_column_2": ["c", "d", "d", "d"],
        "keyword": ["keyword 1", "keyword 2", "keyword 3", "keyword 4"],
    }).set_index(["index_column_1", "index_column_2"])

    additional_instructions_data = pd.DataFrame(
        columns=[
            "index_column_1",
            "index_column_2",
            "version",
            "additional_instructions",
        ]
    ).set_index(["index_column_1", "index_column_2", "version"])

    actual = utils.construct_generation_data(
        new_keywords_data=new_keywords_data,
        additional_instructions_data=additional_instructions_data,
        n_versions=2,
    )

    expected = pd.DataFrame({
        "index_column_1": ["a", "a", "a", "a", "b", "b"],
        "index_column_2": ["c", "c", "d", "d", "d", "d"],
        "version": ["1", "2", "1", "2", "1", "2"],
        "keywords": [
            "keyword 1",
            "keyword 1",
            "keyword 2",
            "keyword 2",
            "keyword 3, keyword 4",
            "keyword 3, keyword 4",
        ],
        "additional_instructions": ["", "", "", "", "", ""],
        "existing_headlines": [[], [], [], [], [], []],
        "existing_descriptions": [[], [], [], [], [], []],
    }).set_index(["index_column_1", "index_column_2", "version"])

    pd.testing.assert_frame_equal(actual, expected, check_like=True)

  def test_construct_generation_data_with_empty_existing_generations(
      self,
  ):
    new_keywords_data = pd.DataFrame({
        "index_column_1": ["a", "a", "b", "b"],
        "index_column_2": ["c", "d", "d", "d"],
        "keyword": ["keyword 1", "keyword 2", "keyword 3", "keyword 4"],
    }).set_index(["index_column_1", "index_column_2"])

    existing_generations_data = pd.DataFrame(
        columns=[
            "index_column_1",
            "index_column_2",
            "version",
            "existing_headlines",
            "existing_descriptions",
        ]
    ).set_index(["index_column_1", "index_column_2", "version"])

    actual = utils.construct_generation_data(
        new_keywords_data=new_keywords_data,
        existing_generations_data=existing_generations_data,
        n_versions=2,
    )

    expected = pd.DataFrame({
        "index_column_1": ["a", "a", "a", "a", "b", "b"],
        "index_column_2": ["c", "c", "d", "d", "d", "d"],
        "version": ["1", "2", "1", "2", "1", "2"],
        "keywords": [
            "keyword 1",
            "keyword 1",
            "keyword 2",
            "keyword 2",
            "keyword 3, keyword 4",
            "keyword 3, keyword 4",
        ],
        "additional_instructions": ["", "", "", "", "", ""],
        "existing_headlines": [[], [], [], [], [], []],
        "existing_descriptions": [[], [], [], [], [], []],
    }).set_index(["index_column_1", "index_column_2", "version"])

    pd.testing.assert_frame_equal(actual, expected, check_like=True)


class ExplodeGeneratedAdObjectTest(parameterized.TestCase):

  def test_explode_generated_ads_object(self):
    data = pd.DataFrame({
        "generated_ad_object": [
            copycat.CopycatResponse(
                google_ad=google_ads.GoogleAd(
                    headlines=["headline 1", "headline 2"],
                    descriptions=["description 1", "description 2"],
                ),
                keywords="keyword 1, keyword 2",
                evaluation_results=copycat.EvaluationResults(
                    headlines_are_memorised=True,
                    descriptions_are_memorised=True,
                    style_similarity=0.5,
                    keyword_similarity=0.6,
                    warnings=["warning 1", "warning 2"],
                    errors=["error 1", "error 2"],
                ),
            ),
            copycat.CopycatResponse(
                google_ad=google_ads.GoogleAd(
                    headlines=["headline 3", "headline 4"],
                    descriptions=["description 3", "description 4"],
                ),
                keywords="keyword 3, keyword 4",
                evaluation_results=copycat.EvaluationResults(
                    headlines_are_memorised=False,
                    descriptions_are_memorised=False,
                    style_similarity=0.25,
                    keyword_similarity=0.35,
                    warnings=[],
                    errors=[],
                ),
            ),
        ],
    })

    exploded_data = utils.explode_generated_ad_object(data)
    expected_data = pd.DataFrame({
        "headlines": [
            ["headline 1", "headline 2"],
            ["headline 3", "headline 4"],
        ],
        "descriptions": [
            ["description 1", "description 2"],
            ["description 3", "description 4"],
        ],
        "Success": [False, True],
        "Headlines are Memorized": [True, False],
        "Descriptions are Memorized": [True, False],
        "Style Similarity": [0.5, 0.25],
        "Keyword Similarity": [0.6, 0.35],
        "Warnings": ["- warning 1\n- warning 2", ""],
        "Errors": ["- error 1\n- error 2", ""],
    })
    expected_data["generated_ad_object"] = data["generated_ad_object"].copy()

    pd.testing.assert_frame_equal(exploded_data, expected_data, check_like=True)


if __name__ == "__main__":
  absltest.main()
